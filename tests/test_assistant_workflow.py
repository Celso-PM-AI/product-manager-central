"""Streamlit tests for Checkpoint 5 prompt selection and workflow hardening."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from src.database import create_document, create_product, initialize_database, update_document
from src.document_templates import document_template
from src.models import DocumentStatus, DocumentType
from src.prompt_catalog import (
    GROUNDED_DRAFT_PROMPT_ID,
    AssistantTask,
    get_approved_prompt,
)
from tests.success_matrix_fixtures import complete_prd_agile_hierarchy, complete_success_matrix


APP_FILE = Path(__file__).resolve().parents[1] / "app.py"


class AssistantWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "assistant.db"
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
        self.source = create_document(
            {
                "product_id": self.product.id,
                "document_type": DocumentType.PRD,
                "title": "Approved Atlas PRD",
                "version": "1.0",
                "document_status": DocumentStatus.APPROVED,
                "success_matrix": complete_success_matrix(),
                "agile_hierarchy": complete_prd_agile_hierarchy("assistant"),
                "sections": {
                    section.key: f"Approved evidence for {section.label}."
                    for section in document_template(DocumentType.PRD)
                },
            },
            self.database_path,
        )
        original_database = os.environ.get("PMC_DATABASE_FILE")
        original_key = os.environ.get("OPENAI_API_KEY")
        os.environ["PMC_DATABASE_FILE"] = str(self.database_path)
        os.environ["OPENAI_API_KEY"] = "test-only-placeholder"

        def restore_environment():
            if original_database is None:
                os.environ.pop("PMC_DATABASE_FILE", None)
            else:
                os.environ["PMC_DATABASE_FILE"] = original_database
            if original_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = original_key

        self.addCleanup(restore_environment)

    def open_assistant(self) -> AppTest:
        app = AppTest.from_file(APP_FILE, default_timeout=5).run()
        app.radio[0].set_value("AI Assistant").run()
        self.assertEqual(list(app.exception), [])
        return app

    def select_valid_controls(self, app: AppTest) -> None:
        app.selectbox(key="grounded_generation_product_id").set_value(
            self.product.id
        ).run()
        app.selectbox(key="grounded_generation_task").set_value(
            AssistantTask.GROUNDED_DRAFT
        ).run()
        app.selectbox(key="grounded_generation_prompt_id").set_value(
            GROUNDED_DRAFT_PROMPT_ID
        ).run()
        app.text_area(key="grounded_generation_request").set_value(
            "Draft a product summary."
        )

    @staticmethod
    def submit(app: AppTest) -> None:
        app.button(
            key="FormSubmitter:grounded_generation_form-Generate draft"
        ).click().run()

    def test_selected_prompt_public_metadata_is_displayed(self):
        app = self.open_assistant()
        app.selectbox(key="grounded_generation_task").set_value(
            AssistantTask.GROUNDED_DRAFT
        ).run()
        prompt_selector = app.selectbox(key="grounded_generation_prompt_id")

        self.assertEqual(
            prompt_selector.options,
            ["Select an approved prompt", "Grounded product draft"],
        )
        prompt_selector.set_value(GROUNDED_DRAFT_PROMPT_ID).run()

        prompt = get_approved_prompt(
            AssistantTask.GROUNDED_DRAFT,
            GROUNDED_DRAFT_PROMPT_ID,
        )
        visible = "\n".join(
            element.value for element in [*app.markdown, *app.caption]
        )
        self.assertIn(prompt.name, visible)
        self.assertIn(prompt.description, visible)
        self.assertIn(f"Prompt version {prompt.version}", visible)
        self.assertNotIn(prompt.system_instructions, visible)

    def test_missing_product_task_prompt_or_request_stops_before_api(self):
        with patch(
            "src.ai_service.OpenAIService.from_environment",
            return_value=Mock(),
        ) as service_factory:
            app = self.open_assistant()
            app.selectbox(key="grounded_generation_task").set_value(
                AssistantTask.GROUNDED_DRAFT
            ).run()
            app.selectbox(key="grounded_generation_prompt_id").set_value(
                GROUNDED_DRAFT_PROMPT_ID
            ).run()
            app.text_area(key="grounded_generation_request").set_value("Draft it")
            self.submit(app)
            self.assertTrue(any("Select a product" in item.value for item in app.error))

            app = self.open_assistant()
            app.selectbox(key="grounded_generation_product_id").set_value(
                self.product.id
            ).run()
            app.text_area(key="grounded_generation_request").set_value("Draft it")
            self.submit(app)
            self.assertTrue(
                any("supported assistant task" in item.value for item in app.error)
            )

            app = self.open_assistant()
            app.selectbox(key="grounded_generation_product_id").set_value(
                self.product.id
            ).run()
            app.selectbox(key="grounded_generation_task").set_value(
                AssistantTask.GROUNDED_DRAFT
            ).run()
            app.text_area(key="grounded_generation_request").set_value("Draft it")
            self.submit(app)
            self.assertTrue(
                any("approved prompt" in item.value for item in app.error)
            )

            app = self.open_assistant()
            self.select_valid_controls(app)
            app.text_area(key="grounded_generation_request").set_value("   ")
            self.submit(app)
            self.assertTrue(any("Enter a request" in item.value for item in app.error))

        service_factory.assert_not_called()

    def test_missing_configuration_prevents_retrieval_or_generation(self):
        os.environ["OPENAI_API_KEY"] = ""
        with patch("src.ai_service._create_official_client") as client_factory, patch(
            "src.grounded_generation.retrieve_approved_sources"
        ) as retrieve:
            app = self.open_assistant()
            self.select_valid_controls(app)
            self.submit(app)

        self.assertEqual(list(app.exception), [])
        client_factory.assert_not_called()
        retrieve.assert_not_called()
        self.assertTrue(
            any("currently inactive" in item.value for item in app.error)
        )

    def test_no_approved_evidence_skips_embeddings_and_text_generation(self):
        update_document(
            self.source.id,
            {"document_status": DocumentStatus.DRAFT},
            self.database_path,
        )
        fake_ai = Mock()
        with patch(
            "src.ai_service.OpenAIService.from_environment",
            return_value=fake_ai,
        ):
            app = self.open_assistant()
            self.select_valid_controls(app)
            self.submit(app)

        self.assertEqual(list(app.exception), [])
        fake_ai.create_embeddings.assert_not_called()
        fake_ai.create_text_response.assert_not_called()
        self.assertTrue(
            any("No approved BRD or PRD" in item.value for item in app.warning)
        )

    def test_unexpected_failures_do_not_expose_sensitive_details(self):
        secret = "test-only-sensitive-provider-detail"
        hidden_instruction = "Use only the approved source context"
        with patch(
            "src.ai_service.OpenAIService.from_environment",
            return_value=Mock(),
        ), patch(
            "src.grounded_generation.DatabaseGroundedGenerationService.generate",
            side_effect=ValueError(f"{secret}: {hidden_instruction}"),
        ):
            app = self.open_assistant()
            self.select_valid_controls(app)
            self.submit(app)

        visible = "\n".join(
            element.value
            for element in [
                *app.error,
                *app.warning,
                *app.info,
                *app.markdown,
                *app.caption,
            ]
        )
        self.assertIn("could not be generated safely", visible)
        self.assertNotIn(secret, visible)
        self.assertNotIn(hidden_instruction, visible)


if __name__ == "__main__":
    unittest.main()
