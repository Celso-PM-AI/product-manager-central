"""Isolated migration and persistence tests for Phase 8 documents."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from src.database import (
    SCHEMA_CANONICAL,
    SCHEMA_PRODUCT_ONLY,
    DocumentAssociationError,
    DocumentValidationError,
    count_documents_for_product,
    create_document,
    create_product,
    delete_product,
    detect_database_schema,
    get_document,
    get_product,
    initialize_database,
    list_documents_for_product,
    migrate_document_database,
    update_document,
    update_product,
)
from src.document_templates import document_template
from src.models import DocumentStatus, DocumentType


def product_data(name: str = "Atlas") -> dict[str, object]:
    return {
        "name": name,
        "description": "Portfolio planning workspace.",
        "target_users": "Product leaders",
        "business_goal": "Improve portfolio decisions.",
        "status": "planning",
        "customer_problem": "Evidence is fragmented.",
    }


def document_data(
    product_id: int,
    document_type: DocumentType = DocumentType.BRD,
    **overrides: object,
) -> dict[str, object]:
    data: dict[str, object] = {
        "product_id": product_id,
        "document_type": document_type,
        "title": f"Atlas {document_type.value}",
        "version": "1.0",
        "document_status": "draft",
        "sections": {
            section.key: "" for section in document_template(document_type)
        },
    }
    data.update(overrides)
    return data


class TemporaryDocumentDatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "documents.db"
        initialize_database(self.database_path)
        self.product = create_product(product_data(), self.database_path)


class DocumentMigrationTests(TemporaryDocumentDatabaseTestCase):
    def _remove_document_schema(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute("DROP TABLE document_sections")
            connection.execute("DROP TABLE documents")

    def test_additive_migration_preserves_every_product_value(self):
        before = get_product(self.product.id, self.database_path)
        self._remove_document_schema()
        self.assertEqual(detect_database_schema(self.database_path), SCHEMA_PRODUCT_ONLY)

        self.assertTrue(migrate_document_database(self.database_path))

        self.assertEqual(detect_database_schema(self.database_path), SCHEMA_CANONICAL)
        self.assertEqual(get_product(self.product.id, self.database_path), before)
        self.assertFalse(migrate_document_database(self.database_path))

    def test_initialize_performs_backward_compatible_additive_migration(self):
        self._remove_document_schema()

        initialize_database(self.database_path)

        self.assertEqual(detect_database_schema(self.database_path), SCHEMA_CANONICAL)
        self.assertEqual(get_product(self.product.id, self.database_path), self.product)

    def test_failed_additive_migration_rolls_back_all_new_tables(self):
        self._remove_document_schema()

        def partially_create_then_fail(connection: sqlite3.Connection) -> None:
            connection.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY)")
            raise RuntimeError("simulated migration failure")

        with patch(
            "src.database._create_document_tables",
            side_effect=partially_create_then_fail,
        ):
            with self.assertRaises(RuntimeError):
                migrate_document_database(self.database_path)

        self.assertEqual(
            detect_database_schema(self.database_path),
            SCHEMA_PRODUCT_ONLY,
        )
        self.assertEqual(get_product(self.product.id, self.database_path), self.product)

    def test_document_index_and_foreign_keys_exist(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            index_names = {
                row[1] for row in connection.execute("PRAGMA index_list(documents)")
            }
            foreign_keys = connection.execute("PRAGMA foreign_key_list(documents)").fetchall()

        self.assertIn("idx_documents_product_id", index_names)
        self.assertEqual(foreign_keys[0][2], "products")
        self.assertEqual(foreign_keys[0][6].upper(), "CASCADE")


class DocumentPersistenceTests(TemporaryDocumentDatabaseTestCase):
    def test_brd_creation_and_retrieval(self):
        created = create_document(document_data(self.product.id), self.database_path)

        self.assertEqual(get_document(created.id, self.database_path), created)
        self.assertIs(created.document_type, DocumentType.BRD)
        self.assertIs(created.document_status, DocumentStatus.DRAFT)
        self.assertEqual(created.created_at, created.updated_at)

    def test_prd_creation_and_retrieval(self):
        created = create_document(
            document_data(self.product.id, DocumentType.PRD),
            self.database_path,
        )

        self.assertIs(created.document_type, DocumentType.PRD)
        self.assertEqual(
            set(created.sections),
            {section.key for section in document_template(DocumentType.PRD)},
        )

    def test_product_association_and_multiple_documents(self):
        first = create_document(document_data(self.product.id), self.database_path)
        second = create_document(
            document_data(self.product.id, DocumentType.PRD),
            self.database_path,
        )
        other_product = create_product(product_data("Beacon"), self.database_path)
        other = create_document(document_data(other_product.id), self.database_path)

        self.assertEqual(
            [
                document.id
                for document in list_documents_for_product(
                    self.product.id,
                    self.database_path,
                )
            ],
            [second.id, first.id],
        )
        self.assertEqual(
            [
                document.id
                for document in list_documents_for_product(
                    other_product.id,
                    self.database_path,
                )
            ],
            [other.id],
        )
        self.assertEqual(
            count_documents_for_product(self.product.id, self.database_path),
            2,
        )

    def test_missing_product_association_is_rejected(self):
        with self.assertRaises(DocumentAssociationError):
            create_document(document_data(999), self.database_path)

        self.assertEqual(
            list_documents_for_product(999, self.database_path),
            [],
        )

    def test_stable_id_update_preserves_association_type_and_creation_time(self):
        with patch(
            "src.database._utc_now",
            return_value="2026-08-01T10:00:00.000000Z",
        ):
            original = create_document(document_data(self.product.id), self.database_path)
        sections = dict(original.sections)
        sections["executive_summary"] = "Updated summary"

        with patch(
            "src.database._utc_now",
            return_value="2026-08-02T10:00:00.000000Z",
        ):
            updated = update_document(
                original.id,
                {
                    "title": "Updated BRD",
                    "version": "Release candidate",
                    "document_status": "draft",
                    "sections": sections,
                },
                self.database_path,
            )

        self.assertEqual(updated.id, original.id)
        self.assertEqual(updated.product_id, original.product_id)
        self.assertIs(updated.document_type, original.document_type)
        self.assertEqual(updated.created_at, original.created_at)
        self.assertEqual(updated.updated_at, "2026-08-02T10:00:00.000000Z")
        self.assertEqual(updated.version, "Release candidate")
        self.assertEqual(updated.sections["executive_summary"], "Updated summary")

    def test_approved_update_requires_all_sections_and_is_atomic(self):
        original = create_document(document_data(self.product.id), self.database_path)

        with self.assertRaises(DocumentValidationError):
            update_document(
                original.id,
                {"document_status": "approved"},
                self.database_path,
            )

        self.assertEqual(get_document(original.id, self.database_path), original)

    def test_complete_document_can_be_approved(self):
        original = create_document(document_data(self.product.id), self.database_path)
        complete_sections = {
            section.key: f"Complete {section.label}"
            for section in document_template(DocumentType.BRD)
        }

        updated = update_document(
            original.id,
            {"document_status": "approved", "sections": complete_sections},
            self.database_path,
        )

        self.assertIs(updated.document_status, DocumentStatus.APPROVED)

    def test_saved_prepopulation_snapshot_does_not_follow_product_edits(self):
        sections = document_data(self.product.id)["sections"]
        sections["executive_summary"] = self.product.description
        document = create_document(
            document_data(self.product.id, sections=sections),
            self.database_path,
        )

        update_product(
            self.product.id,
            {"description": "A later product description."},
            self.database_path,
        )

        self.assertEqual(
            get_document(document.id, self.database_path).sections[
                "executive_summary"
            ],
            self.product.description,
        )

    def test_update_missing_id_and_immutable_fields(self):
        self.assertIsNone(update_document(999, {"title": "Missing"}, self.database_path))
        document = create_document(document_data(self.product.id), self.database_path)
        for field, value in (("product_id", 2), ("document_type", "PRD"), ("id", 3)):
            with self.subTest(field=field):
                with self.assertRaises(DocumentValidationError):
                    update_document(document.id, {field: value}, self.database_path)

    def test_product_delete_cascades_documents_and_sections(self):
        document = create_document(document_data(self.product.id), self.database_path)

        self.assertTrue(delete_product(self.product.id, self.database_path))

        self.assertIsNone(get_document(document.id, self.database_path))
        with closing(sqlite3.connect(self.database_path)) as connection:
            section_count = connection.execute(
                "SELECT COUNT(*) FROM document_sections"
            ).fetchone()[0]
        self.assertEqual(section_count, 0)


if __name__ == "__main__":
    unittest.main()
