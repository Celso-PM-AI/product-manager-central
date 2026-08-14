"""Focused offline tests for Phase 10 Checkpoint 10."""

from dataclasses import replace
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest
from unittest.mock import patch

from src.agile import (
    AgileAcceptanceCriterion,
    AgileArtifact,
    AgileArtifactType,
    AgileBehaviorProfile,
    AgileReviewState,
    AgileSourceReference,
    ContentProvenance,
    AgileContractError,
)
from src.agile_generation import (
    AgileGenerationRequest,
    AgileGenerationResult,
    AgileGenerationState,
    MissingRequirement,
    NonSaveableProposal,
    SourceScopedAgileRetriever,
)
from src.agile_prompt_catalog import AgilePromptSource, AgilePromptTask
from src.agile_review import (
    AgileReviewAction,
    AgileReviewBatch,
    AgileReviewBlockCode,
    AgileReviewError,
    AgileReviewService,
)
from src.claim_support import ClaimSupportOutcome
from src.database import (
    AgilePersistenceError,
    create_document,
    create_product,
    get_accepted_agile_batch,
    initialize_database,
    list_accepted_agile_batches_for_product,
    save_reviewed_agile_batch,
)
from src.document_templates import document_template
from src.model_controls import RetrievalControls
from src.models import DocumentStatus, DocumentType
from tests.success_matrix_fixtures import complete_prd_agile_hierarchy, complete_success_matrix
from src.semantic_retrieval import chunk_approved_sections
from src.database import list_retrievable_document_sections


NOW = "2026-08-13T12:00:00Z"
LATER = "2026-08-13T12:01:00Z"


class NeverEmbeddingProvider:
    def create_embeddings(self, texts):
        raise AssertionError("Review must not call an embedding or model provider.")


class Clock:
    def __init__(self):
        self.values = iter((NOW, LATER, LATER, LATER, LATER, LATER, LATER))

    def __call__(self):
        return next(self.values)


class Checkpoint10ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "review.db"
        initialize_database(self.database_path)
        self.product = create_product(
            {
                "name": "Atlas",
                "description": "A portfolio planning workspace.",
                "target_users": "Product leaders",
                "business_goal": "Improve planning decisions.",
                "status": "planning",
            },
            self.database_path,
        )
        source_text = (
            "Customer account access. Customers must sign in. "
            "Sign-in succeeds with valid credentials. Customers must use MFA."
        )
        sections = {
            definition.key: (
                source_text
                if index == 0
                else f"Approved evidence for {definition.label}."
            )
            for index, definition in enumerate(document_template(DocumentType.PRD))
        }
        self.document = create_document(
            {
                "product_id": self.product.id,
                "document_type": DocumentType.PRD,
                "title": "Atlas PRD",
                "version": "1.0",
                "document_status": DocumentStatus.APPROVED,
                "success_matrix": complete_success_matrix(),
                "agile_hierarchy": complete_prd_agile_hierarchy("checkpoint10"),
                "sections": sections,
            },
            self.database_path,
        )
        all_chunks = chunk_approved_sections(
            list_retrievable_document_sections(self.database_path)
        )
        self.chunk = next(chunk for chunk in all_chunks if source_text in chunk.text)
        self.prompt_source = AgilePromptSource(
            reference_id=self.chunk.chunk_id,
            product_id=self.chunk.product_id,
            product_name=self.chunk.product_name,
            document_id=self.chunk.document_id,
            document_title=self.chunk.document_title,
            document_type=self.chunk.document_type,
            document_status=self.chunk.document_status,
            section_key=self.chunk.section_key,
            section_title=self.chunk.section_title,
            source_text=self.chunk.text,
        )
        self.source = AgileSourceReference(
            reference_id=self.chunk.chunk_id,
            product_id=self.chunk.product_id,
            product_name=self.chunk.product_name,
            document_id=self.chunk.document_id,
            document_title=self.chunk.document_title,
            document_type=self.chunk.document_type,
            section_key=self.chunk.section_key,
            section_title=self.chunk.section_title,
        )
        self.artifact = AgileArtifact(
            artifact_id="epic-generated",
            artifact_type=AgileArtifactType.EPIC,
            product_id=self.product.id,
            title="Customer account access",
            description="Customers must sign in",
            acceptance_criteria=(
                AgileAcceptanceCriterion(
                    "criterion-1",
                    1,
                    "Sign-in succeeds with valid credentials",
                    (self.source,),
                ),
            ),
            source_references=(self.source,),
            position=1,
            created_at=NOW,
            updated_at=NOW,
        )
        self.request = AgileGenerationRequest(
            product_id=self.product.id,
            selected_document_ids=(self.document.id,),
            artifact_type=AgileArtifactType.EPIC,
            task=AgilePromptTask.GENERATE_EPIC,
            prompt_id="agile-epic",
            prompt_version="1.0.0",
            request_text="Create grounded Agile content.",
            profile=AgileBehaviorProfile.STRICTLY_GROUNDED,
            retrieval_controls=RetrievalControls(5),
        )
        self.generation = AgileGenerationResult(
            state=AgileGenerationState.GENERATED,
            message="Ready for review.",
            artifacts=(self.artifact,),
            review_artifacts=(self.artifact,),
            prompt_sources=(self.prompt_source,),
            retrieval_chunks=(self.chunk,),
            source_references=(self.source,),
            profile=AgileBehaviorProfile.STRICTLY_GROUNDED,
            prompt_id="agile-epic",
            prompt_version="1.0.0",
            grounded=True,
        )
        self.retriever = SourceScopedAgileRetriever(
            lambda: list_retrievable_document_sections(self.database_path),
            NeverEmbeddingProvider(),
        )

    def service(self):
        return AgileReviewService(
            self.retriever,
            self.database_path,
            timestamp_factory=Clock(),
            review_id_factory=lambda: "review-1",
        )

    def review(self):
        return self.service().begin_review(
            self.request, self.generation, reviewer_id="pm-1"
        )

    def assert_blocked(self, callable_, code):
        with self.assertRaises(AgileReviewError) as raised:
            callable_()
        self.assertIn(code, {reason.code for reason in raised.exception.reasons})

    def test_begin_review_preserves_complete_unsaved_generation_evidence(self):
        review = self.review()
        self.assertIs(review.review_state, AgileReviewState.PENDING_REVIEW)
        self.assertEqual(review.original_artifacts, (self.artifact,))
        self.assertEqual(review.source_chunks, (self.chunk,))
        self.assertEqual(review.request.retrieval_controls.top_k, 5)
        self.assertTrue(review.can_accept)
        self.assertEqual(review.events[0].action, AgileReviewAction.BEGIN)
        self.assertEqual(list_accepted_agile_batches_for_product(self.product.id, self.database_path), [])

    def test_acceptance_requires_a_review_and_current_version(self):
        service = self.service()
        self.assert_blocked(
            lambda: service.accept(self.generation, expected_revision=1, reviewer_id="pm-1"),
            AgileReviewBlockCode.INVALID_REVIEW,
        )
        review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
        self.assert_blocked(
            lambda: service.accept(review, expected_revision=2, reviewer_id="pm-1"),
            AgileReviewBlockCode.STALE_VERSION,
        )

    def test_revision_reassesses_changed_title_and_preserves_unchanged_claim_ids(self):
        service = self.service()
        review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
        before = {claim.location: claim.claim_id for claim in review.claims}
        revised = service.revise(
            review,
            (replace(self.artifact, title="Customers must use MFA"),),
            expected_revision=1,
            reviewer_id="pm-1",
        )
        after = {claim.location: claim.claim_id for claim in revised.claims}
        self.assertEqual(revised.revision, 2)
        self.assertEqual(before["description"], after["description"])
        self.assertNotEqual(before["title"], after["title"])
        self.assertTrue(revised.can_accept)
        self.assertTrue(all(item.supported for item in revised.assessments))

    def test_unchanged_revision_is_a_deterministic_no_op(self):
        service = self.service()
        review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
        self.assertIs(
            service.revise(
                review,
                review.artifacts,
                expected_revision=1,
                reviewer_id="pm-1",
            ),
            review,
        )

    def test_unsupported_description_and_criterion_block_independently(self):
        for mutation in (
            lambda artifact: replace(artifact, description="Launch by Friday"),
            lambda artifact: replace(
                artifact,
                acceptance_criteria=(
                    replace(
                        artifact.acceptance_criteria[0],
                        text="Latency must remain under 10 milliseconds",
                    ),
                ),
            ),
        ):
            service = self.service()
            review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
            revised = service.revise(
                review,
                (mutation(self.artifact),),
                expected_revision=1,
                reviewer_id="pm-1",
            )
            with self.subTest(location=revised.assessments[-1].claim.location):
                self.assertFalse(revised.can_accept)
                self.assert_blocked(
                    lambda: service.accept(revised, expected_revision=2, reviewer_id="pm-1"),
                    AgileReviewBlockCode.UNSUPPORTED_CLAIM,
                )

    def test_contradicted_ambiguous_and_missing_source_claims_never_pass(self):
        cases = (
            ("Customers must not sign in", ClaimSupportOutcome.UNSUPPORTED),
            (
                "Customers must sign in using valid credentials",
                ClaimSupportOutcome.AMBIGUOUS,
            ),
        )
        for text, outcome in cases:
            service = self.service()
            review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
            revised = service.revise(
                review,
                (replace(self.artifact, description=text),),
                expected_revision=1,
                reviewer_id="pm-1",
            )
            finding = next(
                item for item in revised.assessments if item.claim.location == "description"
            )
            with self.subTest(outcome=outcome):
                self.assertIs(finding.outcome, outcome)
                self.assertFalse(revised.can_accept)

        fabricated = replace(self.source, reference_id="missing-source")
        service = self.service()
        review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
        revised = service.revise(
            review,
            (
                replace(
                    self.artifact,
                    source_references=(fabricated,),
                    acceptance_criteria=(
                        replace(
                            self.artifact.acceptance_criteria[0],
                            source_references=(fabricated,),
                        ),
                    ),
                ),
            ),
            expected_revision=1,
            reviewer_id="pm-1",
        )
        self.assertTrue(
            any(
                item.outcome is ClaimSupportOutcome.MISSING_SOURCE
                for item in revised.assessments
            )
        )

    def test_domain_contract_rejects_uncited_and_duplicate_citations(self):
        with self.assertRaises(AgileContractError):
            replace(self.artifact, source_references=())
        with self.assertRaises(AgileContractError):
            replace(self.artifact, source_references=(self.source, self.source))

    def test_uncited_fabricated_and_out_of_scope_citations_fail_closed(self):
        fabricated = replace(self.source, reference_id="fabricated")
        for source in (fabricated, replace(self.source, product_id=self.product.id + 1)):
            service = self.service()
            review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
            artifact = replace(
                self.artifact,
                source_references=(source,),
                acceptance_criteria=(replace(self.artifact.acceptance_criteria[0], source_references=(source,)),),
            )
            revised = service.revise(
                review, (artifact,), expected_revision=1, reviewer_id="pm-1"
            )
            with self.subTest(source=source):
                self.assert_blocked(
                    lambda: service.accept(revised, expected_revision=2, reviewer_id="pm-1"),
                    AgileReviewBlockCode.INVALID_CITATION,
                )

    def test_invalid_hierarchy_revision_is_blocked(self):
        service = self.service()
        review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
        self.assert_blocked(
            lambda: service.revise(
                review,
                (
                    replace(
                        self.artifact,
                        artifact_type=AgileArtifactType.CAPABILITY,
                        parent_artifact_id="missing-parent",
                    ),
                ),
                expected_revision=1,
                reviewer_id="pm-1",
            ),
            AgileReviewBlockCode.INVALID_STRUCTURE,
        )

    def test_stale_assessment_cannot_be_accepted(self):
        service = self.service()
        review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
        stale = replace(review, assessed_revision=0)
        self.assert_blocked(
            lambda: service.accept(stale, expected_revision=1, reviewer_id="pm-1"),
            AgileReviewBlockCode.STALE_ASSESSMENT,
        )

    def test_missing_requirements_and_proposals_block_every_profile(self):
        fixtures = (
            replace(
                self.generation,
                state=AgileGenerationState.SUPPORT_BLOCKED,
                grounded=False,
                missing_requirements=(MissingRequirement("gap-1", "Target absent", ()),),
            ),
            replace(
                self.generation,
                state=AgileGenerationState.SUPPORT_BLOCKED,
                grounded=False,
                profile=AgileBehaviorProfile.EXPLORATORY,
                proposals=(NonSaveableProposal("proposal-1", "Try passkeys", "Method absent"),),
            ),
        )
        for generation in fixtures:
            request = replace(self.request, profile=generation.profile)
            service = self.service()
            review = service.begin_review(request, generation, reviewer_id="pm-1")
            with self.subTest(profile=generation.profile):
                self.assertFalse(review.can_accept)
                code = (
                    AgileReviewBlockCode.MISSING_REQUIREMENT
                    if generation.missing_requirements
                    else AgileReviewBlockCode.NON_SAVEABLE_PROPOSAL
                )
                self.assert_blocked(
                    lambda: service.accept(review, expected_revision=1, reviewer_id="pm-1"),
                    code,
                )

    def test_rejection_requires_reason_preserves_history_and_never_saves(self):
        service = self.service()
        review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
        self.assert_blocked(
            lambda: service.reject(
                review, expected_revision=1, reviewer_id="pm-1", reason=" "
            ),
            AgileReviewBlockCode.INVALID_REVIEW,
        )
        rejected = service.reject(
            review,
            expected_revision=1,
            reviewer_id="pm-1",
            reason="The scope is not approved.",
        )
        self.assertIs(rejected.review_state, AgileReviewState.REJECTED)
        self.assertEqual(rejected.events[-1].reason, "The scope is not approved.")
        self.assertIsNone(get_accepted_agile_batch("review-1", self.database_path))
        self.assert_blocked(
            lambda: service.accept(rejected, expected_revision=1, reviewer_id="pm-1"),
            AgileReviewBlockCode.INVALID_TRANSITION,
        )
        self.assert_blocked(
            lambda: service.revise(
                rejected,
                rejected.artifacts,
                expected_revision=1,
                reviewer_id="pm-1",
            ),
            AgileReviewBlockCode.INVALID_TRANSITION,
        )

    def test_missing_reviewer_and_source_provider_failure_are_sanitized(self):
        service = self.service()
        review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
        self.assert_blocked(
            lambda: service.accept(review, expected_revision=1, reviewer_id=" "),
            AgileReviewBlockCode.INVALID_REVIEW,
        )

        class FailingSourceProvider:
            def revalidate(self, chunks):
                raise RuntimeError("secret provider detail")

        failing = AgileReviewService(
            FailingSourceProvider(),
            self.database_path,
            timestamp_factory=Clock(),
            review_id_factory=lambda: "review-failed-provider",
        )
        blocked = failing.begin_review(
            self.request, self.generation, reviewer_id="pm-1"
        )
        self.assertFalse(blocked.can_accept)
        self.assertNotIn("secret", " ".join(reason.message for gate in blocked.gates for reason in gate.reasons))

    def _assert_source_mutation_blocks(self, sql):
        service = self.service()
        review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(sql, (self.document.id,))
        self.assert_blocked(
            lambda: service.accept(review, expected_revision=1, reviewer_id="pm-1"),
            AgileReviewBlockCode.STALE_SOURCE,
        )
        self.assertIsNone(get_accepted_agile_batch("review-1", self.database_path))

    def test_source_becoming_draft_blocks_acceptance(self):
        self._assert_source_mutation_blocks(
            "UPDATE documents SET document_status = 'draft' WHERE id = ?"
        )

    def test_source_deletion_blocks_acceptance(self):
        self._assert_source_mutation_blocks("DELETE FROM documents WHERE id = ?")

    def test_source_content_change_blocks_acceptance(self):
        self._assert_source_mutation_blocks(
            "UPDATE document_sections SET content = 'Changed evidence' WHERE document_id = ?"
        )

    def test_out_of_scope_source_blocks_acceptance(self):
        out_of_scope = replace(
            self.request, selected_document_ids=(self.document.id + 999,)
        )
        service = self.service()
        review = service.begin_review(out_of_scope, self.generation, reviewer_id="pm-1")
        self.assert_blocked(
            lambda: service.accept(review, expected_revision=1, reviewer_id="pm-1"),
            AgileReviewBlockCode.INELIGIBLE_SOURCE,
        )

    def test_source_moving_to_another_product_blocks_acceptance(self):
        other = create_product(
            {
                "name": "Other",
                "description": "Another product.",
                "target_users": "Other users",
                "business_goal": "Keep scope separate.",
                "status": "planning",
            },
            self.database_path,
        )
        service = self.service()
        review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                "UPDATE documents SET product_id = ? WHERE id = ?",
                (other.id, self.document.id),
            )
        self.assert_blocked(
            lambda: service.accept(review, expected_revision=1, reviewer_id="pm-1"),
            AgileReviewBlockCode.STALE_SOURCE,
        )

    def test_changed_prompt_or_profile_metadata_blocks_acceptance(self):
        service = self.service()
        review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
        for request in (
            replace(review.request, prompt_version="2.0.0"),
            replace(review.request, profile=AgileBehaviorProfile.EXPLORATORY),
        ):
            tampered = replace(review, request=request)
            with self.subTest(request=request):
                self.assert_blocked(
                    lambda: service.accept(tampered, expected_revision=1, reviewer_id="pm-1"),
                    AgileReviewBlockCode.INVALID_METADATA,
                )

    def test_acceptance_persists_once_with_provenance_and_complete_evidence(self):
        service = self.service()
        review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
        revised = service.revise(
            review,
            (replace(self.artifact, title="Customers must use MFA"),),
            expected_revision=1,
            reviewer_id="pm-1",
        )
        first = service.accept(revised, expected_revision=2, reviewer_id="pm-2")
        second = service.accept(first.review, expected_revision=2, reviewer_id="pm-2")
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.batch, second.batch)
        self.assertIs(first.batch.artifacts[0].provenance, ContentProvenance.PRODUCT_MANAGER_EDITED)
        self.assertEqual(first.review.events[-1].action, AgileReviewAction.ACCEPT)
        self.assertTrue(all(gate.passed for gate in first.review.gates))
        self.assertTrue(all(item.outcome is ClaimSupportOutcome.SUPPORTED for item in first.review.assessments))

    def test_unused_retrieved_context_is_revalidated_but_need_not_be_cited(self):
        extra = next(
            chunk
            for chunk in chunk_approved_sections(
                list_retrievable_document_sections(self.database_path)
            )
            if chunk.chunk_id != self.chunk.chunk_id
        )
        extra_source = AgilePromptSource(
            reference_id=extra.chunk_id,
            product_id=extra.product_id,
            product_name=extra.product_name,
            document_id=extra.document_id,
            document_title=extra.document_title,
            document_type=extra.document_type,
            document_status=extra.document_status,
            section_key=extra.section_key,
            section_title=extra.section_title,
            source_text=extra.text,
        )
        generation = replace(
            self.generation,
            retrieval_chunks=(self.chunk, extra),
            prompt_sources=(self.prompt_source, extra_source),
        )
        service = self.service()
        review = service.begin_review(self.request, generation, reviewer_id="pm-1")
        accepted = service.accept(review, expected_revision=1, reviewer_id="pm-1")
        self.assertTrue(accepted.created)
        self.assertEqual(accepted.batch.artifacts[0].source_references, (self.source,))

    def test_database_chunk_race_rolls_back_the_entire_acceptance(self):
        service = self.service()
        review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")

        class RaceProvider:
            calls = 0

            def revalidate(inner_self, chunks):
                inner_self.calls += 1
                if inner_self.calls == 2:
                    with closing(sqlite3.connect(self.database_path)) as connection, connection:
                        connection.execute(
                            "UPDATE document_sections SET content = 'Raced content' WHERE document_id = ?",
                            (self.document.id,),
                        )
                return True

        racing_service = AgileReviewService(
            RaceProvider(),
            self.database_path,
            timestamp_factory=Clock(),
            review_id_factory=lambda: "review-race",
        )
        race_review = racing_service.begin_review(
            self.request, self.generation, reviewer_id="pm-1"
        )
        self.assert_blocked(
            lambda: racing_service.accept(race_review, expected_revision=1, reviewer_id="pm-1"),
            AgileReviewBlockCode.PERSISTENCE_FAILED,
        )
        with closing(sqlite3.connect(self.database_path)) as connection:
            counts = tuple(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("agile_generation_runs", "agile_artifacts", "agile_acceptance_criteria")
            )
        self.assertEqual(counts, (0, 0, 0))

    def test_database_review_entry_point_reassesses_and_blocks_direct_bypass(self):
        service = self.service()
        review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
        accepted = service.accept(review, expected_revision=1, reviewer_id="pm-1").batch
        unsafe_artifact = replace(
            accepted.artifacts[0],
            artifact_id="unsafe-epic",
            title="Invented launch date",
        )
        unsafe = replace(
            accepted,
            batch_id="unsafe-review",
            artifacts=(unsafe_artifact,),
        )
        with self.assertRaises(AgilePersistenceError):
            save_reviewed_agile_batch(unsafe, (self.chunk,), self.database_path)
        self.assertIsNone(get_accepted_agile_batch("unsafe-review", self.database_path))

    def test_failure_after_partial_inserts_rolls_back_every_row(self):
        service = self.service()
        review = service.begin_review(self.request, self.generation, reviewer_id="pm-1")
        from src import database as database_module

        original_select = database_module._select_accepted_agile_batch
        calls = 0

        def fail_after_insert(connection, batch_id):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("simulated final read failure")
            return original_select(connection, batch_id)

        with patch(
            "src.database._select_accepted_agile_batch",
            side_effect=fail_after_insert,
        ):
            self.assert_blocked(
                lambda: service.accept(review, expected_revision=1, reviewer_id="pm-1"),
                AgileReviewBlockCode.PERSISTENCE_FAILED,
            )
        with closing(sqlite3.connect(self.database_path)) as connection:
            counts = tuple(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "agile_generation_runs",
                    "agile_artifacts",
                    "agile_acceptance_criteria",
                    "agile_source_snapshots",
                )
            )
        self.assertEqual(counts, (0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
