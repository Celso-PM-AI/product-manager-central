"""SQLite persistence, migration, and compatibility helpers for PMC."""

import os
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final

import pandas as pd

from src.document_templates import document_template
from src.models import (
    DEFAULT_PRODUCT_STATUS,
    DocumentStatus,
    DocumentType,
    Product,
    ProductDocument,
    ProductStatus,
    RetrievableDocumentSection,
)
from src.validation import (
    DocumentValidationResult,
    ValidationResult,
    validate_document,
    validate_product,
)


DATABASE_FILE = "data/pmc.db"

SCHEMA_MISSING: Final[str] = "missing"
SCHEMA_LEGACY: Final[str] = "legacy"
SCHEMA_PRODUCT_ONLY: Final[str] = "canonical_product_only"
SCHEMA_CANONICAL: Final[str] = "canonical"
SCHEMA_UNKNOWN: Final[str] = "unknown"

LEGACY_COLUMNS: Final[tuple[str, ...]] = (
    "id",
    "product_name",
    "product_idea",
    "target_user",
    "business_goal",
    "date_created",
)

CANONICAL_COLUMNS: Final[tuple[str, ...]] = (
    "id",
    "name",
    "description",
    "target_users",
    "business_goal",
    "status",
    "customer_problem",
    "product_strategy",
    "notes",
    "created_at",
    "updated_at",
)

DOCUMENT_COLUMNS: Final[tuple[str, ...]] = (
    "id",
    "product_id",
    "document_type",
    "title",
    "version",
    "document_status",
    "created_at",
    "updated_at",
)

DOCUMENT_SECTION_COLUMNS: Final[tuple[str, ...]] = (
    "document_id",
    "section_key",
    "content",
)

LEGACY_COLUMN_SIGNATURE: Final[tuple[tuple[object, ...], ...]] = (
    ("id", "INTEGER", 0, None, 1),
    ("product_name", "TEXT", 1, None, 0),
    ("product_idea", "TEXT", 1, None, 0),
    ("target_user", "TEXT", 1, None, 0),
    ("business_goal", "TEXT", 1, None, 0),
    ("date_created", "TEXT", 1, None, 0),
)

MIGRATION_TABLE_NAME: Final[str] = "products__migration"
LEGACY_TABLE_NAME: Final[str] = "products__legacy"


class DatabaseSchemaError(RuntimeError):
    """Raised when a database does not have a supported schema."""


class MigrationVerificationError(RuntimeError):
    """Raised when migrated records do not exactly match their source."""


class ProductValidationError(ValueError):
    """Raised when canonical product data fails Phase 2 validation."""

    def __init__(self, errors: Mapping[str, str]):
        self.errors = dict(errors)
        super().__init__(f"Invalid product data: {self.errors}")


class DocumentValidationError(ValueError):
    """Raised when document data fails centralized validation."""

    def __init__(self, errors: Mapping[str, str]):
        self.errors = dict(errors)
        super().__init__(f"Invalid document data: {self.errors}")


class DocumentAssociationError(ValueError):
    """Raised when a document references a missing product."""


def _database_path(database_path: str | os.PathLike[str]) -> Path:
    return Path(database_path)


def _ensure_parent_directory(database_path: str | os.PathLike[str]) -> None:
    path = _database_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)


def _connect(
    database_path: str | os.PathLike[str],
    *,
    isolation_level: str | None = "",
) -> sqlite3.Connection:
    connection = sqlite3.connect(
        _database_path(database_path),
        isolation_level=isolation_level,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def _open_connection(
    database_path: str | os.PathLike[str],
    *,
    isolation_level: str | None = "",
) -> Iterator[sqlite3.Connection]:
    """Open a database connection and always close it."""

    connection = _connect(database_path, isolation_level=isolation_level)
    try:
        yield connection
        if isolation_level is not None:
            connection.commit()
    except Exception:
        if isolation_level is not None:
            connection.rollback()
        raise
    finally:
        connection.close()


def _connect_read_only(
    database_path: str | os.PathLike[str],
) -> sqlite3.Connection:
    uri = f"{_database_path(database_path).resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def _open_read_only(
    database_path: str | os.PathLike[str],
) -> Iterator[sqlite3.Connection]:
    """Open a read-only database connection and always close it."""

    connection = _connect_read_only(database_path)
    try:
        yield connection
    finally:
        connection.close()


def _user_tables(connection: sqlite3.Connection) -> tuple[str, ...]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_schema
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return tuple(row["name"] for row in rows)


def _table_info(
    connection: sqlite3.Connection,
    table_name: str = "products",
) -> tuple[sqlite3.Row, ...]:
    if table_name not in {
        "products",
        "documents",
        "document_sections",
        MIGRATION_TABLE_NAME,
        LEGACY_TABLE_NAME,
    }:
        raise ValueError("Unsupported internal table name.")
    return tuple(connection.execute(f'PRAGMA table_info("{table_name}")'))


def _legacy_signature_is_exact(table_info: tuple[sqlite3.Row, ...]) -> bool:
    signature = tuple(
        (
            row["name"],
            str(row["type"]).upper(),
            row["notnull"],
            row["dflt_value"],
            row["pk"],
        )
        for row in table_info
    )
    return signature == LEGACY_COLUMN_SIGNATURE


def _detect_schema(connection: sqlite3.Connection) -> str:
    tables = _user_tables(connection)
    if not tables:
        return SCHEMA_MISSING
    if tables == ("products",):
        table_info = _table_info(connection)
        columns = tuple(row["name"] for row in table_info)
        if columns == CANONICAL_COLUMNS:
            return SCHEMA_PRODUCT_ONLY
        if columns == LEGACY_COLUMNS and _legacy_signature_is_exact(table_info):
            return SCHEMA_LEGACY
        return SCHEMA_UNKNOWN

    if tables == ("document_sections", "documents", "products"):
        product_columns = tuple(row["name"] for row in _table_info(connection))
        document_columns = tuple(
            row["name"] for row in _table_info(connection, "documents")
        )
        section_columns = tuple(
            row["name"] for row in _table_info(connection, "document_sections")
        )
        if (
            product_columns == CANONICAL_COLUMNS
            and document_columns == DOCUMENT_COLUMNS
            and section_columns == DOCUMENT_SECTION_COLUMNS
        ):
            return SCHEMA_CANONICAL
    return SCHEMA_UNKNOWN


def detect_database_schema(
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> str:
    """Return the recognized schema state without changing data."""

    path = _database_path(database_path)
    if not path.exists():
        return SCHEMA_MISSING

    with _open_read_only(path) as connection:
        return _detect_schema(connection)


def _canonical_table_sql(table_name: str) -> str:
    if table_name not in {"products", MIGRATION_TABLE_NAME}:
        raise ValueError("Unsupported internal table name.")

    approved_statuses = ", ".join(
        f"'{status.value}'" for status in ProductStatus
    )
    return f"""
        CREATE TABLE "{table_name}" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
                CHECK (length(trim(name)) BETWEEN 1 AND 120),
            description TEXT NOT NULL
                CHECK (length(trim(description)) BETWEEN 1 AND 2000),
            target_users TEXT NOT NULL
                CHECK (length(trim(target_users)) BETWEEN 1 AND 1000),
            business_goal TEXT NOT NULL
                CHECK (length(trim(business_goal)) BETWEEN 1 AND 2000),
            status TEXT NOT NULL DEFAULT 'discovery'
                CHECK (status IN ({approved_statuses})),
            customer_problem TEXT
                CHECK (
                    customer_problem IS NULL
                    OR length(trim(customer_problem)) BETWEEN 1 AND 2000
                ),
            product_strategy TEXT
                CHECK (
                    product_strategy IS NULL
                    OR length(trim(product_strategy)) BETWEEN 1 AND 3000
                ),
            notes TEXT
                CHECK (
                    notes IS NULL
                    OR length(trim(notes)) BETWEEN 1 AND 5000
                ),
            created_at TEXT NOT NULL
                CHECK (length(trim(created_at)) > 0),
            updated_at TEXT NOT NULL
                CHECK (length(trim(updated_at)) > 0)
        )
    """


def _create_canonical_table(
    connection: sqlite3.Connection,
    table_name: str = "products",
) -> None:
    connection.execute(_canonical_table_sql(table_name))


def _create_document_tables(connection: sqlite3.Connection) -> None:
    """Add the normalized Phase 8 document schema."""

    connection.execute(
        """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            document_type TEXT NOT NULL
                CHECK (document_type IN ('BRD', 'PRD')),
            title TEXT NOT NULL
                CHECK (length(trim(title)) BETWEEN 1 AND 200),
            version TEXT NOT NULL
                CHECK (length(trim(version)) BETWEEN 1 AND 50),
            document_status TEXT NOT NULL DEFAULT 'draft'
                CHECK (document_status IN ('draft', 'approved')),
            created_at TEXT NOT NULL
                CHECK (length(trim(created_at)) > 0),
            updated_at TEXT NOT NULL
                CHECK (length(trim(updated_at)) > 0),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE document_sections (
            document_id INTEGER NOT NULL,
            section_key TEXT NOT NULL
                CHECK (length(trim(section_key)) > 0),
            content TEXT NOT NULL
                CHECK (length(content) <= 10000),
            PRIMARY KEY (document_id, section_key),
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_documents_product_id
        ON documents (product_id, id DESC)
        """
    )


def _add_document_schema(connection: sqlite3.Connection) -> None:
    """Transactionally add document tables while verifying product rows."""

    before = tuple(
        tuple(row)
        for row in connection.execute(
            "SELECT * FROM products ORDER BY id"
        ).fetchall()
    )
    _create_document_tables(connection)
    after = tuple(
        tuple(row)
        for row in connection.execute(
            "SELECT * FROM products ORDER BY id"
        ).fetchall()
    )
    if after != before:
        raise MigrationVerificationError(
            "Document migration changed existing product data."
        )
    if _detect_schema(connection) != SCHEMA_CANONICAL:
        raise MigrationVerificationError(
            "Document schema verification failed."
        )


def initialize_database(
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> None:
    """Create a canonical empty database without migrating legacy data."""

    _ensure_parent_directory(database_path)

    with _open_connection(database_path) as connection:
        schema = _detect_schema(connection)
        if schema == SCHEMA_MISSING:
            connection.execute("BEGIN IMMEDIATE")
            try:
                _create_canonical_table(connection)
                _create_document_tables(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        elif schema == SCHEMA_PRODUCT_ONLY:
            connection.execute("BEGIN IMMEDIATE")
            try:
                _add_document_schema(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        elif schema in {SCHEMA_LEGACY, SCHEMA_CANONICAL}:
            return
        else:
            raise DatabaseSchemaError(
                "Database schema is neither the known legacy schema "
                "nor the canonical schema."
            )


def _require_canonical_schema(connection: sqlite3.Connection) -> None:
    schema = _detect_schema(connection)
    if schema not in {SCHEMA_PRODUCT_ONLY, SCHEMA_CANONICAL}:
        raise DatabaseSchemaError(
            f"Canonical database schema required; found {schema}."
        )


def _require_document_schema(connection: sqlite3.Connection) -> None:
    schema = _detect_schema(connection)
    if schema != SCHEMA_CANONICAL:
        raise DatabaseSchemaError(
            f"Phase 8 document schema required; found {schema}."
        )


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _legacy_local_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _normalized_or_raise(
    product_data: Mapping[str, object],
) -> ValidationResult:
    result = validate_product(product_data)
    if not result.is_valid:
        raise ProductValidationError(result.errors)
    return result


def _normalized_document_or_raise(
    document_data: Mapping[str, object],
) -> DocumentValidationResult:
    result = validate_document(document_data)
    if not result.is_valid:
        raise DocumentValidationError(result.errors)
    return result


def _row_to_product(row: sqlite3.Row) -> Product:
    return Product(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        target_users=row["target_users"],
        business_goal=row["business_goal"],
        status=ProductStatus(row["status"]),
        customer_problem=row["customer_problem"],
        product_strategy=row["product_strategy"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _select_product_by_id(
    connection: sqlite3.Connection,
    product_id: int,
) -> Product | None:
    row = connection.execute(
        """
        SELECT
            id,
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
        FROM products
        WHERE id = ?
        """,
        (product_id,),
    ).fetchone()
    return _row_to_product(row) if row is not None else None


def create_product(
    product_data: Mapping[str, object],
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> Product:
    """Validate and create one canonical product."""

    result = _normalized_or_raise(product_data)
    data = result.normalized_data
    timestamp = _utc_now()

    with _open_connection(database_path) as connection:
        _require_canonical_schema(connection)
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
                data["name"],
                data["description"],
                data["target_users"],
                data["business_goal"],
                data["status"].value,
                data["customer_problem"],
                data["product_strategy"],
                data["notes"],
                timestamp,
                timestamp,
            ),
        )
        product = _select_product_by_id(connection, cursor.lastrowid)

    if product is None:
        raise RuntimeError("Created product could not be retrieved.")
    return product


def list_products(
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> list[Product]:
    """Return every canonical product in descending ID order."""

    with _open_connection(database_path) as connection:
        _require_canonical_schema(connection)
        rows = connection.execute(
            """
            SELECT
                id,
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
            FROM products
            ORDER BY id DESC
            """
        ).fetchall()
    return [_row_to_product(row) for row in rows]


def get_product(
    product_id: int,
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> Product | None:
    """Return one canonical product, or None when its ID does not exist."""

    with _open_connection(database_path) as connection:
        _require_canonical_schema(connection)
        return _select_product_by_id(connection, product_id)


def _editable_product_data(product: Product) -> dict[str, object]:
    return {
        "name": product.name,
        "description": product.description,
        "target_users": product.target_users,
        "business_goal": product.business_goal,
        "status": product.status,
        "customer_problem": product.customer_problem,
        "product_strategy": product.product_strategy,
        "notes": product.notes,
    }


def update_product(
    product_id: int,
    updates: Mapping[str, object],
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> Product | None:
    """Apply safe partial updates after validating the complete merged record.

    Unspecified editable fields retain their stored values. Supplying None for
    an optional field clears it. An empty update mapping is a no-op.
    """

    supplied_updates = dict(updates)

    with _open_connection(database_path) as connection:
        _require_canonical_schema(connection)
        existing = _select_product_by_id(connection, product_id)
        if existing is None:
            return None
        if not supplied_updates:
            return existing

        merged_data = _editable_product_data(existing)
        merged_data.update(supplied_updates)
        result = _normalized_or_raise(merged_data)
        data = result.normalized_data
        updated_at = _utc_now()

        connection.execute(
            """
            UPDATE products
            SET
                name = ?,
                description = ?,
                target_users = ?,
                business_goal = ?,
                status = ?,
                customer_problem = ?,
                product_strategy = ?,
                notes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                data["name"],
                data["description"],
                data["target_users"],
                data["business_goal"],
                data["status"].value,
                data["customer_problem"],
                data["product_strategy"],
                data["notes"],
                updated_at,
                product_id,
            ),
        )
        return _select_product_by_id(connection, product_id)


def delete_product(
    product_id: int,
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> bool:
    """Permanently delete one canonical product by ID."""

    with _open_connection(database_path) as connection:
        _require_canonical_schema(connection)
        cursor = connection.execute(
            "DELETE FROM products WHERE id = ?",
            (product_id,),
        )
        return cursor.rowcount == 1


def _escape_like(value: str) -> str:
    return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def search_products(
    query: str,
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> list[Product]:
    """Search canonical product text using literal, case-insensitive matching."""

    normalized_query = query.strip()
    if not normalized_query:
        return list_products(database_path)

    pattern = f"%{_escape_like(normalized_query)}%"
    with _open_connection(database_path) as connection:
        _require_canonical_schema(connection)
        rows = connection.execute(
            """
            SELECT
                id,
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
            FROM products
            WHERE name LIKE ? ESCAPE '!' COLLATE NOCASE
               OR description LIKE ? ESCAPE '!' COLLATE NOCASE
               OR target_users LIKE ? ESCAPE '!' COLLATE NOCASE
               OR business_goal LIKE ? ESCAPE '!' COLLATE NOCASE
               OR COALESCE(customer_problem, '') LIKE ? ESCAPE '!' COLLATE NOCASE
               OR COALESCE(product_strategy, '') LIKE ? ESCAPE '!' COLLATE NOCASE
               OR COALESCE(notes, '') LIKE ? ESCAPE '!' COLLATE NOCASE
            ORDER BY id DESC
            """,
            (pattern,) * 7,
        ).fetchall()
    return [_row_to_product(row) for row in rows]


def get_dashboard_metrics(
    database_path: str | os.PathLike[str] = DATABASE_FILE,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Return the four approved dashboard metrics for canonical products."""

    reference_time = now or datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        raise ValueError("Dashboard metric reference time must be timezone-aware.")

    threshold = reference_time.astimezone(timezone.utc) - timedelta(days=30)
    threshold_text = threshold.isoformat().replace("+00:00", "Z")

    with _open_connection(database_path) as connection:
        _require_canonical_schema(connection)
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_products,
                COALESCE(SUM(status <> ?), 0) AS active_products,
                COALESCE(SUM(status = ?), 0) AS launched_products,
                COALESCE(
                    SUM(datetime(updated_at) >= datetime(?)),
                    0
                ) AS recently_updated_products
            FROM products
            """,
            (
                ProductStatus.ARCHIVED.value,
                ProductStatus.LAUNCHED.value,
                threshold_text,
            ),
        ).fetchone()

    return {
        "total_products": int(row["total_products"]),
        "active_products": int(row["active_products"]),
        "launched_products": int(row["launched_products"]),
        "recently_updated_products": int(row["recently_updated_products"]),
    }


def _select_document_sections(
    connection: sqlite3.Connection,
    document_id: int,
) -> dict[str, str]:
    rows = connection.execute(
        """
        SELECT section_key, content
        FROM document_sections
        WHERE document_id = ?
        """,
        (document_id,),
    ).fetchall()
    return {row["section_key"]: row["content"] for row in rows}


def _row_to_document(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
) -> ProductDocument:
    document_id = int(row["id"])
    return ProductDocument(
        id=document_id,
        product_id=row["product_id"],
        document_type=DocumentType(row["document_type"]),
        title=row["title"],
        version=row["version"],
        document_status=DocumentStatus(row["document_status"]),
        sections=_select_document_sections(connection, document_id),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _select_document_by_id(
    connection: sqlite3.Connection,
    document_id: int,
) -> ProductDocument | None:
    row = connection.execute(
        """
        SELECT
            id, product_id, document_type, title, version,
            document_status, created_at, updated_at
        FROM documents
        WHERE id = ?
        """,
        (document_id,),
    ).fetchone()
    return _row_to_document(connection, row) if row is not None else None


def create_document(
    document_data: Mapping[str, object],
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> ProductDocument:
    """Validate and atomically create one product document and its sections."""

    result = _normalized_document_or_raise(document_data)
    data = result.normalized_data
    timestamp = _utc_now()

    with _open_connection(database_path) as connection:
        _require_document_schema(connection)
        product_exists = connection.execute(
            "SELECT 1 FROM products WHERE id = ?",
            (data["product_id"],),
        ).fetchone()
        if product_exists is None:
            raise DocumentAssociationError(
                f"Product ID {data['product_id']} does not exist."
            )

        cursor = connection.execute(
            """
            INSERT INTO documents (
                product_id, document_type, title, version,
                document_status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["product_id"],
                data["document_type"].value,
                data["title"],
                data["version"],
                data["document_status"].value,
                timestamp,
                timestamp,
            ),
        )
        document_id = int(cursor.lastrowid)
        sections = data["sections"]
        connection.executemany(
            """
            INSERT INTO document_sections (document_id, section_key, content)
            VALUES (?, ?, ?)
            """,
            (
                (document_id, definition.key, sections[definition.key])
                for definition in document_template(data["document_type"])
            ),
        )
        document = _select_document_by_id(connection, document_id)

    if document is None:
        raise RuntimeError("Created document could not be retrieved.")
    return document


def get_document(
    document_id: int,
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> ProductDocument | None:
    """Return one document by stable database ID."""

    with _open_connection(database_path) as connection:
        _require_document_schema(connection)
        return _select_document_by_id(connection, document_id)


def list_documents_for_product(
    product_id: int,
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> list[ProductDocument]:
    """Return a product's documents in descending stable-ID order."""

    with _open_connection(database_path) as connection:
        _require_document_schema(connection)
        rows = connection.execute(
            """
            SELECT
                id, product_id, document_type, title, version,
                document_status, created_at, updated_at
            FROM documents
            WHERE product_id = ?
            ORDER BY id DESC
            """,
            (product_id,),
        ).fetchall()
        return [_row_to_document(connection, row) for row in rows]


def count_documents_for_product(
    product_id: int,
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> int:
    """Return the number of documents that product deletion will cascade."""

    with _open_connection(database_path) as connection:
        _require_document_schema(connection)
        row = connection.execute(
            "SELECT COUNT(*) AS document_count FROM documents WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        return int(row["document_count"])


def list_retrievable_document_sections(
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> list[RetrievableDocumentSection]:
    """Return only approved BRD/PRD sections with citation metadata.

    This deterministic, read-only boundary performs no semantic ranking and
    makes no external API calls.
    """

    section_titles = {
        (document_type, definition.key): definition.label
        for document_type in (DocumentType.BRD, DocumentType.PRD)
        for definition in document_template(document_type)
    }
    with _open_read_only(database_path) as connection:
        _require_document_schema(connection)
        rows = connection.execute(
            """
            SELECT
                products.id AS product_id,
                products.name AS product_name,
                documents.id AS document_id,
                documents.title AS document_title,
                documents.document_type,
                document_sections.section_key,
                document_sections.content AS section_content
            FROM document_sections
            INNER JOIN documents
                ON documents.id = document_sections.document_id
            INNER JOIN products
                ON products.id = documents.product_id
            WHERE documents.document_status = ?
              AND documents.document_type IN (?, ?)
            ORDER BY
                products.id,
                documents.id,
                document_sections.section_key
            """,
            (
                DocumentStatus.APPROVED.value,
                DocumentType.BRD.value,
                DocumentType.PRD.value,
            ),
        ).fetchall()

    sections: list[RetrievableDocumentSection] = []
    for row in rows:
        document_type = DocumentType(row["document_type"])
        title = section_titles.get((document_type, row["section_key"]))
        if title is None:
            continue
        sections.append(
            RetrievableDocumentSection(
                product_id=int(row["product_id"]),
                product_name=row["product_name"],
                document_id=int(row["document_id"]),
                document_title=row["document_title"],
                document_type=document_type,
                section_key=row["section_key"],
                section_title=title,
                section_content=row["section_content"],
            )
        )
    return sections


def update_document(
    document_id: int,
    updates: Mapping[str, object],
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> ProductDocument | None:
    """Update editable content by stable document ID."""

    supplied_updates = dict(updates)
    immutable = {"id", "product_id", "document_type", "created_at", "updated_at"}
    invalid = immutable.intersection(supplied_updates)
    if invalid:
        errors = {
            field: f"{field.replace('_', ' ').title()} cannot be changed."
            for field in invalid
        }
        raise DocumentValidationError(errors)

    with _open_connection(database_path) as connection:
        _require_document_schema(connection)
        existing = _select_document_by_id(connection, document_id)
        if existing is None:
            return None
        if not supplied_updates:
            return existing

        sections = dict(existing.sections)
        if "sections" in supplied_updates:
            supplied_sections = supplied_updates.pop("sections")
            if not isinstance(supplied_sections, Mapping):
                raise DocumentValidationError(
                    {"sections": "Document sections must be supplied."}
                )
            sections.update(supplied_sections)

        merged: dict[str, object] = {
            "product_id": existing.product_id,
            "document_type": existing.document_type,
            "title": existing.title,
            "version": existing.version,
            "document_status": existing.document_status,
            "sections": sections,
        }
        merged.update(supplied_updates)
        result = _normalized_document_or_raise(merged)
        data = result.normalized_data
        updated_at = _utc_now()

        connection.execute(
            """
            UPDATE documents
            SET title = ?, version = ?, document_status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                data["title"],
                data["version"],
                data["document_status"].value,
                updated_at,
                document_id,
            ),
        )
        connection.executemany(
            """
            INSERT INTO document_sections (content, document_id, section_key)
            VALUES (?, ?, ?)
            ON CONFLICT (document_id, section_key)
            DO UPDATE SET content = excluded.content
            """,
            (
                (data["sections"][definition.key], document_id, definition.key)
                for definition in document_template(existing.document_type)
            ),
        )
        return _select_document_by_id(connection, document_id)


def migrate_document_database(
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> bool:
    """Add the Phase 8 tables to an exact product-only canonical database."""

    path = _database_path(database_path)
    if not path.exists():
        raise DatabaseSchemaError("Cannot migrate a missing database.")

    with _open_connection(path) as connection:
        schema = _detect_schema(connection)
        if schema == SCHEMA_CANONICAL:
            return False
        if schema != SCHEMA_PRODUCT_ONLY:
            raise DatabaseSchemaError(
                "Document migration requires the product-only canonical schema."
            )
        connection.execute("BEGIN IMMEDIATE")
        try:
            _add_document_schema(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return True


def _integrity_is_ok(connection: sqlite3.Connection) -> bool:
    row = connection.execute("PRAGMA integrity_check").fetchone()
    return row is not None and row[0] == "ok"


def migrate_legacy_database(
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> bool:
    """Transactionally migrate only the exact known legacy schema.

    Return True when migration occurs and False when the database is already
    canonical. Unknown, partial, or invalid legacy schemas are not modified.
    """

    path = _database_path(database_path)
    if not path.exists():
        raise DatabaseSchemaError("Cannot migrate a missing database.")

    connection = _connect(path, isolation_level=None)
    try:
        schema = _detect_schema(connection)
        if schema == SCHEMA_CANONICAL:
            return False
        if schema != SCHEMA_LEGACY:
            raise DatabaseSchemaError(
                "Migration requires the exact known legacy schema."
            )
        if not _integrity_is_ok(connection):
            raise MigrationVerificationError(
                "Legacy database failed its integrity check."
            )

        source_rows = connection.execute(
            """
            SELECT
                id,
                product_name,
                product_idea,
                target_user,
                business_goal,
                date_created
            FROM products
            ORDER BY id
            """
        ).fetchall()

        connection.execute("BEGIN IMMEDIATE")
        try:
            _create_canonical_table(connection, MIGRATION_TABLE_NAME)
            connection.execute(
                f"""
                INSERT INTO "{MIGRATION_TABLE_NAME}" (
                    id,
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
                SELECT
                    id,
                    product_name,
                    product_idea,
                    target_user,
                    business_goal,
                    ?,
                    NULL,
                    NULL,
                    NULL,
                    date_created,
                    date_created
                FROM products
                ORDER BY id
                """,
                (DEFAULT_PRODUCT_STATUS.value,),
            )

            target_rows = connection.execute(
                f"""
                SELECT
                    id,
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
                FROM "{MIGRATION_TABLE_NAME}"
                ORDER BY id
                """
            ).fetchall()

            if len(source_rows) != len(target_rows):
                raise MigrationVerificationError(
                    "Migration changed the product record count."
                )

            for source, target in zip(source_rows, target_rows, strict=True):
                expected = (
                    source["id"],
                    source["product_name"],
                    source["product_idea"],
                    source["target_user"],
                    source["business_goal"],
                    DEFAULT_PRODUCT_STATUS.value,
                    None,
                    None,
                    None,
                    source["date_created"],
                    source["date_created"],
                )
                if tuple(target) != expected:
                    raise MigrationVerificationError(
                        f"Migration verification failed for product {source['id']}."
                    )

            connection.execute(
                f'ALTER TABLE products RENAME TO "{LEGACY_TABLE_NAME}"'
            )
            connection.execute(
                f'ALTER TABLE "{MIGRATION_TABLE_NAME}" RENAME TO products'
            )
            connection.execute(f'DROP TABLE "{LEGACY_TABLE_NAME}"')

            _create_document_tables(connection)

            if _detect_schema(connection) != SCHEMA_CANONICAL:
                raise MigrationVerificationError(
                    "Canonical schema verification failed."
                )
            if not _integrity_is_ok(connection):
                raise MigrationVerificationError(
                    "Migrated database failed its integrity check."
                )

            connection.commit()
        except Exception:
            connection.rollback()
            raise
    finally:
        connection.close()

    return True


def save_product(
    product_name: str,
    product_idea: str,
    target_user: str,
    business_goal: str,
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> None:
    """Preserve the current four-field Streamlit save behavior."""

    schema = detect_database_schema(database_path)
    if schema == SCHEMA_MISSING:
        initialize_database(database_path)
        schema = SCHEMA_CANONICAL

    if schema == SCHEMA_LEGACY:
        with _open_connection(database_path) as connection:
            connection.execute(
                """
                INSERT INTO products (
                    product_name,
                    product_idea,
                    target_user,
                    business_goal,
                    date_created
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    product_name.strip(),
                    product_idea.strip(),
                    target_user.strip(),
                    business_goal.strip(),
                    _legacy_local_now(),
                ),
            )
        return

    if schema in {SCHEMA_PRODUCT_ONLY, SCHEMA_CANONICAL}:
        create_product(
            {
                "name": product_name,
                "description": product_idea,
                "target_users": target_user,
                "business_goal": business_goal,
                "status": DEFAULT_PRODUCT_STATUS,
            },
            database_path,
        )
        return

    raise DatabaseSchemaError("Cannot save to an unknown database schema.")


def load_products(
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> pd.DataFrame:
    """Preserve the DataFrame expected by the current Streamlit app."""

    schema = detect_database_schema(database_path)
    if schema == SCHEMA_MISSING:
        initialize_database(database_path)
        schema = SCHEMA_CANONICAL

    with _open_connection(database_path) as connection:
        if schema == SCHEMA_LEGACY:
            query = """
                SELECT
                    id AS "ID",
                    product_name AS "Product Name",
                    product_idea AS "Product Idea",
                    target_user AS "Target User",
                    business_goal AS "Business Goal",
                    date_created AS "Date Created"
                FROM products
                ORDER BY id DESC
            """
        elif schema in {SCHEMA_PRODUCT_ONLY, SCHEMA_CANONICAL}:
            query = """
                SELECT
                    id AS "ID",
                    name AS "Product Name",
                    description AS "Product Idea",
                    target_users AS "Target User",
                    business_goal AS "Business Goal",
                    created_at AS "Date Created"
                FROM products
                ORDER BY id DESC
            """
        else:
            raise DatabaseSchemaError(
                "Cannot load products from an unknown database schema."
            )

        return pd.read_sql_query(query, connection)
