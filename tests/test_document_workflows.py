"""Streamlit workflow tests for Phase 8 product documents."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_product_detail_path_uses_prepopulation_and_opens_preview(self):
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


class PrimaryDocumentNavigationTestCase(unittest.TestCase):
    create_products = True

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = (
            Path(self.temporary_directory.name) / "primary-navigation.db"
        )
        initialize_database(self.database_path)

        self.first_product = None
        self.second_product = None
        if self.create_products:
            first_data = product_data()
            first_data.update(
                description="First product description.",
                target_users="First product users",
                business_goal="First product goal.",
                customer_problem="First product problem.",
            )
            second_data = product_data()
            second_data.update(
                description="Second product description.",
                target_users="Second product users",
                business_goal="Second product goal.",
                customer_problem="Second product problem.",
            )
            self.first_product = create_product(first_data, self.database_path)
            self.second_product = create_product(second_data, self.database_path)

        original = os.environ.get("PMC_DATABASE_FILE")
        os.environ["PMC_DATABASE_FILE"] = str(self.database_path)

        def restore_environment() -> None:
            if original is None:
                os.environ.pop("PMC_DATABASE_FILE", None)
            else:
                os.environ["PMC_DATABASE_FILE"] = original

        self.addCleanup(restore_environment)
        self.app = AppTest.from_file(APP_FILE, default_timeout=5).run()
        self.assertEqual(list(self.app.exception), [])

    def open_navigation(self, label: str) -> None:
        self.app.radio[0].set_value(label).run()
        self.assertEqual(list(self.app.exception), [])


class PrimaryDocumentNavigationTests(PrimaryDocumentNavigationTestCase):
    def test_sidebar_order_and_intentional_product_selection(self):
        self.assertEqual(
            self.app.radio[0].options,
            [
                "Dashboard",
                "Create Product",
                "Create PRD",
                "Create BRD",
                "AI Assistant",
                "View Products",
                "Search Products",
            ],
        )

        for label, key in (
            ("Create PRD", "primary_create_prd_product_selector"),
            ("Create BRD", "primary_create_brd_product_selector"),
        ):
            with self.subTest(label=label):
                self.open_navigation(label)
                selector = self.app.selectbox(key=key)
                self.assertIsNone(selector.value)
                self.assertEqual(selector.options[0], "Select a product")
                self.assertEqual(len(self.app.text_input), 0)
                self.assertNotIn(
                    "Save document",
                    [button.label for button in self.app.button],
                )

    def test_ai_assistant_missing_configuration_never_constructs_live_client(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), patch(
            "src.ai_service._create_official_client"
        ) as client_factory:
            self.open_navigation("AI Assistant")
            self.app.text_area(key="grounded_generation_request").set_value(
                "Draft a product summary."
            )
            self.app.button(
                key="FormSubmitter:grounded_generation_form-Generate draft"
            ).click().run()

        self.assertEqual(list(self.app.exception), [])
        client_factory.assert_not_called()
        self.assertTrue(
            any("currently inactive" in message.value for message in self.app.error)
        )
        self.assertNotIn("Save", [button.label for button in self.app.button])

    def test_duplicate_names_use_id_labels_and_selected_prd_association(self):
        self.open_navigation("Create PRD")
        selector = self.app.selectbox(
            key="primary_create_prd_product_selector"
        )
        self.assertIn(
            f"Document Product · Planning · ID {self.first_product.id}",
            selector.options,
        )
        self.assertIn(
            f"Document Product · Planning · ID {self.second_product.id}",
            selector.options,
        )

        selector.set_value(self.second_product.id).run()
        prefix = "primary_create_prd_document_form_new_PRD"
        self.assertEqual(
            self.app.text_input(key=f"{prefix}_title").value,
            "Document Product PRD",
        )
        self.assertEqual(
            self.app.text_area(key=f"{prefix}_section_product_overview").value,
            self.second_product.description,
        )
        self.assertEqual(
            self.app.text_area(
                key=f"{prefix}_section_target_users_personas"
            ).value,
            self.second_product.target_users,
        )
        self.app.button(key=f"FormSubmitter:{prefix}-Save document").click().run()

        documents = list_documents_for_product(
            self.second_product.id,
            self.database_path,
        )
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].product_id, self.second_product.id)
        self.assertIs(documents[0].document_type, DocumentType.PRD)
        self.assertEqual(
            list_documents_for_product(
                self.first_product.id,
                self.database_path,
            ),
            [],
        )

    def test_brd_navigation_prepopulation_preview_and_stable_id_edit(self):
        self.open_navigation("Create BRD")
        self.app.selectbox(
            key="primary_create_brd_product_selector"
        ).set_value(self.first_product.id).run()
        prefix = "primary_create_brd_document_form_new_BRD"
        self.assertEqual(
            self.app.text_area(key=f"{prefix}_section_executive_summary").value,
            self.first_product.description,
        )
        self.assertEqual(
            self.app.text_area(key=f"{prefix}_section_business_problem").value,
            self.first_product.customer_problem,
        )
        self.assertEqual(
            self.app.text_area(key=f"{prefix}_section_business_objectives").value,
            self.first_product.business_goal,
        )
        self.app.button(key=f"FormSubmitter:{prefix}-Save document").click().run()

        document = list_documents_for_product(
            self.first_product.id,
            self.database_path,
        )[0]
        self.assertIs(document.document_type, DocumentType.BRD)
        preview = "\n".join(element.value for element in self.app.markdown)
        self.assertIn("### Executive summary", preview)

        self.app.button(
            key=f"primary_create_brd_edit_document_{document.id}"
        ).click().run()
        edit_prefix = (
            f"primary_create_brd_document_form_{document.id}_BRD"
        )
        self.app.text_input(key=f"{edit_prefix}_title").set_value("Edited BRD")
        self.app.button(
            key=f"FormSubmitter:{edit_prefix}-Save document"
        ).click().run()

        updated = get_document(document.id, self.database_path)
        self.assertEqual(updated.id, document.id)
        self.assertEqual(updated.title, "Edited BRD")
        self.assertEqual(updated.product_id, self.first_product.id)

    def test_cancel_returns_to_selector_and_prd_brd_state_is_isolated(self):
        self.open_navigation("Create PRD")
        self.app.selectbox(
            key="primary_create_prd_product_selector"
        ).set_value(self.first_product.id).run()
        prd_prefix = "primary_create_prd_document_form_new_PRD"
        self.app.text_input(key=f"{prd_prefix}_title").set_value(
            "Unsaved PRD title"
        )

        self.open_navigation("Create BRD")
        brd_selector = self.app.selectbox(
            key="primary_create_brd_product_selector"
        )
        self.assertIsNone(brd_selector.value)
        brd_selector.set_value(self.second_product.id).run()
        brd_prefix = "primary_create_brd_document_form_new_BRD"
        self.assertEqual(
            self.app.text_input(key=f"{brd_prefix}_title").value,
            "Document Product BRD",
        )

        self.app.button(key=f"FormSubmitter:{brd_prefix}-Cancel").click().run()

        self.assertIsNone(
            self.app.selectbox(
                key="primary_create_brd_product_selector"
            ).value
        )
        self.assertEqual(
            list_documents_for_product(
                self.second_product.id,
                self.database_path,
            ),
            [],
        )

    def test_selected_product_that_disappears_uses_safe_message(self):
        self.open_navigation("Create PRD")

        with patch("src.database.get_product", return_value=None):
            self.app.selectbox(
                key="primary_create_prd_product_selector"
            ).set_value(self.first_product.id).run()

        self.assertIn(
            "The associated product no longer exists.",
            [message.value for message in self.app.warning],
        )


class EmptyPrimaryDocumentNavigationTests(PrimaryDocumentNavigationTestCase):
    create_products = False

    def test_empty_state_guidance_and_go_to_create_product(self):
        for label in ("Create PRD", "Create BRD"):
            with self.subTest(label=label):
                self.open_navigation(label)
                self.assertIn(
                    "A product must be created before you can create a BRD or PRD.",
                    [message.value for message in self.app.info],
                )
                self.assertEqual(len(self.app.selectbox), 0)
                self.assertEqual(len(self.app.text_input), 0)
                self.assertNotIn(
                    "Save document",
                    [button.label for button in self.app.button],
                )

        self.open_navigation("Create PRD")
        self.app.button(key="primary_create_prd_go_to_create_product").click().run()

        self.assertEqual(self.app.radio[0].value, "Create Product")
        self.assertIn(
            "Capture the essential context for a product.",
            "\n".join(element.value for element in self.app.markdown),
        )


if __name__ == "__main__":
    unittest.main()
