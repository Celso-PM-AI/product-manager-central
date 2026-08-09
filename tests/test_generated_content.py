"""Tests for Phase 9 Checkpoint 4 human review and acceptance."""

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from src.database import (
    SCHEMA_CANONICAL,
    SCHEMA_DOCUMENT_ONLY,
    create_document,
    create_product,
    delete_product,
    detect_database_schema,
    get_document,
    get_product,
    initialize_database,
    list_documents_for_product,
    list_generated_artifacts_for_product,
    update_document,
)
from src.document_templates import document_template
from src.generated_content import (
    GeneratedContentReviewService,
    ReviewDecision,
    ReviewValidationError,
)
from src.grounded_generation import (
    GenerationCitation,
    GroundedGenerationResult,
    GroundedGenerationState,
)
from src.models import DocumentStatus, DocumentType


APP_FILE = Path(__file__).resolve().parents[1] / "app.py"


class GeneratedContentTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "review.db"
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
                "sections": {
                    section.key: f"Approved source for {section.label}."
                    for section in document_template(DocumentType.PRD)
                },
            },
            self.database_path,
        )
        self.generation = GroundedGenerationResult(
            state=GroundedGenerationState.GENERATED_DRAFT,
            message="Ready for review.",
            content="Original AI output [Source 1]",
            citations=(
                GenerationCitation(
                    source_number=1,
                    product_id=self.product.id,
                    product=self.product.name,
                    document_id=self.source.id,
                    document_title=self.source.title,
                    document_type=self.source.document_type,
                    section_key="product_overview",
                    section="Product overview",
                ),
            ),
            grounded=True,
        )
        self.service = GeneratedContentReviewService(
            self.database_path,
            key_factory=lambda: "stable-review-key",
        )

    def begin_review(self):
        return self.service.begin_review(
            product_id=self.product.id,
            request="Draft a product summary.",
            generation=self.generation,
        )


class ReviewAndPersistenceTests(GeneratedContentTestCase):
    def test_additive_schema_upgrade_preserves_product_and_source_documents(self):
        product_before = self.product
        source_before = get_document(self.source.id, self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute("DROP TABLE generated_artifact_citations")
            connection.execute("DROP TABLE generated_artifacts")
        self.assertEqual(
            detect_database_schema(self.database_path), SCHEMA_DOCUMENT_ONLY
        )

        initialize_database(self.database_path)

        self.assertEqual(
            detect_database_schema(self.database_path), SCHEMA_CANONICAL
        )
        self.assertEqual(get_product(self.product.id, self.database_path), product_before)
        self.assertEqual(get_document(self.source.id, self.database_path), source_before)
        self.assertEqual(source_before.product_id, product_before.id)

    def test_reviewing_does_not_save_before_explicit_acceptance(self):
        review = self.begin_review()

        self.assertIs(review.decision, ReviewDecision.PENDING)
        self.assertEqual(review.original_content, "Original AI output [Source 1]")
        self.assertEqual(review.citations[0].document_id, self.source.id)
        self.assertEqual(
            list_generated_artifacts_for_product(
                self.product.id, self.database_path
            ),
            [],
        )

    def test_accepting_unchanged_content_saves_separate_artifact_and_citations(self):
        source_before = get_document(self.source.id, self.database_path)

        accepted = self.service.accept(self.begin_review())

        self.assertTrue(accepted.created)
        self.assertIs(accepted.review.decision, ReviewDecision.ACCEPTED)
        self.assertEqual(
            accepted.artifact.accepted_content,
            accepted.artifact.original_content,
        )
        self.assertFalse(accepted.artifact.was_revised)
        self.assertEqual(accepted.artifact.product_id, self.product.id)
        self.assertEqual(accepted.artifact.citations[0].document_id, self.source.id)
        self.assertEqual(get_document(self.source.id, self.database_path), source_before)
        self.assertEqual(
            list_documents_for_product(self.product.id, self.database_path),
            [source_before],
        )

    def test_revision_stays_unsaved_until_acceptance_and_preserves_original(self):
        review = self.service.revise(
            self.begin_review(),
            "Human-revised output [Source 1]",
        )
        self.assertIs(review.decision, ReviewDecision.PENDING)
        self.assertEqual(
            list_generated_artifacts_for_product(
                self.product.id, self.database_path
            ),
            [],
        )

        accepted = self.service.accept(review).artifact

        self.assertTrue(accepted.was_revised)
        self.assertEqual(accepted.original_content, "Original AI output [Source 1]")
        self.assertEqual(
            accepted.accepted_content, "Human-revised output [Source 1]"
        )

    def test_rejection_never_creates_saved_artifact(self):
        rejected = self.service.reject(self.begin_review())

        self.assertIs(rejected.decision, ReviewDecision.REJECTED)
        self.assertEqual(
            list_generated_artifacts_for_product(
                self.product.id, self.database_path
            ),
            [],
        )
        with self.assertRaises(ReviewValidationError):
            self.service.accept(rejected)

    def test_repeated_acceptance_is_idempotent(self):
        review = self.begin_review()

        first = self.service.accept(review)
        second = self.service.accept(review)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.artifact.id, second.artifact.id)
        self.assertEqual(
            len(
                list_generated_artifacts_for_product(
                    self.product.id, self.database_path
                )
            ),
            1,
        )

    def test_empty_revision_and_ungrounded_generation_are_rejected(self):
        with self.assertRaises(ReviewValidationError):
            self.service.revise(self.begin_review(), "   ")
        ungrounded = GroundedGenerationResult(
            state=GroundedGenerationState.NO_APPROVED_SOURCES,
            message="No approved sources.",
            content=None,
            citations=(),
            grounded=False,
        )
        with self.assertRaises(ReviewValidationError):
            self.service.begin_review(
                product_id=self.product.id,
                request="Draft it",
                generation=ungrounded,
            )

    def test_source_made_draft_before_acceptance_blocks_save(self):
        review = self.begin_review()
        update_document(
            self.source.id,
            {"document_status": DocumentStatus.DRAFT},
            self.database_path,
        )

        with self.assertRaisesRegex(ReviewValidationError, "no longer an eligible"):
            self.service.accept(review)
        self.assertEqual(
            list_generated_artifacts_for_product(
                self.product.id, self.database_path
            ),
            [],
        )


class GeneratedContentWorkflowTests(GeneratedContentTestCase):
    def setUp(self):
        super().setUp()
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

    def generate_review(self, app: AppTest) -> AppTest:
        app.radio[0].set_value("AI Assistant").run()
        app.selectbox(key="grounded_generation_product_id").set_value(
            self.product.id
        )
        app.text_area(key="grounded_generation_request").set_value(
            "Draft a product summary."
        )
        app.button(
            key="FormSubmitter:grounded_generation_form-Generate draft"
        ).click().run()
        return app

    def test_review_revision_acceptance_and_rerun_save_once(self):
        with patch(
            "src.ai_service.OpenAIService.from_environment",
            return_value=Mock(),
        ), patch(
            "src.grounded_generation.DatabaseGroundedGenerationService.generate",
            return_value=self.generation,
        ):
            app = self.generate_review(AppTest.from_file(APP_FILE).run())
            self.assertEqual(list(app.exception), [])
            rendered = "\n".join(item.value for item in app.markdown)
            self.assertIn("Original AI output", rendered)
            self.assertIn("Approved Atlas PRD", rendered)
            self.assertEqual(
                list_generated_artifacts_for_product(
                    self.product.id, self.database_path
                ),
                [],
            )

            revision = next(
                area
                for area in app.text_area
                if area.label == "Revise generated content before acceptance"
            )
            revision.set_value("Reviewed human revision [Source 1]")
            app.button(
                key="FormSubmitter:generated_content_revision_form-Apply revision"
            ).click().run()
            self.assertEqual(
                list_generated_artifacts_for_product(
                    self.product.id, self.database_path
                ),
                [],
            )
            next(
                button for button in app.button if button.label == "Accept and save"
            ).click().run()

        artifacts = list_generated_artifacts_for_product(
            self.product.id, self.database_path
        )
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(
            artifacts[0].accepted_content,
            "Reviewed human revision [Source 1]",
        )
        self.assertTrue(any("explicitly accepted" in item.value for item in app.success))

    def test_reject_action_survives_rerun_without_saving(self):
        with patch(
            "src.ai_service.OpenAIService.from_environment",
            return_value=Mock(),
        ), patch(
            "src.grounded_generation.DatabaseGroundedGenerationService.generate",
            return_value=self.generation,
        ):
            app = self.generate_review(AppTest.from_file(APP_FILE).run())
            next(
                button for button in app.button if button.label == "Reject"
            ).click().run()

        self.assertEqual(list(app.exception), [])
        self.assertEqual(
            list_generated_artifacts_for_product(
                self.product.id, self.database_path
            ),
            [],
        )
        self.assertTrue(any("was rejected" in item.value for item in app.warning))

    def test_no_products_shows_empty_state_without_generation_form(self):
        delete_product(self.product.id, self.database_path)

        app = AppTest.from_file(APP_FILE).run()
        app.radio[0].set_value("AI Assistant").run()

        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any("No products are available" in item.value for item in app.info)
        )
        self.assertNotIn("Generate draft", [button.label for button in app.button])


if __name__ == "__main__":
    unittest.main()
