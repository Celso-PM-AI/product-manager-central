"""Tests for Phase 9 Checkpoint 3 grounded draft generation."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.ai_service import AIConfigurationError, OpenAIService
from src.database import (
    create_document,
    create_product,
    get_document,
    initialize_database,
)
from src.document_templates import document_template
from src.grounded_generation import (
    GROUNDING_INSTRUCTIONS,
    DatabaseGroundedGenerationService,
    GenerationRequestError,
    GroundedGenerationService,
    GroundedGenerationState,
    build_grounded_prompt,
)
from src.models import DocumentStatus, DocumentType
from src.semantic_retrieval import (
    RetrievalChunk,
    SemanticRetrievalResponse,
    SemanticRetrievalResult,
    SemanticRetrievalState,
)


def retrieval_result(
    *,
    state: SemanticRetrievalState = SemanticRetrievalState.RESULTS,
    text: str = "Approved launch requirements.",
) -> SemanticRetrievalResponse:
    results = ()
    if state is SemanticRetrievalState.RESULTS:
        results = (
            SemanticRetrievalResult(
                chunk=RetrievalChunk(
                    chunk_id="document:12:section:launch:chunk:0:test",
                    chunk_index=0,
                    text=text,
                    product_id=7,
                    product_name="Atlas",
                    document_id=12,
                    document_title="Atlas Launch PRD",
                    document_type=DocumentType.PRD,
                    document_status=DocumentStatus.APPROVED,
                    section_key="launch_plan",
                    section_title="Launch plan",
                ),
                similarity=0.9,
            ),
        )
    messages = {
        SemanticRetrievalState.RESULTS: "Found one result.",
        SemanticRetrievalState.NO_APPROVED_SOURCES: (
            "No approved BRD or PRD sources are available."
        ),
        SemanticRetrievalState.NO_RELEVANT_RESULTS: (
            "No relevant approved BRD or PRD sources were found."
        ),
    }
    return SemanticRetrievalResponse(state, messages[state], results)


class GroundedPromptTests(unittest.TestCase):
    def test_prompt_contains_request_trusted_context_and_citation_metadata(self):
        prompt, citations = build_grounded_prompt(
            " Draft a launch summary. ",
            retrieval_result(),
        )

        self.assertIn("Draft a launch summary.", prompt)
        self.assertIn("APPROVED SOURCE CONTEXT", prompt)
        self.assertIn("[Source 1]", prompt)
        self.assertIn("Product: Atlas (ID 7)", prompt)
        self.assertIn("Atlas Launch PRD (ID 12, PRD)", prompt)
        self.assertIn("Section: Launch plan (launch_plan)", prompt)
        self.assertIn("Approved launch requirements.", prompt)
        self.assertIn("Use only the approved source context", GROUNDING_INSTRUCTIONS)
        self.assertEqual(len(citations), 1)
        citation = citations[0]
        self.assertEqual(citation.product, "Atlas")
        self.assertEqual(citation.product_id, 7)
        self.assertEqual(citation.document_title, "Atlas Launch PRD")
        self.assertEqual(citation.document_id, 12)
        self.assertIs(citation.document_type, DocumentType.PRD)
        self.assertEqual(citation.section, "Launch plan")


class GroundedGenerationServiceTests(unittest.TestCase):
    def test_mocked_success_returns_unsaved_generated_draft_with_citations(self):
        retriever = Mock()
        retriever.retrieve.return_value = retrieval_result()
        generator = Mock()
        generator.create_text_response.return_value = "  Launch summary [Source 1]  "
        service = GroundedGenerationService(retriever, generator)

        result = service.generate("Summarize launch readiness.")

        self.assertIs(result.state, GroundedGenerationState.GENERATED_DRAFT)
        self.assertEqual(result.content, "Launch summary [Source 1]")
        self.assertTrue(result.grounded)
        self.assertTrue(result.is_generated_draft)
        self.assertTrue(result.requires_human_review)
        self.assertFalse(result.explicitly_accepted)
        self.assertFalse(result.can_save)
        self.assertEqual(result.citations[0].document_id, 12)
        retriever.retrieve.assert_called_once_with(
            "Summarize launch readiness.", limit=5
        )
        generator.create_text_response.assert_called_once()

    def test_empty_and_invalid_requests_stop_before_retrieval_or_generation(self):
        retriever = Mock()
        generator = Mock()
        service = GroundedGenerationService(retriever, generator)

        for invalid in ("", "   ", None, 42):
            with self.subTest(invalid=invalid):
                with self.assertRaises(GenerationRequestError):
                    service.generate(invalid)

        retriever.retrieve.assert_not_called()
        generator.create_text_response.assert_not_called()

    def test_no_approved_sources_returns_ungrounded_state_without_api_generation(self):
        retriever = Mock()
        retriever.retrieve.return_value = retrieval_result(
            state=SemanticRetrievalState.NO_APPROVED_SOURCES
        )
        generator = Mock()

        result = GroundedGenerationService(retriever, generator).generate("Draft it")

        self.assertIs(result.state, GroundedGenerationState.NO_APPROVED_SOURCES)
        self.assertIsNone(result.content)
        self.assertEqual(result.citations, ())
        self.assertFalse(result.grounded)
        self.assertIn("No grounded draft was generated", result.message)
        generator.create_text_response.assert_not_called()

    def test_no_relevant_results_is_not_claimed_as_grounded(self):
        retriever = Mock()
        retriever.retrieve.return_value = retrieval_result(
            state=SemanticRetrievalState.NO_RELEVANT_RESULTS
        )
        generator = Mock()

        result = GroundedGenerationService(retriever, generator).generate("Draft it")

        self.assertIs(result.state, GroundedGenerationState.NO_RELEVANT_RESULTS)
        self.assertFalse(result.grounded)
        self.assertNotIn("grounded draft content is ready", result.message.lower())
        generator.create_text_response.assert_not_called()

    def test_missing_configuration_stops_before_retrieval_and_network(self):
        factory = Mock()
        with self.assertRaises(AIConfigurationError):
            OpenAIService.from_environment(environ={}, client_factory=factory)
        factory.assert_not_called()


class ApprovedSourceGenerationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "generation.db"
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

    def create_source(self, status: str, title: str):
        sections = {
            definition.key: f"{title} trusted content for {definition.label}."
            for definition in document_template(DocumentType.PRD)
        }
        return create_document(
            {
                "product_id": self.product.id,
                "document_type": DocumentType.PRD,
                "title": title,
                "version": "1.0",
                "document_status": status,
                "sections": sections,
            },
            self.database_path,
        )

    def test_generation_uses_only_approved_sources_and_never_modifies_documents(self):
        approved = self.create_source("approved", "Approved PRD")
        draft = self.create_source("draft", "Draft PRD")
        approved_before = get_document(approved.id, self.database_path)
        draft_before = get_document(draft.id, self.database_path)

        class FakeAIService:
            def __init__(inner_self):
                inner_self.prompts = []

            def create_embeddings(inner_self, texts):
                return [(1.0, 0.0) for _ in texts]

            def create_text_response(inner_self, input_text, *, instructions=None):
                inner_self.prompts.append((input_text, instructions))
                return "Generated review draft [Source 1]"

        fake_ai = FakeAIService()
        result = DatabaseGroundedGenerationService(
            fake_ai,
            self.database_path,
        ).generate("Draft a product review", limit=50)

        self.assertTrue(result.grounded)
        self.assertEqual(
            {citation.document_id for citation in result.citations},
            {approved.id},
        )
        prompt = fake_ai.prompts[0][0]
        self.assertIn("Approved PRD trusted content", prompt)
        self.assertNotIn("Draft PRD trusted content", prompt)
        self.assertEqual(get_document(approved.id, self.database_path), approved_before)
        self.assertEqual(get_document(draft.id, self.database_path), draft_before)
        self.assertFalse(result.can_save)
        self.assertFalse(result.explicitly_accepted)

    def test_explicit_temp_database_path_prevents_live_database_access(self):
        fake_ai = Mock()
        with patch(
            "src.grounded_generation.retrieve_approved_sources",
            return_value=retrieval_result(
                state=SemanticRetrievalState.NO_APPROVED_SOURCES
            ),
        ) as retrieve:
            DatabaseGroundedGenerationService(
                fake_ai,
                self.database_path,
            ).generate("Draft a summary")

        self.assertEqual(retrieve.call_args.args[2], self.database_path)
        self.assertNotEqual(self.database_path, Path("data/pmc.db"))
        fake_ai.create_text_response.assert_not_called()


if __name__ == "__main__":
    unittest.main()
