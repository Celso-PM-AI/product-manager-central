"""Tests for the Product model and centralized validation."""

import unittest
from enum import Enum

from src.models import (
    DEFAULT_PRODUCT_STATUS,
    EDITABLE_PRODUCT_FIELDS,
    LEGACY_TO_CANONICAL_FIELD_MAP,
    OPTIONAL_PRODUCT_FIELDS,
    REQUIRED_PRODUCT_FIELDS,
    SYSTEM_MANAGED_PRODUCT_FIELDS,
    Product,
    ProductStatus,
)
from src.validation import (
    TEXT_FIELD_MAX_LENGTHS,
    normalize_optional_text,
    normalize_text,
    validate_product,
)


def valid_product_data() -> dict[str, object]:
    """Return a new valid input mapping for each test."""

    return {
        "name": "Product Manager Central",
        "description": "A workspace for product managers.",
        "target_users": "Product managers",
        "business_goal": "Improve product planning.",
        "status": "discovery",
    }


class ProductModelTests(unittest.TestCase):
    def test_product_status_is_a_string_enum(self):
        self.assertTrue(issubclass(ProductStatus, str))
        self.assertTrue(issubclass(ProductStatus, Enum))

    def test_product_status_contains_exact_approved_values(self):
        self.assertEqual(
            [status.value for status in ProductStatus],
            [
                "idea",
                "discovery",
                "planning",
                "in_development",
                "launched",
                "archived",
            ],
        )

    def test_default_product_status_is_discovery(self):
        self.assertIs(DEFAULT_PRODUCT_STATUS, ProductStatus.DISCOVERY)
        self.assertEqual(DEFAULT_PRODUCT_STATUS, "discovery")

    def test_field_categories_match_the_specification(self):
        self.assertEqual(
            REQUIRED_PRODUCT_FIELDS,
            (
                "name",
                "description",
                "target_users",
                "business_goal",
                "status",
            ),
        )
        self.assertEqual(
            OPTIONAL_PRODUCT_FIELDS,
            ("customer_problem", "product_strategy", "notes"),
        )
        self.assertEqual(
            SYSTEM_MANAGED_PRODUCT_FIELDS,
            ("id", "created_at", "updated_at"),
        )

    def test_field_categories_do_not_overlap(self):
        required = set(REQUIRED_PRODUCT_FIELDS)
        optional = set(OPTIONAL_PRODUCT_FIELDS)
        system_managed = set(SYSTEM_MANAGED_PRODUCT_FIELDS)

        self.assertTrue(required.isdisjoint(optional))
        self.assertTrue(required.isdisjoint(system_managed))
        self.assertTrue(optional.isdisjoint(system_managed))
        self.assertEqual(
            EDITABLE_PRODUCT_FIELDS,
            REQUIRED_PRODUCT_FIELDS + OPTIONAL_PRODUCT_FIELDS,
        )

    def test_legacy_to_canonical_field_mapping(self):
        self.assertEqual(
            LEGACY_TO_CANONICAL_FIELD_MAP,
            {
                "product_name": "name",
                "product_idea": "description",
                "target_user": "target_users",
                "business_goal": "business_goal",
                "date_created": "created_at",
            },
        )

    def test_product_defaults_optional_and_system_fields_to_none(self):
        product = Product(
            name="PMC",
            description="Product workspace",
            target_users="Product managers",
            business_goal="Improve planning",
            status=ProductStatus.DISCOVERY,
        )

        self.assertIsNone(product.customer_problem)
        self.assertIsNone(product.product_strategy)
        self.assertIsNone(product.notes)
        self.assertIsNone(product.id)
        self.assertIsNone(product.created_at)
        self.assertIsNone(product.updated_at)

    def test_product_can_represent_a_saved_record(self):
        product = Product(
            name="PMC",
            description="Product workspace",
            target_users="Product managers",
            business_goal="Improve planning",
            status=ProductStatus.LAUNCHED,
            customer_problem="Documentation is fragmented.",
            product_strategy="Centralize product knowledge.",
            notes="Initial record",
            id=1,
            created_at="2026-07-19 10:03:17",
            updated_at="2026-07-19 10:03:17",
        )

        self.assertEqual(product.id, 1)
        self.assertIs(product.status, ProductStatus.LAUNCHED)
        self.assertEqual(product.created_at, "2026-07-19 10:03:17")


class NormalizationTests(unittest.TestCase):
    def test_normalize_text_removes_only_outer_whitespace(self):
        self.assertEqual(
            normalize_text("  first line\n  second line  "),
            "first line\n  second line",
        )

    def test_normalize_optional_text_converts_blank_values_to_none(self):
        self.assertIsNone(normalize_optional_text(None))
        self.assertIsNone(normalize_optional_text(""))
        self.assertIsNone(normalize_optional_text(" \n\t "))

    def test_normalize_optional_text_preserves_nonblank_internal_content(self):
        self.assertEqual(
            normalize_optional_text("  first\n  second  "),
            "first\n  second",
        )


class ProductValidationTests(unittest.TestCase):
    def test_valid_required_only_input(self):
        result = validate_product(valid_product_data())

        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, {})
        self.assertIs(result.normalized_data["status"], ProductStatus.DISCOVERY)
        for field in OPTIONAL_PRODUCT_FIELDS:
            self.assertIsNone(result.normalized_data[field])

    def test_valid_input_with_all_optional_fields(self):
        data = valid_product_data()
        data.update(
            {
                "customer_problem": "Information is fragmented.",
                "product_strategy": "Centralize product knowledge.",
                "notes": "Validate with product managers.",
            }
        )

        result = validate_product(data)

        self.assertTrue(result.is_valid)
        self.assertEqual(
            result.normalized_data["customer_problem"],
            "Information is fragmented.",
        )
        self.assertEqual(
            result.normalized_data["product_strategy"],
            "Centralize product knowledge.",
        )
        self.assertEqual(
            result.normalized_data["notes"],
            "Validate with product managers.",
        )

    def test_string_status_is_normalized_to_product_status_enum(self):
        data = valid_product_data()
        data["status"] = "planning"

        result = validate_product(data)

        self.assertTrue(result.is_valid)
        self.assertIs(result.normalized_data["status"], ProductStatus.PLANNING)
        self.assertEqual(result.normalized_data["status"], "planning")

    def test_enum_status_remains_a_product_status_enum(self):
        data = valid_product_data()
        data["status"] = ProductStatus.IN_DEVELOPMENT

        result = validate_product(data)

        self.assertTrue(result.is_valid)
        self.assertIs(
            result.normalized_data["status"],
            ProductStatus.IN_DEVELOPMENT,
        )
        self.assertEqual(result.normalized_data["status"], "in_development")

    def test_every_approved_string_status_is_valid_and_normalized_to_enum(self):
        for status in ProductStatus:
            with self.subTest(status=status.value):
                data = valid_product_data()
                data["status"] = status.value

                result = validate_product(data)

                self.assertTrue(result.is_valid)
                self.assertIs(result.normalized_data["status"], status)

    def test_every_approved_enum_status_is_valid(self):
        for status in ProductStatus:
            with self.subTest(status=status.value):
                data = valid_product_data()
                data["status"] = status

                result = validate_product(data)

                self.assertTrue(result.is_valid)
                self.assertIs(result.normalized_data["status"], status)

    def test_status_string_outer_whitespace_is_removed(self):
        data = valid_product_data()
        data["status"] = "  discovery\n"

        result = validate_product(data)

        self.assertTrue(result.is_valid)
        self.assertIs(result.normalized_data["status"], ProductStatus.DISCOVERY)

    def test_each_missing_required_field_is_reported(self):
        for field in REQUIRED_PRODUCT_FIELDS:
            with self.subTest(field=field):
                data = valid_product_data()
                del data[field]

                result = validate_product(data)

                self.assertFalse(result.is_valid)
                self.assertIn(field, result.errors)

    def test_all_missing_required_fields_are_reported_together(self):
        result = validate_product({})

        self.assertFalse(result.is_valid)
        self.assertEqual(set(result.errors), set(REQUIRED_PRODUCT_FIELDS))
        for field in OPTIONAL_PRODUCT_FIELDS:
            self.assertIsNone(result.normalized_data[field])

    def test_required_text_rejects_empty_and_whitespace_only_values(self):
        for value in ("", "   ", "\n\t"):
            for field in REQUIRED_PRODUCT_FIELDS[:-1]:
                with self.subTest(field=field, value=repr(value)):
                    data = valid_product_data()
                    data[field] = value

                    result = validate_product(data)

                    self.assertIn(field, result.errors)
                    self.assertIn("required", result.errors[field])

    def test_required_fields_reject_none(self):
        for field in REQUIRED_PRODUCT_FIELDS:
            with self.subTest(field=field):
                data = valid_product_data()
                data[field] = None

                result = validate_product(data)

                self.assertIn(field, result.errors)
                self.assertIn("required", result.errors[field])

    def test_required_text_fields_reject_non_string_values(self):
        for field in REQUIRED_PRODUCT_FIELDS[:-1]:
            for value in (123, True, [], {}):
                with self.subTest(field=field, value=value):
                    data = valid_product_data()
                    data[field] = value

                    result = validate_product(data)

                    self.assertIn(field, result.errors)
                    self.assertIn("must be text", result.errors[field])

    def test_required_text_is_trimmed(self):
        data = valid_product_data()
        data.update(
            {
                "name": "  PMC  ",
                "description": "\nDescription\n",
                "target_users": "\tProduct managers\t",
                "business_goal": "  Improve planning.\n",
            }
        )

        result = validate_product(data)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.normalized_data["name"], "PMC")
        self.assertEqual(result.normalized_data["description"], "Description")
        self.assertEqual(
            result.normalized_data["target_users"],
            "Product managers",
        )
        self.assertEqual(
            result.normalized_data["business_goal"],
            "Improve planning.",
        )

    def test_optional_missing_none_and_blank_values_normalize_to_none(self):
        for field in OPTIONAL_PRODUCT_FIELDS:
            for value in (None, "", "  \n\t "):
                with self.subTest(field=field, value=repr(value)):
                    data = valid_product_data()
                    data[field] = value

                    result = validate_product(data)

                    self.assertTrue(result.is_valid)
                    self.assertIsNone(result.normalized_data[field])

    def test_optional_fields_reject_non_string_values(self):
        for field in OPTIONAL_PRODUCT_FIELDS:
            for value in (123, True, [], {}):
                with self.subTest(field=field, value=value):
                    data = valid_product_data()
                    data[field] = value

                    result = validate_product(data)

                    self.assertIn(field, result.errors)
                    self.assertIn("must be text", result.errors[field])

    def test_optional_text_is_trimmed(self):
        data = valid_product_data()
        data.update(
            {
                "customer_problem": "  Fragmented information  ",
                "product_strategy": "\nCentralize knowledge\n",
                "notes": "\tResearch next\t",
            }
        )

        result = validate_product(data)

        self.assertTrue(result.is_valid)
        self.assertEqual(
            result.normalized_data["customer_problem"],
            "Fragmented information",
        )
        self.assertEqual(
            result.normalized_data["product_strategy"],
            "Centralize knowledge",
        )
        self.assertEqual(result.normalized_data["notes"], "Research next")

    def test_every_text_field_accepts_exact_maximum_length(self):
        for field, maximum in TEXT_FIELD_MAX_LENGTHS.items():
            with self.subTest(field=field):
                data = valid_product_data()
                data[field] = "x" * maximum

                result = validate_product(data)

                self.assertTrue(result.is_valid)
                self.assertEqual(len(result.normalized_data[field]), maximum)

    def test_every_text_field_rejects_one_character_over_maximum(self):
        for field, maximum in TEXT_FIELD_MAX_LENGTHS.items():
            with self.subTest(field=field):
                data = valid_product_data()
                data[field] = "x" * (maximum + 1)

                result = validate_product(data)

                self.assertFalse(result.is_valid)
                self.assertIn(field, result.errors)
                self.assertIn("characters or fewer", result.errors[field])

    def test_unicode_emoji_bullets_and_multiline_text_are_valid(self):
        data = valid_product_data()
        data.update(
            {
                "name": "PMC 🚀",
                "description": "Plan clearly.\n• Learn quickly\n• Décider mieux",
                "target_users": "Product managers 👩🏽‍💻",
                "business_goal": "Améliorer les décisions.",
                "notes": "第一步\n第二步",
            }
        )

        result = validate_product(data)

        self.assertTrue(result.is_valid)
        self.assertEqual(
            result.normalized_data["description"],
            "Plan clearly.\n• Learn quickly\n• Décider mieux",
        )
        self.assertEqual(result.normalized_data["notes"], "第一步\n第二步")

    def test_internal_spaces_and_line_breaks_are_preserved(self):
        data = valid_product_data()
        data["description"] = "  First  phrase\n  Second phrase  "

        result = validate_product(data)

        self.assertEqual(
            result.normalized_data["description"],
            "First  phrase\n  Second phrase",
        )

    def test_missing_empty_invalid_and_incorrectly_cased_statuses_fail(self):
        invalid_statuses = (None, "", "   ", "unknown", "Discovery", 123, True)

        for value in invalid_statuses:
            with self.subTest(value=repr(value)):
                data = valid_product_data()
                data["status"] = value

                result = validate_product(data)

                self.assertFalse(result.is_valid)
                self.assertIn("status", result.errors)

    def test_system_managed_fields_are_rejected_even_when_none(self):
        for field in SYSTEM_MANAGED_PRODUCT_FIELDS:
            with self.subTest(field=field):
                data = valid_product_data()
                data[field] = None

                result = validate_product(data)

                self.assertFalse(result.is_valid)
                self.assertIn(field, result.errors)
                self.assertIn("system-managed", result.errors[field])

    def test_all_system_managed_fields_are_reported_together(self):
        data = valid_product_data()
        data.update(
            {
                "id": 1,
                "created_at": "2026-07-19 10:03:17",
                "updated_at": "2026-07-19 10:03:17",
            }
        )

        result = validate_product(data)

        self.assertEqual(
            set(result.errors),
            set(SYSTEM_MANAGED_PRODUCT_FIELDS),
        )

    def test_unknown_fields_are_rejected(self):
        data = valid_product_data()
        data["product_owner"] = "Celso"

        result = validate_product(data)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.errors["product_owner"], "Unknown field.")

    def test_multiple_unknown_fields_are_reported(self):
        data = valid_product_data()
        data["product_owner"] = "Celso"
        data["priority"] = "High"

        result = validate_product(data)

        self.assertIn("product_owner", result.errors)
        self.assertIn("priority", result.errors)

    def test_validation_collects_different_error_types_in_one_pass(self):
        data = {
            "name": " ",
            "description": 123,
            "target_users": "Product managers",
            "business_goal": "x" * 2_001,
            "status": "Discovery",
            "notes": [],
            "id": 1,
            "unexpected": "value",
        }

        result = validate_product(data)

        self.assertFalse(result.is_valid)
        self.assertEqual(
            set(result.errors),
            {
                "name",
                "description",
                "business_goal",
                "status",
                "notes",
                "id",
                "unexpected",
            },
        )

    def test_validation_does_not_mutate_supplied_mapping(self):
        data = valid_product_data()
        data.update(
            {
                "name": "  PMC  ",
                "customer_problem": "  Fragmented information  ",
                "notes": "   ",
            }
        )
        original = data.copy()

        validate_product(data)

        self.assertEqual(data, original)


if __name__ == "__main__":
    unittest.main()
