"""Tests for small presentation helpers used by the Streamlit interface."""

import unittest

from app import product_option_label, status_label, target_users_summary
from src.models import Product, ProductStatus


class AppPresentationHelperTests(unittest.TestCase):
    def test_status_label_is_readable(self):
        self.assertEqual(
            status_label(ProductStatus.IN_DEVELOPMENT),
            "In Development",
        )

    def test_product_option_label_includes_name_status_and_id(self):
        product = Product(
            id=7,
            name="Roadmap Hub",
            description="A planning workspace.",
            target_users="Product managers",
            business_goal="Improve roadmap clarity.",
            status=ProductStatus.PLANNING,
        )

        self.assertEqual(
            product_option_label(product),
            "Roadmap Hub · Planning · ID 7",
        )

    def test_short_target_users_summary_is_unchanged(self):
        self.assertEqual(
            target_users_summary("Product managers"),
            "Product managers",
        )

    def test_target_users_summary_compacts_whitespace_and_truncates(self):
        self.assertEqual(
            target_users_summary("  Product\n leaders and researchers  ", limit=20),
            "Product leaders and…",
        )


if __name__ == "__main__":
    unittest.main()
