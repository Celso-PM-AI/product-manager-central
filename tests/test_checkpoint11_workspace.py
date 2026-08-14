"""Focused Checkpoint 11 workspace, template, and Success Matrix tests."""

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest

from src.ai_service import OpenAIService
from src.database import (
    SCHEMA_CANONICAL,
    SCHEMA_CHECKPOINT10,
    SUCCESS_MATRIX_TABLE,
    create_document,
    create_product,
    detect_database_schema,
    get_document,
    initialize_database,
    update_document,
)
from src.document_templates import document_template
from src.agile import AgileArtifactType, PARENT_TYPE
from src.models import DocumentStatus, DocumentType, SuccessMatrixStatus
from src.validation import SUCCESS_MATRIX_REQUIRED_FIELDS, validate_document
from tests.success_matrix_fixtures import complete_prd_agile_hierarchy, complete_success_matrix
from tests import test_checkpoint10_agile_review as checkpoint10_fixtures


APP_FILE = Path(__file__).resolve().parents[1] / "app.py"


def product_data() -> dict[str, object]:
    return {
        "name": "Atlas",
        "description": "A product planning workspace.",
        "target_users": "Product teams",
        "business_goal": "Improve product decisions.",
        "status": "planning",
        "customer_problem": "Requirements are fragmented.",
    }


def document_data(
    product_id: int,
    *,
    status: DocumentStatus = DocumentStatus.DRAFT,
    matrix: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "product_id": product_id,
        "document_type": DocumentType.PRD,
        "title": "Atlas PRD",
        "version": "1.0",
        "document_status": status,
        "sections": {
            definition.key: (
                f"Approved content for {definition.label}"
                if status is DocumentStatus.APPROVED
                else ""
            )
            for definition in document_template(DocumentType.PRD)
        },
        "success_matrix": matrix or [],
        "agile_hierarchy": [],
    }


class TemplateContractTests(unittest.TestCase):
    def test_approved_group_order_and_stable_keys(self):
        expected = {
            DocumentType.PRD: (
                "1. Document Overview and Metadata",
                "2. Purpose and Objective",
                "3. Scope and Release Strategy",
                "4. Functional Requirements",
                "5. Nonfunctional Requirements",
                "6. Design and User Experience",
                "7. Success Metrics and KPIs",
                "8. Assumptions, Constraints, and Dependencies",
                "9. Timeline, Milestones, and Open Questions",
            ),
            DocumentType.BRD: (
                "1. Executive Summary and Project Overview",
                "2. Business Objectives and Goals",
                "3. Project Scope",
                "4. Stakeholders and Business Context",
                "5. Business Requirements",
                "6. Nonfunctional and Operational Requirements",
                "7. Constraints, Assumptions, and Dependencies",
                "8. Cost-Benefit Analysis and Financial Impact",
                "9. Risk Assessment and Management",
            ),
        }
        for document_type, groups in expected.items():
            definitions = document_template(document_type)
            self.assertEqual(
                tuple(dict.fromkeys(item.group for item in definitions)), groups
            )
            self.assertEqual(len({item.key for item in definitions}), len(definitions))
        self.assertIn("product_overview", {item.key for item in document_template(DocumentType.PRD)})
        self.assertIn("executive_summary", {item.key for item in document_template(DocumentType.BRD)})

    def test_success_matrix_is_not_a_document_section_or_acceptance_criterion(self):
        keys = {item.key for item in document_template(DocumentType.PRD)}
        self.assertNotIn("success_matrix", keys)
        self.assertIn("acceptance_criteria", keys)
        self.assertEqual(
            SUCCESS_MATRIX_REQUIRED_FIELDS,
            (
                "requirement_outcome",
                "metric",
                "target",
                "minimum_acceptance_threshold",
                "measurement_method",
                "data_source",
                "evaluation_period",
                "validation_owner",
                "status",
            ),
        )


class SuccessMatrixValidationTests(unittest.TestCase):
    def test_draft_allows_incomplete_multiple_entries_and_normalizes_order(self):
        data = document_data(1)
        data["success_matrix"] = [
            {"metric": "  Adoption  "},
            {"requirement_outcome": "Faster planning"},
        ]
        result = validate_document(data)
        self.assertTrue(result.is_valid)
        self.assertEqual(
            [row["position"] for row in result.normalized_data["success_matrix"]],
            [1, 2],
        )
        self.assertEqual(result.normalized_data["success_matrix"][0]["metric"], "Adoption")

    def test_approved_requires_complete_measurable_fields_but_not_baseline(self):
        complete = complete_success_matrix()[0]
        for field in SUCCESS_MATRIX_REQUIRED_FIELDS:
            row = dict(complete)
            row[field] = ""
            result = validate_document(
                {
                    **document_data(
                        1, status=DocumentStatus.APPROVED, matrix=[row]
                    ),
                    "agile_hierarchy": complete_prd_agile_hierarchy(),
                }
            )
            self.assertIn(f"success_matrix.1.{field}", result.errors)
        row = dict(complete)
        row["baseline"] = ""
        self.assertTrue(
            validate_document(
                {
                    **document_data(
                        1, status=DocumentStatus.APPROVED, matrix=[row]
                    ),
                    "agile_hierarchy": complete_prd_agile_hierarchy(),
                }
            ).is_valid
        )


class SuccessMatrixPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "checkpoint11.db"
        initialize_database(self.database)
        self.product = create_product(product_data(), self.database)

    def test_multiple_entries_stable_ids_order_and_update_persist(self):
        first = complete_success_matrix()[0]
        second = {**first, "entry_id": "success-test-2", "metric": "Cycle time"}
        document = create_document(
            document_data(self.product.id, matrix=[first, second]), self.database
        )
        self.assertEqual(
            [(entry.entry_id, entry.position) for entry in document.success_matrix],
            [("success-test-1", 1), ("success-test-2", 2)],
        )
        reordered = [
            {**second, "position": 99},
            {**first, "position": 42},
        ]
        updated = update_document(
            document.id, {"success_matrix": reordered}, self.database
        )
        self.assertEqual(
            [(entry.entry_id, entry.position) for entry in updated.success_matrix],
            [("success-test-2", 1), ("success-test-1", 2)],
        )
        self.assertEqual(get_document(document.id, self.database), updated)

    def test_checkpoint10_upgrade_preserves_existing_document_content(self):
        original = create_document(document_data(self.product.id), self.database)
        with sqlite3.connect(self.database) as connection:
            connection.execute(f"DROP TABLE {SUCCESS_MATRIX_TABLE}")
        self.assertEqual(detect_database_schema(self.database), SCHEMA_CHECKPOINT10)
        initialize_database(self.database)
        self.assertEqual(detect_database_schema(self.database), SCHEMA_CANONICAL)
        restored = get_document(original.id, self.database)
        self.assertEqual(restored.sections, original.sections)
        self.assertEqual(restored.success_matrix, ())


class PRDAgileHierarchyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "hierarchy.db"
        initialize_database(self.database)
        self.product = create_product(product_data(), self.database)

    def approved_data(self, hierarchy):
        data = document_data(
            self.product.id,
            status=DocumentStatus.APPROVED,
            matrix=complete_success_matrix(),
        )
        data["agile_hierarchy"] = hierarchy
        return data

    def test_all_four_levels_multiple_entries_and_independent_criteria(self):
        hierarchy = []
        for suffix in ("a", "b"):
            chain = complete_prd_agile_hierarchy(f"chain-{suffix}")
            for artifact in chain:
                artifact["acceptance_criteria"].append(
                    {
                        "criterion_id": f"{artifact['artifact_id']}-criterion-2",
                        "position": 50,
                        "text": f"Second measurable criterion for {artifact['artifact_type']}.",
                    }
                )
            hierarchy.extend(chain)
        result = validate_document(self.approved_data(hierarchy))
        self.assertTrue(result.is_valid, result.errors)
        normalized = result.normalized_data["agile_hierarchy"]
        for artifact_type in AgileArtifactType:
            entries = [
                item for item in normalized if item["artifact_type"] is artifact_type
            ]
            self.assertEqual([item["position"] for item in entries], [1, 2])
            self.assertTrue(all(len(item["acceptance_criteria"]) == 2 for item in entries))
            self.assertTrue(
                all(
                    [criterion["position"] for criterion in item["acceptance_criteria"]]
                    == [1, 2]
                    for item in entries
                )
            )
        criterion_ids = [
            criterion["criterion_id"]
            for artifact in normalized
            for criterion in artifact["acceptance_criteria"]
        ]
        self.assertEqual(len(criterion_ids), len(set(criterion_ids)))

    def test_invalid_and_missing_parents_fail_approved_validation(self):
        hierarchy = complete_prd_agile_hierarchy()
        hierarchy[1]["parent_artifact_id"] = None
        hierarchy[2]["parent_artifact_id"] = hierarchy[0]["artifact_id"]
        result = validate_document(self.approved_data(hierarchy))
        self.assertIn("agile_hierarchy.2.parent_artifact_id", result.errors)
        self.assertIn("agile_hierarchy.3.parent_artifact_id", result.errors)

    def test_nonblank_ids_use_the_shared_stable_identifier_contract(self):
        hierarchy = complete_prd_agile_hierarchy()
        hierarchy[0]["artifact_id"] = "invalid id"
        hierarchy[0]["acceptance_criteria"][0]["criterion_id"] = "invalid criterion"
        result = validate_document(self.approved_data(hierarchy))
        self.assertIn("agile_hierarchy.1.artifact_id", result.errors)
        self.assertIn(
            "agile_hierarchy.1.acceptance_criteria.1.criterion_id",
            result.errors,
        )

    def test_draft_allows_incomplete_entries_but_approved_requires_each_level_and_criteria(self):
        draft = document_data(self.product.id)
        draft["agile_hierarchy"] = [
            {
                "artifact_type": "epic",
                "title": "",
                "description": "",
                "acceptance_criteria": [],
            }
        ]
        self.assertTrue(validate_document(draft).is_valid)
        approved = self.approved_data(draft["agile_hierarchy"])
        result = validate_document(approved)
        self.assertFalse(result.is_valid)
        for artifact_type in (
            AgileArtifactType.CAPABILITY,
            AgileArtifactType.FEATURE,
            AgileArtifactType.USER_STORY,
        ):
            self.assertIn(f"agile_hierarchy.{artifact_type.value}", result.errors)
        self.assertIn("agile_hierarchy.1.acceptance_criteria", result.errors)

    def test_stable_ids_parent_ids_order_and_criteria_persist(self):
        hierarchy = complete_prd_agile_hierarchy("persist")
        created = create_document(self.approved_data(hierarchy), self.database)
        self.assertEqual(
            [item.artifact_type for item in created.agile_hierarchy],
            list(AgileArtifactType),
        )
        for item in created.agile_hierarchy:
            expected_parent = PARENT_TYPE[item.artifact_type]
            self.assertEqual(
                item.parent_artifact_id,
                None if expected_parent is None else f"persist-{expected_parent.value}",
            )
            self.assertEqual(len(item.acceptance_criteria), 1)
        updated = update_document(
            created.id,
            {"version": "1.1"},
            self.database,
        )
        self.assertEqual(updated.agile_hierarchy, created.agile_hierarchy)

    def test_checkpoint11_document_text_is_preserved_when_hierarchy_table_is_added(self):
        document = create_document(document_data(self.product.id), self.database)
        original_sections = dict(document.sections)
        original_sections["user_stories"] = "Existing user stories"
        original_sections["functional_requirements"] = "Existing functional requirements"
        original_sections["acceptance_criteria"] = "Existing acceptance criteria"
        document = update_document(
            document.id, {"sections": original_sections}, self.database
        )
        with sqlite3.connect(self.database) as connection:
            connection.execute("DROP TABLE prd_agile_acceptance_criteria")
            connection.execute("DROP TABLE prd_agile_artifacts")
        initialize_database(self.database)
        restored = get_document(document.id, self.database)
        self.assertEqual(restored.sections, original_sections)
        self.assertEqual(restored.agile_hierarchy, ())


class WorkspaceUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "workspace.db"
        initialize_database(self.database)
        original = os.environ.get("PMC_DATABASE_FILE")
        os.environ["PMC_DATABASE_FILE"] = str(self.database)
        self.addCleanup(
            lambda: os.environ.pop("PMC_DATABASE_FILE", None)
            if original is None
            else os.environ.__setitem__("PMC_DATABASE_FILE", original)
        )

    def test_all_seven_destinations_title_and_rerun_state(self):
        app = AppTest.from_file(APP_FILE).run()
        expected = (
            "Dashboard",
            "Create Product",
            "Create PRD",
            "Create BRD",
            "AI Assistant",
            "View Products",
            "Search Products",
        )
        self.assertEqual(tuple(app.radio[0].options), expected)
        for destination in expected:
            app.radio[0].set_value(destination).run()
            self.assertEqual(app.radio[0].value, destination)
            self.assertIn(destination, [header.value for header in app.header])
            self.assertEqual(list(app.exception), [])
        self.assertIn("Product workspace", [caption.value for caption in app.caption])

    def test_navigation_change_clears_transient_page_state(self):
        app = AppTest.from_file(APP_FILE).run()
        app.session_state["agile_generation_submission"] = ("stale",)
        app.session_state["grounded_generation_request"] = "stale request"
        app.session_state["primary_create_prd_stale"] = "stale form"
        app.radio[0].set_value("Create Product").run()
        self.assertNotIn("agile_generation_submission", app.session_state)
        self.assertNotIn("grounded_generation_request", app.session_state)
        self.assertNotIn("primary_create_prd_stale", app.session_state)

    def test_agile_ui_scopes_approved_sources_and_exposes_only_approved_controls(self):
        product = create_product(product_data(), self.database)
        create_document(
            {
                "product_id": product.id,
                "document_type": DocumentType.BRD,
                "title": "Approved strategy",
                "version": "1.0",
                "document_status": "approved",
                "sections": {
                    item.key: f"Evidence for {item.label}"
                    for item in document_template(DocumentType.BRD)
                },
            },
            self.database,
        )
        app = AppTest.from_file(APP_FILE).run()
        app.radio[0].set_value("AI Assistant").run()
        app.selectbox(key="agile_product_id").set_value(product.id).run()
        self.assertEqual(
            app.selectbox(key="agile_artifact_type").options,
            [item[0] for item in __import__("app").AGILE_TYPE_OPTIONS],
        )
        self.assertEqual(app.selectbox(key="agile_profile").value, "strictly_grounded")
        self.assertEqual(app.number_input(key="agile_top_k").value, 5)
        labels = [
            getattr(widget, "label", "")
            for collection in (app.text_input, app.number_input, app.selectbox)
            for widget in collection
        ]
        for prohibited in ("Temperature", "Top-P", "GEPA", "hallucination flag"):
            self.assertNotIn(prohibited, labels)
        self.assertTrue(app.multiselect(key="agile_document_ids").options)

    def test_agile_review_ui_displays_citations_claims_and_fail_closed_gates(self):
        fixture = checkpoint10_fixtures.Checkpoint10ReviewTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        os.environ["PMC_DATABASE_FILE"] = str(fixture.database_path)
        review = fixture.review()
        app = AppTest.from_file(APP_FILE).run()
        app.radio[0].set_value("AI Assistant").run()
        app.session_state["agile_review_batch"] = review
        app.run()
        rendered = "\n".join(
            element.value
            for collection in (
                app.markdown,
                app.caption,
                app.success,
                app.warning,
                app.error,
            )
            for element in collection
        )
        self.assertIn("Artifact-level citations", rendered)
        self.assertIn("Structured acceptance criteria", rendered)
        self.assertIn("Claim-support results", rendered)
        self.assertIn("Fail-closed acceptance gates", rendered)
        self.assertIn(fixture.chunk.chunk_id, rendered)
        self.assertFalse(
            app.button(key=f"agile_accept_{review.review_id}_{review.revision}").disabled
        )

    def _review_app(self):
        fixture = checkpoint10_fixtures.Checkpoint10ReviewTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        os.environ["PMC_DATABASE_FILE"] = str(fixture.database_path)
        original_api_key = os.environ.pop("OPENAI_API_KEY", None)
        self.addCleanup(
            lambda: os.environ.pop("OPENAI_API_KEY", None)
            if original_api_key is None
            else os.environ.__setitem__("OPENAI_API_KEY", original_api_key)
        )
        review = fixture.review()
        app = AppTest.from_file(APP_FILE).run()
        app.radio[0].set_value("AI Assistant").run()
        app.session_state["agile_review_batch"] = review
        app.run()
        return fixture, review, app

    def test_agile_ui_revision_reassesses_before_acceptance(self):
        _, review, app = self._review_app()
        app.text_input(
            key=f"agile_revision_title_{review.review_id}_{review.revision}_epic-generated"
        ).set_value("Customers must use MFA")
        app.button(
            key=f"FormSubmitter:agile_revision_form_{review.review_id}_{review.revision}-Revise and reassess"
        ).click().run()
        revised = app.session_state["agile_review_batch"]
        self.assertEqual(revised.revision, 2)
        self.assertEqual(revised.assessed_revision, 2)
        self.assertTrue(revised.can_accept)

    def test_agile_ui_reject_never_enters_accepted_storage(self):
        fixture, review, app = self._review_app()
        app.text_input(
            key=f"agile_rejection_reason_{review.review_id}_{review.revision}"
        ).set_value("Needs product changes")
        app.button(
            key=f"FormSubmitter:agile_reject_form_{review.review_id}_{review.revision}-Reject Agile batch"
        ).click().run()
        rejected = app.session_state["agile_review_batch"]
        self.assertEqual(rejected.review_state.value, "rejected")
        from src.database import list_accepted_agile_batches_for_product

        self.assertEqual(
            list_accepted_agile_batches_for_product(
                fixture.product.id, fixture.database_path
            ),
            [],
        )

    def test_agile_ui_accepts_once_through_trusted_service(self):
        fixture, review, app = self._review_app()
        app.button(
            key=f"agile_accept_{review.review_id}_{review.revision}"
        ).click().run()
        accepted = app.session_state["agile_review_batch"]
        self.assertEqual(accepted.review_state.value, "accepted")
        from src.database import list_accepted_agile_batches_for_product

        self.assertEqual(
            len(
                list_accepted_agile_batches_for_product(
                    fixture.product.id, fixture.database_path
                )
            ),
            1,
        )

    def test_corrected_prd_builder_guidance_counts_and_add_remove_actions(self):
        product = create_product(product_data(), self.database)
        app = AppTest.from_file(APP_FILE).run()
        app.radio[0].set_value("Create PRD").run()
        app.selectbox(key="primary_create_prd_product_selector").set_value(product.id).run()
        rendered = "\n".join(
            str(element.value)
            for collection in (app.markdown, app.caption, app.text)
            for element in collection
        )
        self.assertIn("Informational hierarchy summary", rendered)
        self.assertIn("Success Matrix entries:", rendered)
        self.assertNotIn("Success Matrix entries: 0 · Epics", rendered)
        button_labels = {button.label for button in app.button}
        self.assertIn("Add Contributor and Role", button_labels)
        self.assertIn("Remove Contributor and Role", button_labels)
        self.assertIn("Add Key Date and Milestone", button_labels)
        self.assertIn("Add Success Matrix entry", button_labels)
        help_text = "\n".join(
            str(getattr(widget, "help", "") or "") for widget in app.text_area
        )
        self.assertIn("how, where, and how frequently", help_text)
        self.assertIn("scheduling_started", help_text)
        self.assertIn("not saved automatically", help_text)
        prefix = "primary_create_prd_document_form_new_PRD"
        app.button(key=f"{prefix}_contributors_count_add").click().run()
        self.assertEqual(app.number_input(key=f"{prefix}_contributors_count").value, 1)
        app.button(key=f"{prefix}_contributors_count_remove").click().run()
        self.assertEqual(app.number_input(key=f"{prefix}_contributors_count").value, 0)


class StructuredCorrectionContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "structured-corrections.db"
        initialize_database(self.database)
        self.product = create_product(product_data(), self.database)

    @staticmethod
    def criteria(prefix: str):
        return [
            {"criterion_id": f"{prefix}-criterion-1", "position": 99,
             "text": f"{prefix} reaches a measurable threshold."},
            {"criterion_id": f"{prefix}-criterion-2", "position": 42,
             "text": f"{prefix} remains measurable under failure."},
        ]

    @classmethod
    def brd_row(cls, suffix: str = "one"):
        return {
            "row_id": f"brd-row-{suffix}",
            "position": 90,
            "epic_id": f"brd-epic-{suffix}",
            "epic": "Scheduling outcomes",
            "epic_acceptance_criteria": cls.criteria(f"epic-{suffix}"),
            "capability_id": f"brd-capability-{suffix}",
            "capability_parent_id": f"brd-epic-{suffix}",
            "capability": "Appointment scheduling",
            "capability_acceptance_criteria": cls.criteria(f"capability-{suffix}"),
            "feature_id": f"brd-feature-{suffix}",
            "feature_parent_id": f"brd-capability-{suffix}",
            "feature": "Availability selection",
            "feature_acceptance_criteria": cls.criteria(f"feature-{suffix}"),
            "user_story_id": f"brd-user-story-{suffix}",
            "user_story_parent_id": f"brd-feature-{suffix}",
            "user_story": "As a patient, I schedule an available appointment.",
            "user_story_acceptance_criteria": cls.criteria(f"story-{suffix}"),
        }

    def complete_document(self, document_type: DocumentType, status="draft"):
        data = {
            "product_id": self.product.id,
            "document_type": document_type,
            "title": f"Atlas {document_type.value}",
            "version": "1.0",
            "document_status": status,
            "sections": {
                item.key: f"Existing content for {item.label}"
                for item in document_template(document_type)
            },
            "success_matrix": [],
            "agile_hierarchy": [],
            "contributors": [],
            "key_dates_milestones": [],
            "brd_hierarchy": [],
            "brd_risks": [],
        }
        if document_type is DocumentType.PRD:
            data.update({
                "success_matrix": complete_success_matrix(),
                "agile_hierarchy": complete_prd_agile_hierarchy("correction"),
                "contributors": [
                    {"entry_id": "contributor-1", "contributor_name": "Avery", "contributor_role": "Product Manager"},
                    {"entry_id": "contributor-2", "contributor_name": "Morgan", "contributor_role": "Analytics Lead"},
                ],
                "key_dates_milestones": [
                    {"entry_id": "milestone-1", "date": "2026-09-01", "milestone": "Beta begins"},
                    {"entry_id": "milestone-2", "date": "2026-10-15", "milestone": "Launch review"},
                ],
            })
        else:
            data.update({
                "brd_hierarchy": [self.brd_row("one"), self.brd_row("two")],
                "brd_risks": [
                    {"entry_id": "risk-1", "business_risk": "Low adoption", "mitigation_strategy": "Run a guided beta"},
                    {"entry_id": "risk-2", "business_risk": "Data gaps", "mitigation_strategy": "Audit telemetry weekly"},
                ],
            })
        return data

    def test_multiple_contributors_milestones_stable_ids_order_and_preservation(self):
        data = self.complete_document(DocumentType.PRD)
        original_sections = dict(data["sections"])
        created = create_document(data, self.database)
        self.assertEqual([row.entry_id for row in created.contributors], ["contributor-1", "contributor-2"])
        self.assertEqual([row.position for row in created.key_dates_milestones], [1, 2])
        updated = update_document(created.id, {
            "contributors": list(reversed(data["contributors"])),
            "key_dates_milestones": list(reversed(data["key_dates_milestones"])),
        }, self.database)
        self.assertEqual([row.entry_id for row in updated.contributors], ["contributor-2", "contributor-1"])
        self.assertEqual([row.entry_id for row in updated.key_dates_milestones], ["milestone-2", "milestone-1"])
        self.assertEqual(updated.sections, original_sections)

    def test_brd_hierarchy_all_levels_and_risks_persist_in_deterministic_order(self):
        data = self.complete_document(DocumentType.BRD)
        created = create_document(data, self.database)
        self.assertEqual([row.row_id for row in created.brd_hierarchy], ["brd-row-one", "brd-row-two"])
        self.assertEqual(created.brd_hierarchy[0].capability_parent_id, "brd-epic-one")
        for level in ("epic", "capability", "feature", "user_story"):
            criteria = getattr(created.brd_hierarchy[0], f"{level}_acceptance_criteria")
            self.assertEqual([item.position for item in criteria], [1, 2])
            self.assertEqual(len({item.criterion_id for item in criteria}), 2)
        self.assertEqual(
            [(row.business_risk, row.mitigation_strategy) for row in created.brd_risks],
            [("Low adoption", "Run a guided beta"), ("Data gaps", "Audit telemetry weekly")],
        )

    def test_draft_incomplete_rows_allowed_but_explicit_approved_rows_are_complete(self):
        draft = self.complete_document(DocumentType.BRD)
        draft["brd_hierarchy"] = [{"row_id": "draft-row", "epic": "Draft"}]
        draft["brd_risks"] = [{"entry_id": "draft-risk", "business_risk": "Unknown"}]
        self.assertTrue(validate_document(draft).is_valid)
        draft["document_status"] = "approved"
        result = validate_document(draft)
        self.assertIn("brd_hierarchy.1.capability", result.errors)
        self.assertIn("brd_hierarchy.1.epic_acceptance_criteria", result.errors)
        self.assertIn("brd_risks.1.mitigation_strategy", result.errors)

        prd = self.complete_document(DocumentType.PRD, "approved")
        prd["contributors"][1]["contributor_role"] = ""
        prd["key_dates_milestones"][1]["date"] = ""
        result = validate_document(prd)
        self.assertIn("contributors.2.contributor_role", result.errors)
        self.assertIn("key_dates_milestones.2.date", result.errors)

    def test_legacy_sections_initialize_without_overwrite_or_criteria_copying(self):
        data = self.complete_document(DocumentType.BRD)
        data.pop("brd_hierarchy")
        data.pop("brd_risks")
        data["sections"].update({
            "epics": "Legacy epic", "capabilities": "Legacy capability",
            "features": "Legacy feature", "user_stories": "Legacy story",
            "acceptance_criteria": "Legacy story criterion",
            "business_risks": "Legacy risk", "mitigation_strategies": "Legacy mitigation",
        })
        created = create_document(data, self.database)
        self.assertEqual(created.sections, data["sections"])
        row = created.brd_hierarchy[0]
        self.assertEqual(row.epic, "Legacy epic")
        self.assertEqual(row.epic_acceptance_criteria, ())
        self.assertEqual(row.capability_acceptance_criteria, ())
        self.assertEqual(row.feature_acceptance_criteria, ())
        self.assertEqual(row.user_story_acceptance_criteria[0].text, "Legacy story criterion")
        self.assertEqual(created.brd_risks[0].mitigation_strategy, "Legacy mitigation")

    def test_schema_upgrade_is_additive_idempotent_and_preserves_existing_rows(self):
        created = create_document(self.complete_document(DocumentType.PRD), self.database)
        original = get_document(created.id, self.database)
        with sqlite3.connect(self.database) as connection:
            connection.execute("DROP TABLE structured_document_rows")
        self.assertEqual(detect_database_schema(self.database), "canonical_checkpoint11_hierarchy")
        initialize_database(self.database)
        initialize_database(self.database)
        restored = get_document(created.id, self.database)
        self.assertEqual(restored.sections, original.sections)
        self.assertEqual(restored.success_matrix, original.success_matrix)
        self.assertEqual(restored.agile_hierarchy, original.agile_hierarchy)
        self.assertEqual(restored.contributors, ())


class StructuredProviderAdapterTests(unittest.TestCase):
    def test_json_schema_request_is_parsed_without_exposing_internal_controls(self):
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            output_text=json.dumps({"artifacts": []})
        )
        service = OpenAIService(client, "offline-model", "offline-embedding")
        source = SimpleNamespace(reference_id="source-1")
        # dataclasses.asdict requires a dataclass, so use an actual minimal source shape.
        from src.agile_prompt_catalog import AgilePromptSource

        source = AgilePromptSource(
            "source-1", 1, "Atlas", 2, "PRD", DocumentType.PRD,
            DocumentStatus.APPROVED, "success_metrics", "Success metrics", "Evidence"
        )
        envelope = SimpleNamespace(
            trusted_instructions=("Return structured data.",),
            application_context={"product_id": 1},
            request_data="Generate one Epic.",
            source_data=(source,),
        )
        settings = SimpleNamespace(
            model="offline-model", as_request_parameters=lambda: {}
        )
        self.assertEqual(
            service.create_structured_response(
                envelope, json_schema={"type": "object"}, settings=settings
            ),
            {"artifacts": []},
        )
        request = client.responses.create.call_args.kwargs
        self.assertEqual(request["text"]["format"]["type"], "json_schema")
        self.assertTrue(request["text"]["format"]["strict"])
        self.assertNotIn("temperature", request)
        self.assertNotIn("top_p", request)


if __name__ == "__main__":
    unittest.main()
