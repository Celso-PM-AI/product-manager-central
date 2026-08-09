"""Deterministic Phase 10 Checkpoint 2 onboarding and history tests."""

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
    list_generated_artifacts_for_product,
    list_products,
    list_retrievable_document_sections,
    save_accepted_generated_artifact,
)
from src.document_templates import document_template
from src.models import DocumentStatus, DocumentType
from src.sample_data import (
    SAMPLE_APPROVED_PRD_TITLE,
    SAMPLE_DRAFT_BRD_TITLE,
    SAMPLE_LOADING_NOTE,
    SAMPLE_PRODUCT_NAME,
    SAMPLE_READY_NOTE,
    SampleDataLoadStatus,
    load_fictional_sample_data,
)


APP_FILE = Path(__file__).resolve().parents[1] / "app.py"


def _product_data(name: str) -> dict[str, object]:
    return {
        "name": name,
        "description": "Existing user-created product context.",
        "target_users": "Product managers",
        "business_goal": "Preserve existing data during onboarding.",
        "status": "planning",
        "notes": "User-authored notes must remain unchanged.",
    }


def _approved_document_data(product_id: int) -> dict[str, object]:
    return {
        "product_id": product_id,
        "document_type": DocumentType.PRD,
        "title": "User-authored Approved PRD",
        "version": "1.0",
        "document_status": DocumentStatus.APPROVED,
        "sections": {
            section.key: f"User-authored evidence for {section.label}."
            for section in document_template(DocumentType.PRD)
        },
    }


class TemporaryCheckpoint2TestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "checkpoint2.db"
        initialize_database(self.database_path)

        original_database = os.environ.get("PMC_DATABASE_FILE")
        original_key = os.environ.get("OPENAI_API_KEY")
        os.environ["PMC_DATABASE_FILE"] = str(self.database_path)
        os.environ.pop("OPENAI_API_KEY", None)

        def restore_environment() -> None:
            if original_database is None:
                os.environ.pop("PMC_DATABASE_FILE", None)
            else:
                os.environ["PMC_DATABASE_FILE"] = original_database
            if original_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = original_key

        self.addCleanup(restore_environment)

    @staticmethod
    def rendered_text(app: AppTest) -> str:
        collections = (
            app.subheader,
            app.markdown,
            app.caption,
            app.info,
            app.success,
            app.warning,
            app.error,
        )
        return "\n".join(
            str(element.value)
            for collection in collections
            for element in collection
        )


class FictionalSampleDataTests(TemporaryCheckpoint2TestCase):
    def test_application_start_does_not_load_sample_or_call_openai(self):
        with patch("src.ai_service.OpenAIService.from_environment") as openai:
            app = AppTest.from_file(APP_FILE).run()

        self.assertEqual(list(app.exception), [])
        self.assertEqual(list_products(self.database_path), [])
        openai.assert_not_called()
        self.assertIn(
            "Load fictional sample data",
            [button.label for button in app.button],
        )

    def test_explicit_load_creates_identified_product_and_document_states(self):
        result = load_fictional_sample_data(self.database_path)

        self.assertIs(result.status, SampleDataLoadStatus.CREATED)
        self.assertEqual(result.product.name, SAMPLE_PRODUCT_NAME)
        self.assertEqual(result.product.notes, SAMPLE_READY_NOTE)
        documents = list_documents_for_product(
            result.product.id,
            self.database_path,
        )
        self.assertEqual(len(documents), 2)
        by_title = {document.title: document for document in documents}
        self.assertIs(
            by_title[SAMPLE_APPROVED_PRD_TITLE].document_status,
            DocumentStatus.APPROVED,
        )
        self.assertIs(
            by_title[SAMPLE_DRAFT_BRD_TITLE].document_status,
            DocumentStatus.DRAFT,
        )
        self.assertTrue(
            all("Fictional Sample" in document.title for document in documents)
        )

    def test_repeat_load_is_idempotent_and_deterministic(self):
        first = load_fictional_sample_data(self.database_path)
        first_documents = list_documents_for_product(
            first.product.id,
            self.database_path,
        )

        second = load_fictional_sample_data(self.database_path)

        self.assertIs(second.status, SampleDataLoadStatus.ALREADY_LOADED)
        self.assertEqual(second.product, first.product)
        self.assertEqual(list_products(self.database_path), [first.product])
        self.assertEqual(
            list_documents_for_product(first.product.id, self.database_path),
            first_documents,
        )

    def test_interrupted_product_only_load_is_completed_without_duplicate(self):
        partial = create_product(
            {
                **_product_data(SAMPLE_PRODUCT_NAME),
                "notes": SAMPLE_LOADING_NOTE,
            },
            self.database_path,
        )

        result = load_fictional_sample_data(self.database_path)

        self.assertIs(result.status, SampleDataLoadStatus.CREATED)
        self.assertEqual(result.product.id, partial.id)
        self.assertEqual(result.product.notes, SAMPLE_READY_NOTE)
        self.assertEqual(len(list_products(self.database_path)), 1)
        self.assertEqual(
            len(list_documents_for_product(partial.id, self.database_path)),
            2,
        )

    def test_loading_sample_preserves_existing_user_product_and_document(self):
        existing = create_product(_product_data("User Product"), self.database_path)
        existing_document = create_document(
            _approved_document_data(existing.id),
            self.database_path,
        )
        product_before = list_products(self.database_path)
        document_before = get_document(existing_document.id, self.database_path)

        sample = load_fictional_sample_data(self.database_path)

        self.assertEqual(get_document(existing_document.id, self.database_path), document_before)
        self.assertIn(existing, list_products(self.database_path))
        self.assertEqual(product_before, [existing])
        self.assertNotEqual(sample.product.id, existing.id)

    def test_only_approved_fictional_document_is_retrieval_eligible(self):
        sample = load_fictional_sample_data(self.database_path)
        documents = list_documents_for_product(sample.product.id, self.database_path)
        by_title = {document.title: document for document in documents}

        sections = list_retrievable_document_sections(self.database_path)
        retrieved_ids = {section.document_id for section in sections}

        self.assertIn(by_title[SAMPLE_APPROVED_PRD_TITLE].id, retrieved_ids)
        self.assertNotIn(by_title[SAMPLE_DRAFT_BRD_TITLE].id, retrieved_ids)
        self.assertTrue(
            all(section.document_status is DocumentStatus.APPROVED for section in sections)
        )

    def test_dashboard_explains_required_onboarding_concepts(self):
        app = AppTest.from_file(APP_FILE).run()

        self.assertEqual(list(app.exception), [])
        content = self.rendered_text(app)
        for required in (
            "Getting Started",
            "runs on your computer",
            "Create a product",
            "Create a BRD or PRD",
            "Draft documents are excluded",
            "trusted sources",
            "citations",
            "Accept, revise, or reject",
            "never edits or overwrites",
            "your own OpenAI API key",
            "commit one to Git",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_dashboard_load_action_reports_success_then_already_loaded(self):
        with patch("src.ai_service.OpenAIService.from_environment") as openai:
            app = AppTest.from_file(APP_FILE).run()
            app.button(key="load_fictional_sample_data").click().run()
            self.assertIn("was loaded", self.rendered_text(app))
            app.button(key="load_fictional_sample_data").click().run()

        self.assertEqual(list(app.exception), [])
        self.assertIn("already loaded", self.rendered_text(app))
        self.assertEqual(len(list_products(self.database_path)), 1)
        openai.assert_not_called()

    def test_dashboard_sample_failure_is_safe_and_non_sensitive(self):
        with patch(
            "src.sample_data.load_fictional_sample_data",
            side_effect=RuntimeError("sensitive internal path and token"),
        ):
            app = AppTest.from_file(APP_FILE).run()
            app.button(key="load_fictional_sample_data").click().run()

        content = self.rendered_text(app)
        self.assertEqual(list(app.exception), [])
        self.assertIn("could not be loaded safely", content)
        self.assertNotIn("sensitive internal path", content)
        self.assertNotIn("token", content)
        self.assertEqual(list_products(self.database_path), [])


class AcceptedArtifactHistoryTests(TemporaryCheckpoint2TestCase):
    def setUp(self):
        super().setUp()
        self.product = create_product(
            _product_data("History Product"),
            self.database_path,
        )
        self.document = create_document(
            _approved_document_data(self.product.id),
            self.database_path,
        )

    def open_product_detail(self) -> AppTest:
        app = AppTest.from_file(APP_FILE).run()
        app.radio[0].set_value("View Products").run()
        self.assertEqual(list(app.exception), [])
        return app

    def save_artifact(self) -> None:
        save_accepted_generated_artifact(
            acceptance_key="checkpoint2-history-artifact",
            product_id=self.product.id,
            request="Draft a fictional launch summary.",
            original_content="Original grounded draft [Source 1]",
            accepted_content="Human-revised accepted summary [Source 1]",
            citations=(
                {
                    "source_number": 1,
                    "source_product_id": self.product.id,
                    "source_product_name": self.product.name,
                    "document_id": self.document.id,
                    "document_title": self.document.title,
                    "document_type": self.document.document_type,
                    "section_key": "product_overview",
                    "section_title": "Product overview",
                },
            ),
            database_path=self.database_path,
        )

    def test_product_without_accepted_artifacts_has_clear_empty_state(self):
        app = self.open_product_detail()

        self.assertIn(
            "No accepted AI-generated artifacts for this product yet",
            self.rendered_text(app),
        )

    def test_history_shows_product_content_dates_and_complete_citation_read_only(self):
        self.save_artifact()
        source_before = get_document(self.document.id, self.database_path)

        with patch("src.ai_service.OpenAIService.from_environment") as openai:
            app = self.open_product_detail()

        content = self.rendered_text(app)
        for required in (
            "Accepted AI-generated artifacts",
            "Read-only history",
            "History Product",
            "Draft a fictional launch summary.",
            "Human-revised accepted summary [Source 1]",
            "Original grounded draft [Source 1]",
            "User-authored Approved PRD",
            "document ID",
            "PRD",
            "Product overview",
            "Accepted:",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)
        labels = {button.label for button in app.button}
        self.assertNotIn("Edit artifact", labels)
        self.assertNotIn("Delete artifact", labels)
        self.assertNotIn("Regenerate artifact", labels)
        self.assertEqual(get_document(self.document.id, self.database_path), source_before)
        self.assertEqual(
            len(
                list_generated_artifacts_for_product(
                    self.product.id,
                    self.database_path,
                )
            ),
            1,
        )
        openai.assert_not_called()


if __name__ == "__main__":
    unittest.main()
