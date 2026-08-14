"""Tests for deterministic retrieval of approved BRD and PRD sources."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.database import (
    create_document,
    create_product,
    initialize_database,
    list_retrievable_document_sections,
)
from src.document_templates import document_template
from src.models import DocumentStatus, DocumentType
from tests.success_matrix_fixtures import complete_prd_agile_hierarchy, complete_success_matrix


def complete_sections(document_type: DocumentType, prefix: str) -> dict[str, str]:
    return {
        definition.key: f"{prefix}: {definition.label}"
        for definition in document_template(document_type)
    }


class ApprovedDocumentRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "retrieval.db"
        initialize_database(self.database_path)
        self.product = create_product(
            {
                "name": "Atlas",
                "description": "Portfolio planning workspace.",
                "target_users": "Product leaders",
                "business_goal": "Improve portfolio decisions.",
                "status": "planning",
            },
            self.database_path,
        )

    def create_document(
        self,
        document_type: DocumentType,
        status: str,
        title: str,
    ):
        sections = (
            complete_sections(document_type, title)
            if status == "approved"
            else {
                definition.key: f"Draft: {definition.label}"
                for definition in document_template(document_type)
            }
        )
        return create_document(
            {
                "product_id": self.product.id,
                "document_type": document_type,
                "title": title,
                "version": "1.0",
                "document_status": status,
                "sections": sections,
                "success_matrix": (
                    complete_success_matrix()
                    if document_type is DocumentType.PRD and status in {"approved", DocumentStatus.APPROVED}
                    else []
                ),
                "agile_hierarchy": (
                    complete_prd_agile_hierarchy(f"retrieval-{title.lower().replace(' ', '-')}")
                    if document_type is DocumentType.PRD and status in {"approved", DocumentStatus.APPROVED}
                    else []
                ),
            },
            self.database_path,
        )

    def test_approved_brd_and_prd_sections_are_included_but_drafts_are_not(self):
        approved_brd = self.create_document(
            DocumentType.BRD, "approved", "Approved BRD"
        )
        approved_prd = self.create_document(
            DocumentType.PRD, "approved", "Approved PRD"
        )
        draft = self.create_document(DocumentType.BRD, "draft", "Draft BRD")

        sections = list_retrievable_document_sections(self.database_path)

        returned_ids = {section.document_id for section in sections}
        self.assertEqual(returned_ids, {approved_brd.id, approved_prd.id})
        self.assertNotIn(draft.id, returned_ids)
        self.assertEqual(
            len(sections),
            len(document_template(DocumentType.BRD))
            + len(document_template(DocumentType.PRD)),
        )

    def test_citation_metadata_and_source_content_are_returned(self):
        document = self.create_document(
            DocumentType.PRD, "approved", "Atlas Launch PRD"
        )

        sections = list_retrievable_document_sections(self.database_path)
        overview = next(
            section
            for section in sections
            if section.section_key == "product_overview"
        )

        self.assertEqual(overview.product_id, self.product.id)
        self.assertEqual(overview.product_name, "Atlas")
        self.assertEqual(overview.document_id, document.id)
        self.assertEqual(overview.document_title, "Atlas Launch PRD")
        self.assertIs(overview.document_type, DocumentType.PRD)
        self.assertIs(overview.document_status, DocumentStatus.APPROVED)
        self.assertEqual(overview.section_title, "Product overview")
        self.assertEqual(
            overview.section_content,
            "Atlas Launch PRD: Product overview",
        )

    def test_unsupported_document_type_is_excluded(self):
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute("PRAGMA ignore_check_constraints = ON")
            cursor = connection.execute(
                """
                INSERT INTO documents (
                    product_id, document_type, title, version,
                    document_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.product.id,
                    "OTHER",
                    "Unsupported source",
                    "1.0",
                    "approved",
                    "2026-08-04T00:00:00Z",
                    "2026-08-04T00:00:00Z",
                ),
            )
            connection.execute(
                """
                INSERT INTO document_sections (document_id, section_key, content)
                VALUES (?, ?, ?)
                """,
                (cursor.lastrowid, "unsupported", "Must never be retrieved."),
            )

        self.assertEqual(
            list_retrievable_document_sections(self.database_path),
            [],
        )


if __name__ == "__main__":
    unittest.main()
