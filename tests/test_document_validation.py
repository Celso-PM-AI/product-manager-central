"""Tests for deterministic BRD and PRD validation and prepopulation."""

import unittest

from src.document_templates import (
    document_template,
    prepopulated_sections,
)
from src.models import DocumentStatus, DocumentType, Product, ProductStatus
from src.validation import (
    DOCUMENT_SECTION_MAX_LENGTH,
    DOCUMENT_TITLE_MAX_LENGTH,
    DOCUMENT_VERSION_MAX_LENGTH,
    validate_document,
)


def valid_document_data(
    document_type: DocumentType = DocumentType.BRD,
    **overrides: object,
) -> dict[str, object]:
    data: dict[str, object] = {
        "product_id": 1,
        "document_type": document_type,
        "title": "Product requirements",
        "version": "1.0",
        "document_status": DocumentStatus.DRAFT,
        "sections": {
            section.key: "" for section in document_template(document_type)
        },
    }
    data.update(overrides)
    return data


class DocumentValidationTests(unittest.TestCase):
    def test_draft_accepts_every_empty_body_section(self):
        result = validate_document(valid_document_data())

        self.assertTrue(result.is_valid)
        self.assertTrue(all(value == "" for value in result.normalized_data["sections"].values()))

    def test_approved_reports_every_incomplete_section_by_label(self):
        data = valid_document_data(document_status=DocumentStatus.APPROVED)

        result = validate_document(data)

        expected_keys = {
            f"sections.{section.key}" for section in document_template(DocumentType.BRD)
        }
        self.assertFalse(result.is_valid)
        self.assertEqual(set(result.errors), expected_keys)
        for section in document_template(DocumentType.BRD):
            self.assertIn(section.label, result.errors[f"sections.{section.key}"])

    def test_approved_accepts_complete_brd_and_prd(self):
        for document_type in DocumentType:
            with self.subTest(document_type=document_type):
                sections = {
                    section.key: f"Content for {section.label}"
                    for section in document_template(document_type)
                }
                result = validate_document(
                    valid_document_data(
                        document_type,
                        document_status="approved",
                        sections=sections,
                    )
                )
                self.assertTrue(result.is_valid)

    def test_metadata_is_required_and_normalized(self):
        data = valid_document_data()
        data.update(
            product_id=0,
            document_type="unknown",
            title="  ",
            version="\n",
            document_status="Approved",
        )

        result = validate_document(data)

        self.assertEqual(
            set(result.errors),
            {"product_id", "document_type", "title", "version", "document_status"},
        )

    def test_document_length_limits(self):
        valid = valid_document_data(
            title="x" * DOCUMENT_TITLE_MAX_LENGTH,
            version="x" * DOCUMENT_VERSION_MAX_LENGTH,
            sections={
                section.key: "x" * DOCUMENT_SECTION_MAX_LENGTH
                for section in document_template(DocumentType.BRD)
            },
        )
        self.assertTrue(validate_document(valid).is_valid)

        cases = (
            ("title", "x" * (DOCUMENT_TITLE_MAX_LENGTH + 1)),
            ("version", "x" * (DOCUMENT_VERSION_MAX_LENGTH + 1)),
        )
        for field, value in cases:
            with self.subTest(field=field):
                data = valid_document_data(**{field: value})
                self.assertIn(field, validate_document(data).errors)

        data = valid_document_data()
        data["sections"]["executive_summary"] = "x" * (
            DOCUMENT_SECTION_MAX_LENGTH + 1
        )
        self.assertIn(
            "sections.executive_summary",
            validate_document(data).errors,
        )

    def test_unknown_sections_and_system_fields_are_rejected(self):
        data = valid_document_data(id=10)
        data["sections"]["future_section"] = "Unexpected"

        result = validate_document(data)

        self.assertIn("id", result.errors)
        self.assertIn("sections.future_section", result.errors)

    def test_outer_whitespace_is_trimmed_and_internal_content_preserved(self):
        data = valid_document_data(title="  Title  ", version=" v1 ")
        data["sections"]["executive_summary"] = "  First\n  Second  "

        result = validate_document(data)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.normalized_data["title"], "Title")
        self.assertEqual(result.normalized_data["version"], "v1")
        self.assertEqual(
            result.normalized_data["sections"]["executive_summary"],
            "First\n  Second",
        )


class DocumentPrepopulationTests(unittest.TestCase):
    def setUp(self):
        self.product = Product(
            id=7,
            name="Atlas",
            description="Portfolio planning workspace.",
            target_users="Product leaders",
            business_goal="Improve portfolio decisions.",
            status=ProductStatus.PLANNING,
            customer_problem="Evidence is fragmented.",
        )

    def test_brd_prepopulation_uses_only_approved_mappings(self):
        sections = prepopulated_sections(self.product, DocumentType.BRD)

        self.assertEqual(sections["executive_summary"], self.product.description)
        self.assertEqual(sections["business_problem"], self.product.customer_problem)
        self.assertEqual(sections["business_objectives"], self.product.business_goal)
        self.assertEqual(sections["stakeholders"], "")

    def test_prd_prepopulation_uses_only_approved_mappings(self):
        sections = prepopulated_sections(self.product, DocumentType.PRD)

        self.assertEqual(sections["product_overview"], self.product.description)
        self.assertEqual(sections["customer_problem"], self.product.customer_problem)
        self.assertEqual(sections["target_users_personas"], self.product.target_users)
        self.assertEqual(sections["product_goals"], self.product.business_goal)
        self.assertEqual(sections["functional_requirements"], "")


if __name__ == "__main__":
    unittest.main()
