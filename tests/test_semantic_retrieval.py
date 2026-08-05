"""Tests for Phase 9 Checkpoint 2 chunking and semantic retrieval."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.database import (
    create_document,
    create_product,
    delete_product,
    get_document,
    initialize_database,
)
from src.document_templates import document_template
from src.models import (
    DocumentStatus,
    DocumentType,
    RetrievableDocumentSection,
)
from src.semantic_retrieval import (
    SemanticRetrievalState,
    SemanticRetriever,
    chunk_approved_sections,
    retrieve_approved_sources,
)


def source_section(
    content: str,
    *,
    document_id: int = 10,
    document_type: DocumentType = DocumentType.PRD,
    status: DocumentStatus = DocumentStatus.APPROVED,
    section_key: str = "product_overview",
    section_title: str = "Product overview",
) -> RetrievableDocumentSection:
    return RetrievableDocumentSection(
        product_id=7,
        product_name="Atlas",
        document_id=document_id,
        document_title="Atlas requirements",
        document_type=document_type,
        document_status=status,
        section_key=section_key,
        section_title=section_title,
        section_content=content,
    )


class MappingEmbeddingProvider:
    def __init__(self, vectors: dict[str, tuple[float, ...]]):
        self.vectors = vectors
        self.calls: list[list[str]] = []

    def create_embeddings(self, texts: list[str]) -> list[tuple[float, ...]]:
        self.calls.append(texts)
        return [self.vectors[text] for text in texts]


class ChunkingTests(unittest.TestCase):
    def test_chunking_is_stable_meaningful_and_preserves_metadata(self):
        section = source_section(
            "First coherent paragraph.\n\nSecond coherent paragraph."
        )

        first = chunk_approved_sections([section], max_characters=32)
        second = chunk_approved_sections([section], max_characters=32)

        self.assertEqual(first, second)
        self.assertEqual(
            [chunk.text for chunk in first],
            ["First coherent paragraph.", "Second coherent paragraph."],
        )
        self.assertTrue(all(len(chunk.text) <= 32 for chunk in first))
        chunk = first[0]
        self.assertEqual(chunk.product_id, 7)
        self.assertEqual(chunk.product_name, "Atlas")
        self.assertEqual(chunk.document_id, 10)
        self.assertEqual(chunk.document_title, "Atlas requirements")
        self.assertIs(chunk.document_type, DocumentType.PRD)
        self.assertIs(chunk.document_status, DocumentStatus.APPROVED)
        self.assertEqual(chunk.section_key, "product_overview")
        self.assertEqual(chunk.section_title, "Product overview")

    def test_chunking_defensively_excludes_unapproved_and_unsupported_sources(self):
        sections = [
            source_section("Draft", status=DocumentStatus.DRAFT),
            source_section("Approved", document_id=11),
        ]

        chunks = chunk_approved_sections(sections)

        self.assertEqual([chunk.document_id for chunk in chunks], [11])


class SemanticRankingTests(unittest.TestCase):
    def test_embedding_abstraction_ranks_results_and_applies_limit(self):
        sources = [
            source_section("Closest source", document_id=1),
            source_section("Weaker source", document_id=2),
            source_section("Unrelated source", document_id=3),
        ]
        provider = MappingEmbeddingProvider(
            {
                "portfolio question": (1.0, 0.0),
                "Closest source": (1.0, 0.0),
                "Weaker source": (0.6, 0.8),
                "Unrelated source": (0.0, 1.0),
            }
        )
        retriever = SemanticRetriever(lambda: sources, provider)

        response = retriever.retrieve(" portfolio question ", limit=2)

        self.assertIs(response.state, SemanticRetrievalState.RESULTS)
        self.assertEqual(
            [result.chunk.document_id for result in response.results],
            [1, 2],
        )
        self.assertEqual(response.results[0].similarity, 1.0)
        self.assertGreater(
            response.results[0].similarity,
            response.results[1].similarity,
        )
        self.assertEqual(
            provider.calls,
            [[
                "portfolio question",
                "Closest source",
                "Weaker source",
                "Unrelated source",
            ]],
        )

    def test_no_approved_sources_does_not_call_embedding_provider(self):
        provider = Mock()
        retriever = SemanticRetriever(lambda: [], provider)

        response = retriever.retrieve("question")

        self.assertIs(
            response.state,
            SemanticRetrievalState.NO_APPROVED_SOURCES,
        )
        self.assertEqual(response.results, ())
        self.assertIn("No approved BRD or PRD", response.message)
        provider.create_embeddings.assert_not_called()

    def test_no_relevant_results_is_explicit(self):
        sources = [source_section("Orthogonal source")]
        provider = MappingEmbeddingProvider(
            {
                "question": (1.0, 0.0),
                "Orthogonal source": (0.0, 1.0),
            }
        )
        retriever = SemanticRetriever(
            lambda: sources,
            provider,
            minimum_similarity=0.1,
        )

        response = retriever.retrieve("question")

        self.assertIs(
            response.state,
            SemanticRetrievalState.NO_RELEVANT_RESULTS,
        )
        self.assertEqual(response.results, ())
        self.assertIn("No relevant", response.message)


class SemanticRetrievalIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "semantic.db"
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
            definition.key: f"{title} {definition.label}"
            for definition in document_template(DocumentType.BRD)
        }
        return create_document(
            {
                "product_id": self.product.id,
                "document_type": DocumentType.BRD,
                "title": title,
                "version": "1.0",
                "document_status": status,
                "sections": sections,
            },
            self.database_path,
        )

    def test_only_approved_documents_are_ranked_and_sources_remain_unchanged(self):
        approved = self.create_source("approved", "Trusted")
        draft = self.create_source("draft", "Draft")
        approved_before = get_document(approved.id, self.database_path)
        draft_before = get_document(draft.id, self.database_path)

        class ConstantProvider:
            def create_embeddings(self, texts):
                return [(1.0, 0.0) for _ in texts]

        response = retrieve_approved_sources(
            "requirements",
            ConstantProvider(),
            self.database_path,
            limit=50,
        )

        self.assertTrue(response.results)
        self.assertEqual(
            {result.chunk.document_id for result in response.results},
            {approved.id},
        )
        self.assertNotIn(
            draft.id,
            {result.chunk.document_id for result in response.results},
        )
        self.assertTrue(
            all(
                result.chunk.document_status is DocumentStatus.APPROVED
                for result in response.results
            )
        )
        self.assertEqual(get_document(approved.id, self.database_path), approved_before)
        self.assertEqual(get_document(draft.id, self.database_path), draft_before)

    def test_document_unapproved_during_embedding_cannot_be_returned(self):
        approved = self.create_source("approved", "Soon unapproved")

        class UnapprovingProvider:
            def create_embeddings(inner_self, texts):
                with sqlite3.connect(self.database_path) as connection:
                    connection.execute(
                        "UPDATE documents SET document_status = 'draft' WHERE id = ?",
                        (approved.id,),
                    )
                return [(1.0, 0.0) for _ in texts]

        response = retrieve_approved_sources(
            "requirements",
            UnapprovingProvider(),
            self.database_path,
        )

        self.assertIs(
            response.state,
            SemanticRetrievalState.NO_APPROVED_SOURCES,
        )
        self.assertEqual(response.results, ())

    def test_deleted_or_missing_source_cannot_be_returned(self):
        self.create_source("approved", "Soon deleted")

        class DeletingProvider:
            def create_embeddings(inner_self, texts):
                delete_product(self.product.id, self.database_path)
                return [(1.0, 0.0) for _ in texts]

        response = retrieve_approved_sources(
            "requirements",
            DeletingProvider(),
            self.database_path,
        )

        self.assertIs(
            response.state,
            SemanticRetrievalState.NO_APPROVED_SOURCES,
        )
        self.assertEqual(response.results, ())


if __name__ == "__main__":
    unittest.main()
