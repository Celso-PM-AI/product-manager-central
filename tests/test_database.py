"""Isolated tests for the Phase 3 SQLite database layer."""

import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.database import (
    CANONICAL_COLUMNS,
    SCHEMA_CANONICAL,
    SCHEMA_LEGACY,
    SCHEMA_MISSING,
    SCHEMA_UNKNOWN,
    DatabaseSchemaError,
    MigrationVerificationError,
    ProductValidationError,
    create_product,
    delete_product,
    detect_database_schema,
    get_dashboard_metrics,
    get_product,
    initialize_database,
    list_products,
    load_products,
    migrate_legacy_database,
    save_product,
    search_products,
    update_product,
)
from src.models import ProductStatus


LEGACY_CREATE_SQL = """
    CREATE TABLE products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        product_idea TEXT NOT NULL,
        target_user TEXT NOT NULL,
        business_goal TEXT NOT NULL,
        date_created TEXT NOT NULL
    )
"""

LEGACY_ROW = (
    1,
    "Product Manager Central",
    "An AI-assisted product management workspace.",
    "Product managers",
    "Improve product planning and decisions.",
    "2026-07-19 10:03:17",
)


def valid_product_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "name": "Product Manager Central",
        "description": "A workspace for product managers.",
        "target_users": "Product managers",
        "business_goal": "Improve product planning.",
        "status": "discovery",
    }
    data.update(overrides)
    return data


def create_legacy_database(
    database_path: Path,
    rows: list[tuple[object, ...]] | None = None,
) -> None:
    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.execute(LEGACY_CREATE_SQL)
        legacy_rows = [LEGACY_ROW] if rows is None else rows
        for row in legacy_rows:
            connection.execute(
                """
                INSERT INTO products (
                    id,
                    product_name,
                    product_idea,
                    target_user,
                    business_goal,
                    date_created
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                row,
            )


def table_columns(database_path: Path) -> tuple[str, ...]:
    with closing(sqlite3.connect(database_path)) as connection, connection:
        return tuple(
            row[1] for row in connection.execute("PRAGMA table_info(products)")
        )


def database_sha256(database_path: Path) -> str:
    return hashlib.sha256(database_path.read_bytes()).hexdigest()


def insert_canonical_record(
    database_path: Path,
    *,
    name: str,
    status: str = "discovery",
    description: str = "Description",
    target_users: str = "Target users",
    business_goal: str = "Business goal",
    customer_problem: str | None = None,
    product_strategy: str | None = None,
    notes: str | None = None,
    created_at: str = "2026-07-01T00:00:00.000000Z",
    updated_at: str = "2026-07-01T00:00:00.000000Z",
) -> int:
    with closing(sqlite3.connect(database_path)) as connection, connection:
        cursor = connection.execute(
            """
            INSERT INTO products (
                name,
                description,
                target_users,
                business_goal,
                status,
                customer_problem,
                product_strategy,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                description,
                target_users,
                business_goal,
                status,
                customer_problem,
                product_strategy,
                notes,
                created_at,
                updated_at,
            ),
        )
        return int(cursor.lastrowid)


class TemporaryDatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = (
            Path(self.temporary_directory.name) / "temporary-test.db"
        )


class DatabaseInitializationTests(TemporaryDatabaseTestCase):
    def test_detect_missing_database_does_not_create_a_file(self):
        self.assertEqual(
            detect_database_schema(self.database_path),
            SCHEMA_MISSING,
        )
        self.assertFalse(self.database_path.exists())

    def test_initialize_empty_database_creates_canonical_schema(self):
        initialize_database(self.database_path)

        self.assertEqual(
            detect_database_schema(self.database_path),
            SCHEMA_CANONICAL,
        )
        self.assertEqual(table_columns(self.database_path), CANONICAL_COLUMNS)

    def test_repeated_initialization_is_safe_and_does_not_add_rows(self):
        initialize_database(self.database_path)
        first_hash = database_sha256(self.database_path)

        initialize_database(self.database_path)

        self.assertEqual(list_products(self.database_path), [])
        self.assertEqual(first_hash, database_sha256(self.database_path))

    def test_initialize_never_automatically_migrates_legacy_schema(self):
        create_legacy_database(self.database_path)
        before = database_sha256(self.database_path)

        initialize_database(self.database_path)

        self.assertEqual(
            detect_database_schema(self.database_path),
            SCHEMA_LEGACY,
        )
        self.assertEqual(table_columns(self.database_path), tuple(
            (
                "id",
                "product_name",
                "product_idea",
                "target_user",
                "business_goal",
                "date_created",
            )
        ))
        self.assertEqual(before, database_sha256(self.database_path))

    def test_unknown_schema_is_rejected_without_modification(self):
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute(
                "CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)"
            )
        before = database_sha256(self.database_path)

        self.assertEqual(
            detect_database_schema(self.database_path),
            SCHEMA_UNKNOWN,
        )
        with self.assertRaises(DatabaseSchemaError):
            initialize_database(self.database_path)

        self.assertEqual(before, database_sha256(self.database_path))


class CanonicalCrudTests(TemporaryDatabaseTestCase):
    def setUp(self):
        super().setUp()
        initialize_database(self.database_path)

    def test_empty_list(self):
        self.assertEqual(list_products(self.database_path), [])

    def test_create_and_retrieve_complete_product(self):
        data = valid_product_data(
            status=ProductStatus.PLANNING,
            customer_problem="Information is fragmented.",
            product_strategy="Centralize product knowledge.",
            notes="Interview product managers.",
        )

        product = create_product(data, self.database_path)
        retrieved = get_product(product.id, self.database_path)

        self.assertEqual(retrieved, product)
        self.assertIs(product.status, ProductStatus.PLANNING)
        self.assertEqual(product.customer_problem, data["customer_problem"])
        self.assertEqual(product.created_at, product.updated_at)
        self.assertTrue(product.created_at.endswith("Z"))

    def test_create_with_optional_fields_omitted_stores_nulls(self):
        product = create_product(valid_product_data(), self.database_path)

        self.assertIsNone(product.customer_problem)
        self.assertIsNone(product.product_strategy)
        self.assertIsNone(product.notes)

    def test_get_missing_product_returns_none(self):
        self.assertIsNone(get_product(999, self.database_path))

    def test_duplicate_names_are_allowed(self):
        first = create_product(valid_product_data(), self.database_path)
        second = create_product(valid_product_data(), self.database_path)

        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.name, second.name)

    def test_list_products_uses_descending_id_order(self):
        first = create_product(
            valid_product_data(name="First"),
            self.database_path,
        )
        second = create_product(
            valid_product_data(name="Second"),
            self.database_path,
        )

        products = list_products(self.database_path)

        self.assertEqual([product.id for product in products], [second.id, first.id])

    def test_create_rejects_invalid_required_data(self):
        with self.assertRaises(ProductValidationError) as context:
            create_product(
                valid_product_data(name=" "),
                self.database_path,
            )

        self.assertIn("name", context.exception.errors)

    def test_create_rejects_invalid_status(self):
        with self.assertRaises(ProductValidationError) as context:
            create_product(
                valid_product_data(status="Discovery"),
                self.database_path,
            )

        self.assertIn("status", context.exception.errors)

    def test_create_rejects_system_managed_and_unknown_fields(self):
        data = valid_product_data(id=1, unexpected="value")

        with self.assertRaises(ProductValidationError) as context:
            create_product(data, self.database_path)

        self.assertEqual(
            set(context.exception.errors),
            {"id", "unexpected"},
        )

    def test_partial_update_preserves_unspecified_fields(self):
        with patch(
            "src.database._utc_now",
            return_value="2026-07-01T00:00:00.000000Z",
        ):
            original = create_product(
                valid_product_data(
                    customer_problem="Original problem",
                    notes="Original notes",
                ),
                self.database_path,
            )

        with patch(
            "src.database._utc_now",
            return_value="2026-07-02T00:00:00.000000Z",
        ):
            updated = update_product(
                original.id,
                {"name": "Updated name"},
                self.database_path,
            )

        self.assertEqual(updated.name, "Updated name")
        self.assertEqual(updated.description, original.description)
        self.assertEqual(updated.customer_problem, "Original problem")
        self.assertEqual(updated.notes, "Original notes")
        self.assertEqual(updated.created_at, original.created_at)
        self.assertEqual(updated.updated_at, "2026-07-02T00:00:00.000000Z")

    def test_update_can_change_every_editable_field(self):
        with patch(
            "src.database._utc_now",
            return_value="2026-07-01T00:00:00.000000Z",
        ):
            original = create_product(valid_product_data(), self.database_path)
        updates = valid_product_data(
            name="Updated",
            description="Updated description",
            target_users="Product leaders",
            business_goal="Updated goal",
            status=ProductStatus.LAUNCHED,
            customer_problem="Updated problem",
            product_strategy="Updated strategy",
            notes="Updated notes",
        )

        with patch(
            "src.database._utc_now",
            return_value="2026-07-02T00:00:00.000000Z",
        ):
            updated = update_product(
                original.id,
                updates,
                self.database_path,
            )

        self.assertEqual(updated.id, original.id)
        self.assertEqual(updated.name, "Updated")
        self.assertEqual(updated.description, "Updated description")
        self.assertEqual(updated.target_users, "Product leaders")
        self.assertEqual(updated.business_goal, "Updated goal")
        self.assertIs(updated.status, ProductStatus.LAUNCHED)
        self.assertEqual(updated.customer_problem, "Updated problem")
        self.assertEqual(updated.product_strategy, "Updated strategy")
        self.assertEqual(updated.notes, "Updated notes")
        self.assertEqual(updated.created_at, original.created_at)
        self.assertEqual(updated.created_at, "2026-07-01T00:00:00.000000Z")
        self.assertEqual(updated.updated_at, "2026-07-02T00:00:00.000000Z")

    def test_invalid_update_does_not_change_any_stored_value(self):
        original = create_product(
            valid_product_data(
                customer_problem="Original problem",
                product_strategy="Original strategy",
                notes="Original notes",
            ),
            self.database_path,
        )

        with self.assertRaises(ProductValidationError):
            update_product(
                original.id,
                {
                    "name": " ",
                    "description": "Changed description",
                    "notes": "Changed notes",
                },
                self.database_path,
            )

        self.assertEqual(
            get_product(original.id, self.database_path),
            original,
        )

    def test_update_none_explicitly_clears_optional_field(self):
        product = create_product(
            valid_product_data(notes="Remove this"),
            self.database_path,
        )

        updated = update_product(
            product.id,
            {"notes": None},
            self.database_path,
        )

        self.assertIsNone(updated.notes)

    def test_empty_update_is_a_no_op(self):
        product = create_product(valid_product_data(), self.database_path)

        updated = update_product(product.id, {}, self.database_path)

        self.assertEqual(updated, product)

    def test_update_missing_product_returns_none(self):
        self.assertIsNone(
            update_product(999, {"name": "Missing"}, self.database_path)
        )

    def test_update_rejects_invalid_required_status_system_and_unknown_data(self):
        product = create_product(valid_product_data(), self.database_path)
        invalid_updates = (
            ({"name": " "}, "name"),
            ({"status": "Discovery"}, "status"),
            ({"id": 2}, "id"),
            ({"unexpected": "value"}, "unexpected"),
        )

        for updates, field in invalid_updates:
            with self.subTest(field=field):
                with self.assertRaises(ProductValidationError) as context:
                    update_product(product.id, updates, self.database_path)
                self.assertIn(field, context.exception.errors)

    def test_delete_existing_and_missing_product(self):
        product = create_product(valid_product_data(), self.database_path)

        self.assertTrue(delete_product(product.id, self.database_path))
        self.assertFalse(delete_product(product.id, self.database_path))
        self.assertIsNone(get_product(product.id, self.database_path))

    def test_delete_uses_id_when_names_are_duplicates(self):
        first = create_product(valid_product_data(), self.database_path)
        second = create_product(valid_product_data(), self.database_path)

        self.assertTrue(delete_product(first.id, self.database_path))
        self.assertIsNone(get_product(first.id, self.database_path))
        self.assertIsNotNone(get_product(second.id, self.database_path))


class SearchTests(TemporaryDatabaseTestCase):
    def setUp(self):
        super().setUp()
        initialize_database(self.database_path)
        self.product = create_product(
            valid_product_data(
                name="Atlas",
                description="Manager's research workspace",
                target_users="Portfolio leaders",
                business_goal="Reduce decision latency",
                customer_problem="Scattered evidence",
                product_strategy="Unify planning",
                notes="Special 100%_Complete\\Path",
            ),
            self.database_path,
        )
        self.other = create_product(
            valid_product_data(
                name="Beacon",
                description="Plain description",
                target_users="Delivery teams",
                business_goal="Improve delivery",
            ),
            self.database_path,
        )

    def test_searches_every_approved_text_field(self):
        queries = (
            "Atlas",
            "research workspace",
            "Portfolio leaders",
            "decision latency",
            "Scattered evidence",
            "Unify planning",
            "Complete",
        )

        for query in queries:
            with self.subTest(query=query):
                self.assertEqual(
                    [product.id for product in search_products(
                        query,
                        self.database_path,
                    )],
                    [self.product.id],
                )

    def test_search_is_case_insensitive(self):
        results = search_products("aTlAs", self.database_path)

        self.assertEqual([product.id for product in results], [self.product.id])

    def test_empty_search_returns_normal_list(self):
        self.assertEqual(
            search_products("  ", self.database_path),
            list_products(self.database_path),
        )

    def test_search_returns_empty_list_when_nothing_matches(self):
        self.assertEqual(search_products("not present", self.database_path), [])

    def test_search_handles_apostrophes_safely(self):
        results = search_products("Manager's", self.database_path)

        self.assertEqual([product.id for product in results], [self.product.id])

    def test_percent_underscore_and_escape_are_literal(self):
        for query in ("%", "_", "\\"):
            with self.subTest(query=query):
                results = search_products(query, self.database_path)
                self.assertEqual(
                    [product.id for product in results],
                    [self.product.id],
                )


class DatabaseConstraintTests(TemporaryDatabaseTestCase):
    def setUp(self):
        super().setUp()
        initialize_database(self.database_path)

    def _base_values(self) -> list[object]:
        return [
            "Name",
            "Description",
            "Target users",
            "Business goal",
            "discovery",
            None,
            None,
            None,
            "2026-07-01T00:00:00Z",
            "2026-07-01T00:00:00Z",
        ]

    def _insert_values(self, values: list[object]) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute(
                """
                INSERT INTO products (
                    name,
                    description,
                    target_users,
                    business_goal,
                    status,
                    customer_problem,
                    product_strategy,
                    notes,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )

    def test_required_and_optional_constraints_reject_invalid_values(self):
        invalid_cases = (
            (0, "   "),
            (0, "x" * 121),
            (1, "x" * 2_001),
            (2, "x" * 1_001),
            (3, "x" * 2_001),
            (4, "invalid"),
            (5, "   "),
            (5, "x" * 2_001),
            (6, "x" * 3_001),
            (7, "x" * 5_001),
            (8, None),
            (8, "   "),
            (9, None),
            (9, "   "),
        )

        for index, value in invalid_cases:
            with self.subTest(index=index, value=repr(value)):
                values = self._base_values()
                values[index] = value
                with self.assertRaises(sqlite3.IntegrityError):
                    self._insert_values(values)


class DashboardMetricTests(TemporaryDatabaseTestCase):
    def setUp(self):
        super().setUp()
        initialize_database(self.database_path)
        self.reference_time = datetime(
            2026,
            7,
            27,
            12,
            0,
            0,
            tzinfo=timezone.utc,
        )

    def test_empty_database_metrics_are_zero(self):
        self.assertEqual(
            get_dashboard_metrics(
                self.database_path,
                now=self.reference_time,
            ),
            {
                "total_products": 0,
                "active_products": 0,
                "launched_products": 0,
                "recently_updated_products": 0,
            },
        )

    def test_metrics_include_both_supported_timestamp_formats(self):
        threshold = "2026-06-27T12:00:00Z"
        insert_canonical_record(
            self.database_path,
            name="UTC boundary",
            status="launched",
            updated_at=threshold,
        )
        insert_canonical_record(
            self.database_path,
            name="UTC old",
            status="archived",
            updated_at="2026-06-27T11:59:59Z",
        )
        insert_canonical_record(
            self.database_path,
            name="Legacy recent",
            status="planning",
            created_at="2026-07-19 10:03:17",
            updated_at="2026-07-19 10:03:17",
        )
        insert_canonical_record(
            self.database_path,
            name="Legacy old",
            status="idea",
            created_at="2026-06-01 10:03:17",
            updated_at="2026-06-01 10:03:17",
        )

        metrics = get_dashboard_metrics(
            self.database_path,
            now=self.reference_time,
        )

        self.assertEqual(
            metrics,
            {
                "total_products": 4,
                "active_products": 3,
                "launched_products": 1,
                "recently_updated_products": 2,
            },
        )

    def test_metrics_change_after_create_update_and_delete(self):
        with patch(
            "src.database._utc_now",
            return_value="2026-07-27T11:00:00.000000Z",
        ):
            product = create_product(
                valid_product_data(status="planning"),
                self.database_path,
            )

        initial = get_dashboard_metrics(
            self.database_path,
            now=self.reference_time,
        )
        self.assertEqual(initial["active_products"], 1)
        self.assertEqual(initial["launched_products"], 0)
        self.assertEqual(initial["recently_updated_products"], 1)

        update_product(
            product.id,
            {"status": "launched"},
            self.database_path,
        )
        updated = get_dashboard_metrics(
            self.database_path,
            now=self.reference_time,
        )
        self.assertEqual(updated["launched_products"], 1)

        delete_product(product.id, self.database_path)
        deleted = get_dashboard_metrics(
            self.database_path,
            now=self.reference_time,
        )
        self.assertEqual(deleted["total_products"], 0)

    def test_metrics_require_timezone_aware_reference_time(self):
        with self.assertRaises(ValueError):
            get_dashboard_metrics(
                self.database_path,
                now=datetime(2026, 7, 27, 12, 0, 0),
            )


class MigrationTests(TemporaryDatabaseTestCase):
    def setUp(self):
        super().setUp()
        create_legacy_database(self.database_path)

    def test_migration_preserves_record_and_applies_defaults(self):
        migrated = migrate_legacy_database(self.database_path)

        self.assertTrue(migrated)
        self.assertEqual(
            detect_database_schema(self.database_path),
            SCHEMA_CANONICAL,
        )
        self.assertEqual(table_columns(self.database_path), CANONICAL_COLUMNS)

        product = get_product(1, self.database_path)
        self.assertEqual(product.id, LEGACY_ROW[0])
        self.assertEqual(product.name, LEGACY_ROW[1])
        self.assertEqual(product.description, LEGACY_ROW[2])
        self.assertEqual(product.target_users, LEGACY_ROW[3])
        self.assertEqual(product.business_goal, LEGACY_ROW[4])
        self.assertEqual(product.created_at, LEGACY_ROW[5])
        self.assertEqual(product.updated_at, LEGACY_ROW[5])
        self.assertIs(product.status, ProductStatus.DISCOVERY)
        self.assertIsNone(product.customer_problem)
        self.assertIsNone(product.product_strategy)
        self.assertIsNone(product.notes)

        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            self.assertEqual(
                connection.execute("PRAGMA integrity_check").fetchone()[0],
                "ok",
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM products").fetchone()[0],
                1,
            )

    def test_repeated_migration_and_initialization_are_safe_no_ops(self):
        self.assertTrue(migrate_legacy_database(self.database_path))
        product_before = get_product(1, self.database_path)

        self.assertFalse(migrate_legacy_database(self.database_path))
        initialize_database(self.database_path)
        initialize_database(self.database_path)

        self.assertEqual(list_products(self.database_path), [product_before])

    def test_migration_preserves_autoincrement_sequence(self):
        migrate_legacy_database(self.database_path)

        created = create_product(
            valid_product_data(name="Second"),
            self.database_path,
        )

        self.assertEqual(created.id, 2)

    def test_unknown_partial_schema_is_rejected_without_modification(self):
        self.database_path.unlink()
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute(
                """
                CREATE TABLE products (
                    id INTEGER PRIMARY KEY,
                    product_name TEXT NOT NULL
                )
                """
            )
        before = database_sha256(self.database_path)

        with self.assertRaises(DatabaseSchemaError):
            migrate_legacy_database(self.database_path)

        self.assertEqual(before, database_sha256(self.database_path))
        self.assertEqual(
            detect_database_schema(self.database_path),
            SCHEMA_UNKNOWN,
        )

    def test_extra_user_table_causes_rejection_without_modification(self):
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute("CREATE TABLE unexpected (id INTEGER)")
        before = database_sha256(self.database_path)

        with self.assertRaises(DatabaseSchemaError):
            migrate_legacy_database(self.database_path)

        self.assertEqual(before, database_sha256(self.database_path))

    def test_invalid_legacy_data_rolls_back_completely(self):
        self.database_path.unlink()
        invalid_row = (
            1,
            "   ",
            "Description",
            "Target users",
            "Business goal",
            "2026-07-19 10:03:17",
        )
        create_legacy_database(self.database_path, [invalid_row])

        with self.assertRaises(sqlite3.IntegrityError):
            migrate_legacy_database(self.database_path)

        self.assertEqual(
            detect_database_schema(self.database_path),
            SCHEMA_LEGACY,
        )
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            self.assertEqual(
                connection.execute(
                    "SELECT product_name FROM products WHERE id = 1"
                ).fetchone()[0],
                "   ",
            )
            tables = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_schema
                    WHERE type = 'table'
                      AND name NOT LIKE 'sqlite_%'
                    """
                )
            }
        self.assertEqual(tables, {"products"})

    def test_verification_failure_rolls_back_completely(self):
        with patch(
            "src.database._integrity_is_ok",
            side_effect=[True, False],
        ):
            with self.assertRaises(MigrationVerificationError):
                migrate_legacy_database(self.database_path)

        self.assertEqual(
            detect_database_schema(self.database_path),
            SCHEMA_LEGACY,
        )
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    product_name,
                    product_idea,
                    target_user,
                    business_goal,
                    date_created
                FROM products
                """
            ).fetchone()
        self.assertEqual(tuple(row), LEGACY_ROW)

    def test_already_canonical_database_is_a_no_op(self):
        self.database_path.unlink()
        initialize_database(self.database_path)
        before = database_sha256(self.database_path)

        self.assertFalse(migrate_legacy_database(self.database_path))

        self.assertEqual(before, database_sha256(self.database_path))


class CompatibilityWrapperTests(TemporaryDatabaseTestCase):
    EXPECTED_COLUMNS = [
        "ID",
        "Product Name",
        "Product Idea",
        "Target User",
        "Business Goal",
        "Date Created",
    ]

    def test_save_and_load_preserve_legacy_app_contract(self):
        create_legacy_database(self.database_path, [])

        save_product(
            "  Legacy Name  ",
            "  Legacy Idea  ",
            "  Legacy User  ",
            "  Legacy Goal  ",
            self.database_path,
        )
        frame = load_products(self.database_path)

        self.assertEqual(list(frame.columns), self.EXPECTED_COLUMNS)
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.iloc[0]["Product Name"], "Legacy Name")
        self.assertEqual(frame.iloc[0]["Product Idea"], "Legacy Idea")
        self.assertEqual(frame.iloc[0]["Target User"], "Legacy User")
        self.assertEqual(frame.iloc[0]["Business Goal"], "Legacy Goal")
        self.assertEqual(
            detect_database_schema(self.database_path),
            SCHEMA_LEGACY,
        )

    def test_save_and_load_preserve_app_contract_after_migration(self):
        initialize_database(self.database_path)

        save_product(
            "  Canonical Name  ",
            "  Canonical Idea  ",
            "  Canonical User  ",
            "  Canonical Goal  ",
            self.database_path,
        )
        frame = load_products(self.database_path)
        product = get_product(int(frame.iloc[0]["ID"]), self.database_path)

        self.assertEqual(list(frame.columns), self.EXPECTED_COLUMNS)
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.iloc[0]["Product Name"], "Canonical Name")
        self.assertIs(product.status, ProductStatus.DISCOVERY)


if __name__ == "__main__":
    unittest.main()
