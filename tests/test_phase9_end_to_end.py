"""Deterministic end-to-end release evaluation for the Phase 9 workflow."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.database import (
    create_document,
    create_product,
    get_document,
    initialize_database,
    list_documents_for_product,
    list_generated_artifacts_for_product,
    list_retrievable_document_sections,
)
from src.document_templates import document_template
from src.generated_content import GeneratedContentReviewService, ReviewDecision
from src.grounded_generation import GroundedGenerationService
from src.models import DocumentStatus, DocumentType
from src.prompt_catalog import GROUNDED_DRAFT_PROMPT_ID, AssistantTask
from tests.success_matrix_fixtures import complete_prd_agile_hierarchy, complete_success_matrix
from src.rag_evaluation import (
    Phase9EvaluationCase,
    evaluate_phase9_case,
    evaluate_phase9_suite,
)
from src.semantic_retrieval import (
    SemanticRetrievalResponse,
    SemanticRetriever,
    chunk_approved_sections,
)


class DeterministicAIProvider:
    """Local fake implementing both Phase 9 provider boundaries."""

    def __init__(self) -> None:
        self.embedding_calls = 0
        self.generation_calls = 0

    def create_embeddings(self, texts: list[str]) -> list[tuple[float, ...]]:
        self.embedding_calls += 1
        return [(1.0, 0.0) for _ in texts]

    def create_text_response(
        self,
        input_text: str,
        *,
        instructions: str | None = None,
    ) -> str:
        self.generation_calls += 1
        return "Deterministic grounded draft [Source 1]"


class FixedRetrievalProvider:
    def __init__(self, response: SemanticRetrievalResponse) -> None:
        self.response = response

    def retrieve(self, query: str, *, limit: int) -> SemanticRetrievalResponse:
        return self.response


class Phase9EndToEndEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "phase9.db"
        initialize_database(self.database_path)
        self.product = create_product(
            {
                "name": "Atlas",
                "description": "Portfolio workspace.",
                "target_users": "Product leaders",
                "business_goal": "Improve decisions.",
                "status": "planning",
            },
            self.database_path,
        )

    def create_source(
        self,
        title: str,
        *,
        status: DocumentStatus,
        document_type: DocumentType = DocumentType.PRD,
    ):
        return create_document(
            {
                "product_id": self.product.id,
                "document_type": document_type,
                "title": title,
                "version": "1.0",
                "document_status": status,
                "sections": {
                    section.key: f"{title} evidence for {section.label}."
                    for section in document_template(document_type)
                },
                "success_matrix": (
                    complete_success_matrix()
                    if document_type is DocumentType.PRD
                    and status is DocumentStatus.APPROVED
                    else []
                ),
                "agile_hierarchy": (
                    complete_prd_agile_hierarchy(f"phase9-{title.lower().replace(' ', '-')}")
                    if document_type is DocumentType.PRD
                    and status is DocumentStatus.APPROVED
                    else []
                ),
            },
            self.database_path,
        )

    def retrieve(self, provider: DeterministicAIProvider):
        return SemanticRetriever(
            lambda: list_retrievable_document_sections(self.database_path),
            provider,
        ).retrieve("Draft a launch summary", limit=100)

    @staticmethod
    def generate(retrieval, provider):
        return GroundedGenerationService(
            FixedRetrievalProvider(retrieval),
            provider,
        ).generate(
            "Draft a launch summary",
            task=AssistantTask.GROUNDED_DRAFT,
            prompt_id=GROUNDED_DRAFT_PROMPT_ID,
            limit=100,
        )

    def test_successful_workflow_scores_100_and_passes_release_criteria(self):
        approved = self.create_source(
            "Approved launch PRD",
            status=DocumentStatus.APPROVED,
        )
        draft = self.create_source(
            "Draft strategy BRD",
            status=DocumentStatus.DRAFT,
            document_type=DocumentType.BRD,
        )
        approved_before = get_document(approved.id, self.database_path)
        draft_before = get_document(draft.id, self.database_path)
        expected_chunks = chunk_approved_sections(
            list_retrievable_document_sections(self.database_path)
        )
        provider = DeterministicAIProvider()

        retrieval = self.retrieve(provider)
        generation = self.generate(retrieval, provider)
        review_service = GeneratedContentReviewService(
            self.database_path,
            key_factory=lambda: "phase9-release-review",
        )
        review = review_service.begin_review(
            product_id=self.product.id,
            request="Draft a launch summary",
            generation=generation,
        )
        nothing_saved_before_acceptance = (
            review.decision is ReviewDecision.PENDING
            and not list_generated_artifacts_for_product(
                self.product.id, self.database_path
            )
        )
        review = review_service.revise(
            review,
            "Human-reviewed grounded draft [Source 1]",
        )
        nothing_saved_after_revision = not list_generated_artifacts_for_product(
            self.product.id, self.database_path
        )
        accepted = review_service.accept(review)

        sources_unchanged = (
            get_document(approved.id, self.database_path) == approved_before
            and get_document(draft.id, self.database_path) == draft_before
            and list_documents_for_product(self.product.id, self.database_path)
            == [draft_before, approved_before]
        )
        report = evaluate_phase9_case(
            Phase9EvaluationCase(
                name="successful review and acceptance",
                expected_chunk_ids=frozenset(
                    chunk.chunk_id for chunk in expected_chunks
                ),
                retrieval=retrieval,
                generation=generation,
                grounding_expected=True,
                human_control_preserved=(
                    nothing_saved_before_acceptance
                    and nothing_saved_after_revision
                    and accepted.review.decision is ReviewDecision.ACCEPTED
                    and accepted.artifact.original_content == generation.content
                    and accepted.artifact.was_revised
                ),
                source_separation_preserved=sources_unchanged,
            )
        )

        self.assertEqual(report.scores.criteria, (1.0,) * 8)
        self.assertEqual(report.scores.overall_score, 100.0)
        self.assertTrue(report.release_passed)
        self.assertEqual(provider.embedding_calls, 1)
        self.assertEqual(provider.generation_calls, 1)
        self.assertEqual(
            {citation.document_id for citation in generation.citations},
            {approved.id},
        )
        self.assertNotIn(
            draft.id,
            {citation.document_id for citation in generation.citations},
        )
        self.assertEqual(len(accepted.artifact.citations), len(generation.citations))

    def test_no_approved_sources_is_safe_and_scores_100_without_provider_calls(self):
        self.create_source("Draft only", status=DocumentStatus.DRAFT)
        provider = DeterministicAIProvider()

        retrieval = self.retrieve(provider)
        generation = self.generate(retrieval, provider)
        report = evaluate_phase9_case(
            Phase9EvaluationCase(
                "no approved evidence",
                frozenset(),
                retrieval,
                generation,
                False,
                True,
                True,
            )
        )

        self.assertEqual(report.scores.overall_score, 100.0)
        self.assertTrue(report.release_passed)
        self.assertEqual(provider.embedding_calls, 0)
        self.assertEqual(provider.generation_calls, 0)
        self.assertEqual(
            list_generated_artifacts_for_product(
                self.product.id, self.database_path
            ),
            [],
        )

    def test_source_changed_during_retrieval_is_not_grounded_or_generated(self):
        approved = self.create_source(
            "Changing source",
            status=DocumentStatus.APPROVED,
        )

        class ChangingProvider(DeterministicAIProvider):
            def create_embeddings(inner_self, texts):
                with sqlite3.connect(self.database_path) as connection:
                    connection.execute(
                        """
                        UPDATE document_sections
                        SET content = content || ' changed after embedding input'
                        WHERE document_id = ?
                        """,
                        (approved.id,),
                    )
                return super().create_embeddings(texts)

        provider = ChangingProvider()
        retrieval = self.retrieve(provider)
        generation_provider = Mock()
        generation = GroundedGenerationService(
            FixedRetrievalProvider(retrieval),
            generation_provider,
        ).generate(
            "Draft a launch summary",
            task=AssistantTask.GROUNDED_DRAFT,
            prompt_id=GROUNDED_DRAFT_PROMPT_ID,
        )
        report = evaluate_phase9_case(
            Phase9EvaluationCase(
                "source changed during retrieval",
                frozenset(),
                retrieval,
                generation,
                False,
                True,
                True,
            )
        )

        self.assertEqual(report.scores.overall_score, 100.0)
        self.assertTrue(report.release_passed)
        generation_provider.create_text_response.assert_not_called()

    def test_rejection_remains_unsaved_and_contributes_a_passing_suite_case(self):
        self.create_source("Approved source", status=DocumentStatus.APPROVED)
        provider = DeterministicAIProvider()
        retrieval = self.retrieve(provider)
        generation = self.generate(retrieval, provider)
        review_service = GeneratedContentReviewService(
            self.database_path,
            key_factory=lambda: "phase9-rejected-review",
        )
        review = review_service.begin_review(
            product_id=self.product.id,
            request="Draft a launch summary",
            generation=generation,
        )
        rejected = review_service.reject(review)
        expected_ids = frozenset(
            result.chunk.chunk_id for result in retrieval.results
        )
        rejected_case = Phase9EvaluationCase(
            "explicit rejection",
            expected_ids,
            retrieval,
            generation,
            True,
            rejected.decision is ReviewDecision.REJECTED
            and not list_generated_artifacts_for_product(
                self.product.id, self.database_path
            ),
            True,
        )
        repeated_case = Phase9EvaluationCase(
            "deterministic repeated observation",
            expected_ids,
            retrieval,
            generation,
            True,
            True,
            True,
        )

        suite = evaluate_phase9_suite((rejected_case, repeated_case))

        self.assertEqual(suite.scores.criteria, (1.0,) * 8)
        self.assertEqual(suite.scores.overall_score, 100.0)
        self.assertTrue(suite.release_passed)


if __name__ == "__main__":
    unittest.main()
