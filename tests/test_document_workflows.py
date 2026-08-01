"""Streamlit workflow tests for Phase 8 product documents."""

import os
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.database import (
    create_document,
    create_product,
    get_document,
    initialize_database,
    list_documents_for_product,
)
from src.document_templates import document_template
from src.models import DocumentStatus, DocumentType


APP_FILE = Path(__file__).resolve().parents[1] / "app.py"


def product_data() -> dict[str, object]:
    return {
        "name": "Document Product",
        "description": "A product overview from the saved record.",
        "target_users": "Product teams",
        "business_goal": "Improve requirements quality.",
        "status": "planning",
        "customer_problem": "Requirements are inconsistent.",
    }


def document_data(
    product_id: int,
    document_type: DocumentType,
) -> dict[str, object]:
    return {
        "product_id": product_id,
        "document_type": document_type,
        "title": f"Saved {document_type.value}",
        "version": "1.0",
        "document_status": "draft",
        "sections": {
            section.key: "" for section in document_template(document_type)
        },
    }


class DocumentWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "ui-documents.db"
        initialize_database(self.database_path)
        self.product = create_product(product_data(), self.database_path)

        original = os.environ.get("PMC_DATABASE_FILE")
        os.environ["PMC_DATABASE_FILE"] = str(self.database_path)

        def restore_environment() -> None:
            if original is None:
                os.environ.pop("PMC_DATABASE_FILE", None)
            else:
                os.environ["PMC_DATABASE_FILE"] = original

        self.addCleanup(restore_environment)
        self.app = AppTest.from_file(APP_FILE, default_timeout=5).run()
        self.app.radio[0].set_value("View Products").run()
        self.assertEqual(list(self.app.exception), [])

    def open_new_document_form(
        self,
        document_type: DocumentType = DocumentType.BRD,
    ) -> str:
        self.app.button(
            key=f"view_product_selector_create_document_{self.product.id}"
        ).click().run()
        self.app.radio(key="view_product_selector_new_document_type").set_value(
            document_type
        )
        self.app.button(key="view_product_selector_continue_document").click().run()
        self.assertEqual(list(self.app.exception), [])
        return f"view_product_selector_document_form_new_{document_type.value}"

    def test_create_draft_uses_prepopulation_and_opens_preview(self):
        prefix = self.open_new_document_form(DocumentType.BRD)

        self.assertEqual(
            self.app.text_input(key=f"{prefix}_title").value,
            "Document Product BRD",
        )
        self.assertEqual(
            self.app.text_area(key=f"{prefix}_section_executive_summary").value,
            self.product.description,
        )
        self.assertEqual(
            self.app.text_area(key=f"{prefix}_section_business_problem").value,
            self.product.customer_problem,
        )
        self.assertEqual(
            self.app.text_area(key=f"{prefix}_section_stakeholders").value,
            "",
        )

        self.app.button(key=f"FormSubmitter:{prefix}-Save document").click().run()

        documents = list_documents_for_product(self.product.id, self.database_path)
        self.assertEqual(len(documents), 1)
        self.assertIs(documents[0].document_status, DocumentStatus.DRAFT)
        preview = "\n".join(element.value for element in self.app.markdown)
        self.assertIn("### Executive summary", preview)
        self.assertIn("### Approval criteria", preview)

    def test_approved_form_identifies_incomplete_sections(self):
        prefix = self.open_new_document_form(DocumentType.PRD)
        self.app.selectbox(key=f"{prefix}_status").set_value(
            DocumentStatus.APPROVED
        )

        self.app.button(key=f"FormSubmitter:{prefix}-Save document").click().run()

        self.assertEqual(
            list_documents_for_product(self.product.id, self.database_path),
            [],
        )
        rendered = "\n".join(element.value for element in self.app.markdown)
        self.assertIn("Non-goals is required before approval.", rendered)
        self.assertIn("Acceptance criteria is required before approval.", rendered)

    def test_complete_approved_prd_can_be_created(self):
        prefix = self.open_new_document_form(DocumentType.PRD)
        self.app.selectbox(key=f"{prefix}_status").set_value(
            DocumentStatus.APPROVED
        )
        for definition in document_template(DocumentType.PRD):
            self.app.text_area(
                key=f"{prefix}_section_{definition.key}"
            ).set_value(f"Completed {definition.label}")

        self.app.button(key=f"FormSubmitter:{prefix}-Save document").click().run()

        documents = list_documents_for_product(self.product.id, self.database_path)
        self.assertEqual(len(documents), 1)
        self.assertIs(documents[0].document_status, DocumentStatus.APPROVED)
        self.assertIs(documents[0].document_type, DocumentType.PRD)

    def test_edit_updates_by_stable_document_id(self):
        saved = create_document(
            document_data(self.product.id, DocumentType.PRD),
            self.database_path,
        )
        self.app.run()
        self.app.selectbox(key="view_product_selector_document_selector").set_value(
            saved.id
        )
        self.app.button(key="view_product_selector_preview_document").click().run()
        self.app.button(
            key=f"view_product_selector_edit_document_{saved.id}"
        ).click().run()
        prefix = f"view_product_selector_document_form_{saved.id}_PRD"
        self.app.text_input(key=f"{prefix}_title").set_value("Edited PRD")
        self.app.text_input(key=f"{prefix}_version").set_value("2026-Q3")
        self.app.text_area(key=f"{prefix}_section_product_overview").set_value(
            "Edited overview"
        )

        self.app.button(key=f"FormSubmitter:{prefix}-Save document").click().run()

        updated = get_document(saved.id, self.database_path)
        self.assertEqual(updated.id, saved.id)
        self.assertEqual(updated.title, "Edited PRD")
        self.assertEqual(updated.version, "2026-Q3")
        self.assertEqual(updated.sections["product_overview"], "Edited overview")

    def test_multiple_documents_are_listed_for_the_product(self):
        first = create_document(
            document_data(self.product.id, DocumentType.BRD),
            self.database_path,
        )
        second = create_document(
            document_data(self.product.id, DocumentType.PRD),
            self.database_path,
        )

        self.app.run()

        self.assertEqual(
            self.app.selectbox(key="view_product_selector_document_selector").options,
            [
                f"Saved PRD · PRD · Version 1.0 · ID {second.id}",
                f"Saved BRD · BRD · Version 1.0 · ID {first.id}",
            ],
        )
        captions = [caption.value for caption in self.app.caption]
        self.assertIn("2 documents associated with this product", captions)

    def test_product_delete_warning_reports_cascading_document_count(self):
        create_document(
            document_data(self.product.id, DocumentType.BRD),
            self.database_path,
        )
        create_document(
            document_data(self.product.id, DocumentType.PRD),
            self.database_path,
        )
        self.app.run()

        self.app.button(
            key=f"view_product_selector_delete_action_{self.product.id}"
        ).click().run()

        warning = "\n".join(message.value for message in self.app.warning)
        self.assertIn("permanently delete 2 associated documents", warning)

    def test_saved_document_persists_in_a_fresh_app_session(self):
        saved = create_document(
            document_data(self.product.id, DocumentType.BRD),
            self.database_path,
        )

        fresh_app = AppTest.from_file(APP_FILE, default_timeout=5).run()
        fresh_app.radio[0].set_value("View Products").run()

        self.assertEqual(list(fresh_app.exception), [])
        self.assertIn(
            f"Saved BRD · BRD · Version 1.0 · ID {saved.id}",
            fresh_app.selectbox(
                key="view_product_selector_document_selector"
            ).options,
        )


if __name__ == "__main__":
    unittest.main()
