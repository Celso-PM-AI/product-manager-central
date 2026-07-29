"""Isolated Streamlit workflow tests for Phase 4 and Phase 5 behavior."""

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.database import (
    create_product,
    get_product,
    initialize_database,
    list_products,
)
from src.models import ProductStatus


APP_FILE = Path(__file__).resolve().parents[1] / "app.py"


def disposable_product_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "name": "Disposable Product",
        "description": "A disposable product for isolated workflow testing.",
        "target_users": "Test users",
        "business_goal": "Verify product workflows safely.",
        "status": "planning",
        "customer_problem": "The workflow needs verification.",
        "product_strategy": "Exercise it with temporary data.",
        "notes": "Never use the live database.",
    }
    data.update(overrides)
    return data


class StreamlitWorkflowTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = (
            Path(self.temporary_directory.name) / "temporary-ui-test.db"
        )
        initialize_database(self.database_path)
        self.product = create_product(
            disposable_product_data(),
            self.database_path,
        )

        original_database_file = os.environ.get("PMC_DATABASE_FILE")
        os.environ["PMC_DATABASE_FILE"] = str(self.database_path)

        def restore_database_environment() -> None:
            if original_database_file is None:
                os.environ.pop("PMC_DATABASE_FILE", None)
            else:
                os.environ["PMC_DATABASE_FILE"] = original_database_file

        self.addCleanup(restore_database_environment)
        self.app = AppTest.from_file(APP_FILE, default_timeout=5).run()
        self.assertEqual(list(self.app.exception), [])

    def open_product_list(self) -> None:
        self.app.radio[0].set_value("View Products").run()
        self.assertEqual(list(self.app.exception), [])

    def open_edit_form(self) -> str:
        self.open_product_list()
        self.app.button(
            key=f"view_product_selector_edit_action_{self.product.id}"
        ).click().run()
        self.assertEqual(list(self.app.exception), [])
        return f"view_product_selector_edit_{self.product.id}"

    def open_delete_confirmation(self) -> None:
        self.open_product_list()
        self.app.button(
            key=f"view_product_selector_delete_action_{self.product.id}"
        ).click().run()
        self.assertEqual(list(self.app.exception), [])

    def execute_database_sql(self, sql: str) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute(sql)


class EditWorkflowTests(StreamlitWorkflowTestCase):
    def test_edit_form_is_prepopulated_and_updates_every_editable_field(self):
        prefix = self.open_edit_form()
        original = get_product(self.product.id, self.database_path)

        self.assertEqual(self.app.text_input(key=f"{prefix}_name").value, original.name)
        self.assertEqual(
            self.app.text_area(key=f"{prefix}_description").value,
            original.description,
        )
        self.assertEqual(
            self.app.text_area(key=f"{prefix}_target_users").value,
            original.target_users,
        )
        self.assertEqual(
            self.app.text_area(key=f"{prefix}_business_goal").value,
            original.business_goal,
        )
        self.assertEqual(
            self.app.selectbox(key=f"{prefix}_status").value,
            original.status,
        )
        self.assertEqual(
            self.app.text_area(key=f"{prefix}_customer_problem").value,
            original.customer_problem,
        )
        self.assertEqual(
            self.app.text_area(key=f"{prefix}_product_strategy").value,
            original.product_strategy,
        )
        self.assertEqual(
            self.app.text_area(key=f"{prefix}_notes").value,
            original.notes,
        )

        self.app.text_input(key=f"{prefix}_name").set_value("Updated Product")
        self.app.text_area(key=f"{prefix}_description").set_value(
            "Updated description"
        )
        self.app.text_area(key=f"{prefix}_target_users").set_value(
            "Product leaders"
        )
        self.app.text_area(key=f"{prefix}_business_goal").set_value(
            "Updated business goal"
        )
        self.app.selectbox(key=f"{prefix}_status").set_value(
            ProductStatus.LAUNCHED
        )
        self.app.text_area(key=f"{prefix}_customer_problem").set_value(
            "Updated customer problem"
        )
        self.app.text_area(key=f"{prefix}_product_strategy").set_value(
            "Updated product strategy"
        )
        self.app.text_area(key=f"{prefix}_notes").set_value("Updated notes")
        self.app.button(
            key=f"FormSubmitter:{prefix}-Save changes"
        ).click().run()

        updated = get_product(self.product.id, self.database_path)
        self.assertEqual(updated.id, original.id)
        self.assertEqual(updated.name, "Updated Product")
        self.assertEqual(updated.description, "Updated description")
        self.assertEqual(updated.target_users, "Product leaders")
        self.assertEqual(updated.business_goal, "Updated business goal")
        self.assertIs(updated.status, ProductStatus.LAUNCHED)
        self.assertEqual(updated.customer_problem, "Updated customer problem")
        self.assertEqual(updated.product_strategy, "Updated product strategy")
        self.assertEqual(updated.notes, "Updated notes")
        self.assertEqual(updated.created_at, original.created_at)
        self.assertNotEqual(updated.updated_at, original.updated_at)
        self.assertEqual(
            [message.value for message in self.app.success],
            ['"Updated Product" was updated successfully.'],
        )
        self.assertIsNotNone(
            self.app.button(
                key=f"view_product_selector_edit_action_{self.product.id}"
            )
        )

    def test_invalid_edit_displays_all_errors_and_does_not_update_database(self):
        prefix = self.open_edit_form()
        original = get_product(self.product.id, self.database_path)
        for suffix in ("name", "description", "target_users", "business_goal"):
            widget = (
                self.app.text_input(key=f"{prefix}_{suffix}")
                if suffix == "name"
                else self.app.text_area(key=f"{prefix}_{suffix}")
            )
            widget.set_value("   ")

        self.app.button(
            key=f"FormSubmitter:{prefix}-Save changes"
        ).click().run()

        self.assertEqual(
            get_product(self.product.id, self.database_path),
            original,
        )
        self.assertIn(
            "Please correct the following fields before saving:",
            [message.value for message in self.app.error],
        )
        rendered_markdown = "\n".join(
            element.value for element in self.app.markdown
        )
        for label in ("Name", "Description", "Target users", "Business goal"):
            self.assertIn(f"{label} is required.", rendered_markdown)

    def test_cancel_edit_leaves_product_unchanged(self):
        prefix = self.open_edit_form()
        original = get_product(self.product.id, self.database_path)
        self.app.text_input(key=f"{prefix}_name").set_value("Unsaved name")

        self.app.button(key=f"FormSubmitter:{prefix}-Cancel").click().run()

        self.assertEqual(
            get_product(self.product.id, self.database_path),
            original,
        )
        self.assertIsNotNone(
            self.app.button(
                key=f"view_product_selector_edit_action_{self.product.id}"
            )
        )

    def test_product_deleted_while_editing_is_handled_gracefully(self):
        prefix = self.open_edit_form()
        self.execute_database_sql(
            """
            CREATE TRIGGER delete_product_before_update
            BEFORE UPDATE ON products
            BEGIN
                DELETE FROM products WHERE id = OLD.id;
            END
            """
        )

        self.app.button(
            key=f"FormSubmitter:{prefix}-Save changes"
        ).click().run()

        self.assertIn(
            "This product no longer exists and could not be updated.",
            [message.value for message in self.app.warning],
        )

    def test_database_error_during_edit_is_user_safe(self):
        prefix = self.open_edit_form()
        self.execute_database_sql(
            """
            CREATE TRIGGER fail_product_update
            BEFORE UPDATE ON products
            BEGIN
                SELECT RAISE(ABORT, 'temporary update failure');
            END
            """
        )

        self.app.button(
            key=f"FormSubmitter:{prefix}-Save changes"
        ).click().run()

        self.assertEqual(list(self.app.exception), [])
        self.assertIn(
            "Product data could not be updated. "
            "Please check the local database and try again.",
            [message.value for message in self.app.error],
        )
        self.assertIsNotNone(get_product(self.product.id, self.database_path))


class DeleteWorkflowTests(StreamlitWorkflowTestCase):
    def test_first_delete_click_only_opens_confirmation(self):
        self.open_delete_confirmation()

        self.assertIsNotNone(get_product(self.product.id, self.database_path))
        warning = "\n".join(message.value for message in self.app.warning)
        self.assertIn(self.product.name, warning)
        self.assertIn(f"product ID {self.product.id}", warning)
        self.assertIsNotNone(
            self.app.button(
                key=f"view_product_selector_confirm_delete_{self.product.id}"
            )
        )
        self.assertIsNotNone(
            self.app.button(
                key=f"view_product_selector_cancel_delete_{self.product.id}"
            )
        )

    def test_cancel_delete_leaves_product_unchanged(self):
        self.open_delete_confirmation()
        original = get_product(self.product.id, self.database_path)

        self.app.button(
            key=f"view_product_selector_cancel_delete_{self.product.id}"
        ).click().run()

        self.assertEqual(
            get_product(self.product.id, self.database_path),
            original,
        )
        self.assertIsNotNone(
            self.app.button(
                key=f"view_product_selector_delete_action_{self.product.id}"
            )
        )

    def test_confirm_delete_removes_once_and_returns_to_product_list(self):
        self.open_delete_confirmation()

        self.app.button(
            key=f"view_product_selector_confirm_delete_{self.product.id}"
        ).click().run()

        self.assertIsNone(get_product(self.product.id, self.database_path))
        self.assertEqual(self.app.radio[0].value, "View Products")
        self.assertEqual(
            [message.value for message in self.app.success],
            [
                f'"{self.product.name}" (product ID {self.product.id}) '
                "was permanently deleted."
            ],
        )
        self.assertEqual(
            [message.value for message in self.app.info],
            ["No products have been saved yet."],
        )

    def test_already_deleted_product_is_handled_without_repeating_delete(self):
        self.open_delete_confirmation()
        self.execute_database_sql(
            """
            CREATE TRIGGER ignore_repeated_product_delete
            BEFORE DELETE ON products
            BEGIN
                SELECT RAISE(IGNORE);
            END
            """
        )

        self.app.button(
            key=f"view_product_selector_confirm_delete_{self.product.id}"
        ).click().run()

        self.assertIsNotNone(get_product(self.product.id, self.database_path))
        self.assertIn(
            f'"{self.product.name}" (product ID {self.product.id}) '
            "was already deleted.",
            [message.value for message in self.app.warning],
        )
        self.assertEqual(
            self.app.session_state["view_product_selector_action_mode"],
            "detail",
        )
        self.assertIsNotNone(
            self.app.button(
                key=f"view_product_selector_delete_action_{self.product.id}"
            )
        )

    def test_database_error_during_delete_keeps_confirmation_safe(self):
        self.open_delete_confirmation()
        self.execute_database_sql(
            """
            CREATE TRIGGER fail_product_delete
            BEFORE DELETE ON products
            BEGIN
                SELECT RAISE(ABORT, 'temporary delete failure');
            END
            """
        )

        self.app.button(
            key=f"view_product_selector_confirm_delete_{self.product.id}"
        ).click().run()

        self.assertEqual(list(self.app.exception), [])
        self.assertIn(
            "Product data could not be deleted. "
            "Please check the local database and try again.",
            [message.value for message in self.app.error],
        )
        self.assertIsNotNone(get_product(self.product.id, self.database_path))
        self.assertIsNotNone(
            self.app.button(
                key=f"view_product_selector_confirm_delete_{self.product.id}"
            )
        )


class Phase4WorkflowRegressionTests(StreamlitWorkflowTestCase):
    def test_dashboard_create_list_detail_and_search_remain_operational(self):
        metric_values = {metric.label: metric.value for metric in self.app.metric}
        self.assertEqual(metric_values["Total products"], "1")
        self.assertEqual(metric_values["Active products"], "1")

        self.app.radio[0].set_value("Create Product").run()
        self.app.text_input(key="create_product_name").set_value(
            "Regression Product"
        )
        self.app.text_area(key="create_product_description").set_value(
            "Regression description"
        )
        self.app.text_area(key="create_product_target_users").set_value(
            "Regression users"
        )
        self.app.text_area(key="create_product_business_goal").set_value(
            "Regression goal"
        )
        self.app.button(
            key="FormSubmitter:create_product_form-Create product"
        ).click().run()
        self.assertIn(
            '"Regression Product" was created successfully as product ID 2.',
            [message.value for message in self.app.success],
        )
        self.assertEqual(len(list_products(self.database_path)), 2)

        self.app.radio[0].set_value("View Products").run()
        self.assertEqual(len(self.app.dataframe), 1)
        self.app.selectbox(key="view_product_selector").set_value(2).run()
        detail_text = "\n".join(
            element.value for element in self.app.markdown
        )
        self.assertIn("**Description**", detail_text)
        self.assertIn("**Target users**", detail_text)

        self.app.radio[0].set_value("Search Products").run()
        self.app.text_input[0].set_value("Regression description").run()
        self.assertIn(
            '1 result for "Regression description"',
            [message.value for message in self.app.markdown],
        )
        self.assertEqual(
            self.app.selectbox(key="search_product_selector").value,
            2,
        )


if __name__ == "__main__":
    unittest.main()
