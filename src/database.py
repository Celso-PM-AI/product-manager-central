"""SQLite persistence, migration, and compatibility helpers for PMC."""

import os
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final

import pandas as pd

from src.agile import (
    AgileAcceptanceCriterion,
    AgileArtifact,
    AgileArtifactBatch,
    AgileArtifactType,
    AgileBehaviorProfile,
    AgileContractError,
    AgileReviewState,
    AgileSourceReference,
    ContentProvenance,
)
from src.document_templates import document_template
from src.models import (
    DEFAULT_PRODUCT_STATUS,
    DocumentStatus,
    DocumentType,
    GeneratedArtifact,
    GeneratedArtifactCitation,
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
SCHEMA_DOCUMENT_ONLY: Final[str] = "canonical_documents"
SCHEMA_PHASE9: Final[str] = "canonical_phase9"
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

GENERATED_ARTIFACT_COLUMNS: Final[tuple[str, ...]] = (
    "id",
    "acceptance_key",
    "product_id",
    "request",
    "original_content",
    "accepted_content",
    "was_revised",
    "created_at",
    "accepted_at",
)

GENERATED_CITATION_COLUMNS: Final[tuple[str, ...]] = (
    "artifact_id",
    "source_number",
    "source_product_id",
    "source_product_name",
    "document_id",
    "document_title",
    "document_type",
    "section_key",
    "section_title",
)

AGILE_RUN_COLUMNS: Final[tuple[str, ...]] = (
    "batch_id",
    "product_id",
    "behavior_profile",
    "review_state",
    "prompt_version",
    "revision",
    "created_at",
    "updated_at",
    "accepted_at",
)

AGILE_ARTIFACT_COLUMNS: Final[tuple[str, ...]] = (
    "artifact_id",
    "batch_id",
    "product_id",
    "artifact_type",
    "title",
    "description",
    "parent_artifact_id",
    "position",
    "review_state",
    "provenance",
    "revision",
    "created_at",
    "updated_at",
)

AGILE_CRITERION_COLUMNS: Final[tuple[str, ...]] = (
    "criterion_id",
    "artifact_id",
    "position",
    "criterion_text",
)

AGILE_SOURCE_COLUMNS: Final[tuple[str, ...]] = (
    "id",
    "batch_id",
    "reference_id",
    "source_product_id",
    "source_product_name",
    "document_id",
    "document_title",
    "document_type",
    "section_key",
    "section_title",
)

AGILE_ARTIFACT_SOURCE_COLUMNS: Final[tuple[str, ...]] = (
    "artifact_id",
    "source_id",
)

AGILE_CRITERION_SOURCE_COLUMNS: Final[tuple[str, ...]] = (
    "criterion_id",
    "source_id",
)

AGILE_TABLES: Final[tuple[str, ...]] = (
    "agile_acceptance_criteria",
    "agile_artifact_sources",
    "agile_artifacts",
    "agile_criterion_sources",
    "agile_generation_runs",
    "agile_source_snapshots",
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


class GeneratedArtifactValidationError(ValueError):
    """Raised when accepted generated content is unsafe to persist."""


class AgilePersistenceError(ValueError):
    """Raised when an Agile batch is not eligible for accepted persistence."""


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
        "generated_artifacts",
        "generated_artifact_citations",
        "agile_generation_runs",
        "agile_artifacts",
        "agile_acceptance_criteria",
        "agile_source_snapshots",
        "agile_artifact_sources",
        "agile_criterion_sources",
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
    table_set = set(tables)
    agile_table_set = set(AGILE_TABLES)
    has_exact_agile_tables = agile_table_set.issubset(table_set)

    def columns_are(table_name: str, expected: tuple[str, ...]) -> bool:
        return tuple(
            row["name"] for row in _table_info(connection, table_name)
        ) == expected

    agile_schema_is_exact = has_exact_agile_tables and all(
        (
            columns_are("agile_generation_runs", AGILE_RUN_COLUMNS),
            columns_are("agile_artifacts", AGILE_ARTIFACT_COLUMNS),
            columns_are("agile_acceptance_criteria", AGILE_CRITERION_COLUMNS),
            columns_are("agile_source_snapshots", AGILE_SOURCE_COLUMNS),
            columns_are("agile_artifact_sources", AGILE_ARTIFACT_SOURCE_COLUMNS),
            columns_are("agile_criterion_sources", AGILE_CRITERION_SOURCE_COLUMNS),
        )
    )
    if has_exact_agile_tables and not agile_schema_is_exact:
        return SCHEMA_UNKNOWN

    base_tables = table_set - agile_table_set if agile_schema_is_exact else table_set
    if not tables:
        return SCHEMA_MISSING
    if base_tables == {"products"}:
        table_info = _table_info(connection)
        columns = tuple(row["name"] for row in table_info)
        if columns == CANONICAL_COLUMNS:
            return SCHEMA_PRODUCT_ONLY
        if columns == LEGACY_COLUMNS and _legacy_signature_is_exact(table_info):
            return SCHEMA_LEGACY
        return SCHEMA_UNKNOWN

    if base_tables == {"document_sections", "documents", "products"}:
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
            return SCHEMA_DOCUMENT_ONLY
    if base_tables == {
        "document_sections",
        "documents",
        "generated_artifact_citations",
        "generated_artifacts",
        "products",
    }:
        product_columns = tuple(row["name"] for row in _table_info(connection))
        document_columns = tuple(
            row["name"] for row in _table_info(connection, "documents")
        )
        section_columns = tuple(
            row["name"] for row in _table_info(connection, "document_sections")
        )
        artifact_columns = tuple(
            row["name"] for row in _table_info(connection, "generated_artifacts")
        )
        citation_columns = tuple(
            row["name"]
            for row in _table_info(connection, "generated_artifact_citations")
        )
        if (
            product_columns == CANONICAL_COLUMNS
            and document_columns == DOCUMENT_COLUMNS
            and section_columns == DOCUMENT_SECTION_COLUMNS
            and artifact_columns == GENERATED_ARTIFACT_COLUMNS
            and citation_columns == GENERATED_CITATION_COLUMNS
        ):
            return SCHEMA_CANONICAL if agile_schema_is_exact else SCHEMA_PHASE9
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


def _create_generated_artifact_tables(connection: sqlite3.Connection) -> None:
    """Add separate storage for explicitly accepted generated content."""

    connection.execute(
        """
        CREATE TABLE generated_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            acceptance_key TEXT NOT NULL UNIQUE
                CHECK (length(trim(acceptance_key)) > 0),
            product_id INTEGER NOT NULL,
            request TEXT NOT NULL
                CHECK (length(trim(request)) BETWEEN 1 AND 10000),
            original_content TEXT NOT NULL
                CHECK (length(trim(original_content)) BETWEEN 1 AND 50000),
            accepted_content TEXT NOT NULL
                CHECK (length(trim(accepted_content)) BETWEEN 1 AND 50000),
            was_revised INTEGER NOT NULL CHECK (was_revised IN (0, 1)),
            created_at TEXT NOT NULL CHECK (length(trim(created_at)) > 0),
            accepted_at TEXT NOT NULL CHECK (length(trim(accepted_at)) > 0),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE generated_artifact_citations (
            artifact_id INTEGER NOT NULL,
            source_number INTEGER NOT NULL CHECK (source_number > 0),
            source_product_id INTEGER NOT NULL,
            source_product_name TEXT NOT NULL
                CHECK (length(trim(source_product_name)) > 0),
            document_id INTEGER NOT NULL,
            document_title TEXT NOT NULL
                CHECK (length(trim(document_title)) > 0),
            document_type TEXT NOT NULL CHECK (document_type IN ('BRD', 'PRD')),
            section_key TEXT NOT NULL CHECK (length(trim(section_key)) > 0),
            section_title TEXT NOT NULL CHECK (length(trim(section_title)) > 0),
            PRIMARY KEY (artifact_id, source_number),
            FOREIGN KEY (artifact_id)
                REFERENCES generated_artifacts(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_generated_artifacts_product_id
        ON generated_artifacts (product_id, id DESC)
        """
    )


def _create_agile_tables(connection: sqlite3.Connection) -> None:
    """Add accepted Agile storage without changing Phase 9 tables or rows."""

    artifact_types = ", ".join(
        f"'{artifact_type.value}'" for artifact_type in AgileArtifactType
    )
    behavior_profiles = ", ".join(
        f"'{profile.value}'" for profile in AgileBehaviorProfile
    )
    provenance_values = ", ".join(
        f"'{provenance.value}'" for provenance in ContentProvenance
    )
    connection.execute(
        f"""
        CREATE TABLE agile_generation_runs (
            batch_id TEXT PRIMARY KEY
                CHECK (length(trim(batch_id)) BETWEEN 1 AND 128),
            product_id INTEGER NOT NULL,
            behavior_profile TEXT NOT NULL
                CHECK (behavior_profile IN ({behavior_profiles})),
            review_state TEXT NOT NULL
                CHECK (review_state = 'accepted'),
            prompt_version TEXT NOT NULL
                CHECK (length(trim(prompt_version)) BETWEEN 1 AND 50),
            revision INTEGER NOT NULL CHECK (revision > 0),
            created_at TEXT NOT NULL CHECK (length(trim(created_at)) > 0),
            updated_at TEXT NOT NULL CHECK (length(trim(updated_at)) > 0),
            accepted_at TEXT NOT NULL CHECK (length(trim(accepted_at)) > 0),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE agile_artifacts (
            artifact_id TEXT PRIMARY KEY
                CHECK (length(trim(artifact_id)) BETWEEN 1 AND 128),
            batch_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            artifact_type TEXT NOT NULL
                CHECK (artifact_type IN ({artifact_types})),
            title TEXT NOT NULL
                CHECK (length(trim(title)) BETWEEN 1 AND 200),
            description TEXT NOT NULL
                CHECK (length(trim(description)) BETWEEN 1 AND 10000),
            parent_artifact_id TEXT,
            position INTEGER NOT NULL CHECK (position > 0),
            review_state TEXT NOT NULL CHECK (review_state = 'accepted'),
            provenance TEXT NOT NULL
                CHECK (provenance IN ({provenance_values})),
            revision INTEGER NOT NULL CHECK (revision > 0),
            created_at TEXT NOT NULL CHECK (length(trim(created_at)) > 0),
            updated_at TEXT NOT NULL CHECK (length(trim(updated_at)) > 0),
            UNIQUE (batch_id, position),
            FOREIGN KEY (batch_id)
                REFERENCES agile_generation_runs(batch_id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_artifact_id)
                REFERENCES agile_artifacts(artifact_id) ON DELETE CASCADE,
            CHECK (artifact_type <> 'epic' OR parent_artifact_id IS NULL)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE agile_acceptance_criteria (
            criterion_id TEXT PRIMARY KEY
                CHECK (length(trim(criterion_id)) BETWEEN 1 AND 128),
            artifact_id TEXT NOT NULL,
            position INTEGER NOT NULL CHECK (position > 0),
            criterion_text TEXT NOT NULL
                CHECK (length(trim(criterion_text)) BETWEEN 1 AND 2000),
            UNIQUE (artifact_id, position),
            FOREIGN KEY (artifact_id)
                REFERENCES agile_artifacts(artifact_id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX idx_agile_criterion_unique_text
        ON agile_acceptance_criteria (artifact_id, lower(trim(criterion_text)))
        """
    )
    connection.execute(
        """
        CREATE TABLE agile_source_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            reference_id TEXT NOT NULL
                CHECK (length(trim(reference_id)) BETWEEN 1 AND 128),
            source_product_id INTEGER NOT NULL CHECK (source_product_id > 0),
            source_product_name TEXT NOT NULL
                CHECK (length(trim(source_product_name)) BETWEEN 1 AND 120),
            document_id INTEGER NOT NULL CHECK (document_id > 0),
            document_title TEXT NOT NULL
                CHECK (length(trim(document_title)) BETWEEN 1 AND 200),
            document_type TEXT NOT NULL CHECK (document_type IN ('BRD', 'PRD')),
            section_key TEXT NOT NULL
                CHECK (length(trim(section_key)) BETWEEN 1 AND 100),
            section_title TEXT NOT NULL
                CHECK (length(trim(section_title)) BETWEEN 1 AND 200),
            UNIQUE (batch_id, reference_id),
            FOREIGN KEY (batch_id)
                REFERENCES agile_generation_runs(batch_id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE agile_artifact_sources (
            artifact_id TEXT NOT NULL,
            source_id INTEGER NOT NULL,
            PRIMARY KEY (artifact_id, source_id),
            FOREIGN KEY (artifact_id)
                REFERENCES agile_artifacts(artifact_id) ON DELETE CASCADE,
            FOREIGN KEY (source_id)
                REFERENCES agile_source_snapshots(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE agile_criterion_sources (
            criterion_id TEXT NOT NULL,
            source_id INTEGER NOT NULL,
            PRIMARY KEY (criterion_id, source_id),
            FOREIGN KEY (criterion_id)
                REFERENCES agile_acceptance_criteria(criterion_id) ON DELETE CASCADE,
            FOREIGN KEY (source_id)
                REFERENCES agile_source_snapshots(id) ON DELETE CASCADE
        )
        """
    )
    statements = (
        """CREATE INDEX idx_agile_runs_product_id
            ON agile_generation_runs (product_id, accepted_at DESC)""",
        """CREATE INDEX idx_agile_artifacts_batch
            ON agile_artifacts (batch_id, position)""",
        """CREATE INDEX idx_agile_artifacts_product
            ON agile_artifacts (product_id, artifact_type, position)""",
        """CREATE INDEX idx_agile_criteria_artifact
            ON agile_acceptance_criteria (artifact_id, position)""",
        """CREATE INDEX idx_agile_sources_batch
            ON agile_source_snapshots (batch_id, reference_id)""",
        """
        CREATE TRIGGER trg_agile_artifact_insert_contract
        BEFORE INSERT ON agile_artifacts
        BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM agile_generation_runs AS run
                WHERE run.batch_id = NEW.batch_id
                  AND run.product_id = NEW.product_id
            ) THEN RAISE(ABORT, 'Agile artifact must match its batch product') END;
            SELECT CASE WHEN NEW.parent_artifact_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM agile_artifacts AS parent
                WHERE parent.artifact_id = NEW.parent_artifact_id
                  AND parent.batch_id = NEW.batch_id
                  AND parent.product_id = NEW.product_id
                  AND parent.position < NEW.position
                  AND (
                    (NEW.artifact_type = 'capability' AND parent.artifact_type = 'epic')
                    OR (NEW.artifact_type = 'feature' AND parent.artifact_type = 'capability')
                    OR (NEW.artifact_type = 'user_story' AND parent.artifact_type = 'feature')
                  )
            ) THEN RAISE(ABORT, 'Invalid Agile parent relationship') END;
        END
        """,
        """
        CREATE TRIGGER trg_agile_artifact_update_contract
        BEFORE UPDATE ON agile_artifacts
        BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM agile_generation_runs AS run
                WHERE run.batch_id = NEW.batch_id
                  AND run.product_id = NEW.product_id
            ) THEN RAISE(ABORT, 'Agile artifact must match its batch product') END;
            SELECT CASE WHEN NEW.parent_artifact_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM agile_artifacts AS parent
                WHERE parent.artifact_id = NEW.parent_artifact_id
                  AND parent.batch_id = NEW.batch_id
                  AND parent.product_id = NEW.product_id
                  AND parent.position < NEW.position
                  AND (
                    (NEW.artifact_type = 'capability' AND parent.artifact_type = 'epic')
                    OR (NEW.artifact_type = 'feature' AND parent.artifact_type = 'capability')
                    OR (NEW.artifact_type = 'user_story' AND parent.artifact_type = 'feature')
                  )
            ) THEN RAISE(ABORT, 'Invalid Agile parent relationship') END;
        END
        """,
        """
        CREATE TRIGGER trg_agile_source_product_contract
        BEFORE INSERT ON agile_source_snapshots
        BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM agile_generation_runs AS run
                WHERE run.batch_id = NEW.batch_id
                  AND run.product_id = NEW.source_product_id
            ) THEN RAISE(ABORT, 'Agile source must match its batch product') END;
        END
        """,
        """
        CREATE TRIGGER trg_agile_source_snapshot_immutable
        BEFORE UPDATE ON agile_source_snapshots
        BEGIN
            SELECT RAISE(ABORT, 'Agile source snapshots are immutable');
        END
        """,
        """
        CREATE TRIGGER trg_agile_artifact_source_batch
        BEFORE INSERT ON agile_artifact_sources
        BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1
                FROM agile_artifacts AS artifact
                INNER JOIN agile_source_snapshots AS source
                    ON source.id = NEW.source_id
                WHERE artifact.artifact_id = NEW.artifact_id
                  AND artifact.batch_id = source.batch_id
            ) THEN RAISE(ABORT, 'Agile artifact source must be in the same batch') END;
        END
        """,
        """
        CREATE TRIGGER trg_agile_criterion_source_batch
        BEFORE INSERT ON agile_criterion_sources
        BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1
                FROM agile_acceptance_criteria AS criterion
                INNER JOIN agile_artifacts AS artifact
                    ON artifact.artifact_id = criterion.artifact_id
                INNER JOIN agile_source_snapshots AS source
                    ON source.id = NEW.source_id
                WHERE criterion.criterion_id = NEW.criterion_id
                  AND artifact.batch_id = source.batch_id
            ) THEN RAISE(ABORT, 'Agile criterion source must be in the same batch') END;
        END
        """,
    )
    for statement in statements:
        connection.execute(statement)


def _agile_tables_exist(connection: sqlite3.Connection) -> bool:
    return set(AGILE_TABLES).issubset(_user_tables(connection))


def _add_agile_schema(connection: sqlite3.Connection) -> None:
    """Transactionally add Agile tables and verify all Phase 9 rows exactly."""

    preserved_tables = (
        "products",
        "documents",
        "document_sections",
        "generated_artifacts",
        "generated_artifact_citations",
    )
    before = {
        table: tuple(
            tuple(row)
            for row in connection.execute(
                f'SELECT * FROM "{table}" ORDER BY rowid'
            ).fetchall()
        )
        for table in preserved_tables
    }
    _create_agile_tables(connection)
    after = {
        table: tuple(
            tuple(row)
            for row in connection.execute(
                f'SELECT * FROM "{table}" ORDER BY rowid'
            ).fetchall()
        )
        for table in preserved_tables
    }
    if after != before:
        raise MigrationVerificationError(
            "Agile migration changed existing Phase 9 data."
        )
    if _detect_schema(connection) != SCHEMA_CANONICAL:
        raise MigrationVerificationError("Agile schema verification failed.")


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
    if _detect_schema(connection) != SCHEMA_DOCUMENT_ONLY:
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
                _create_generated_artifact_tables(connection)
                _create_agile_tables(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        elif schema == SCHEMA_PRODUCT_ONLY:
            connection.execute("BEGIN IMMEDIATE")
            try:
                _add_document_schema(connection)
                _create_generated_artifact_tables(connection)
                if not _agile_tables_exist(connection):
                    _create_agile_tables(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        elif schema == SCHEMA_DOCUMENT_ONLY:
            connection.execute("BEGIN IMMEDIATE")
            try:
                _create_generated_artifact_tables(connection)
                if not _agile_tables_exist(connection):
                    _create_agile_tables(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        elif schema == SCHEMA_PHASE9:
            connection.execute("BEGIN IMMEDIATE")
            try:
                _add_agile_schema(connection)
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
    if schema not in {
        SCHEMA_PRODUCT_ONLY,
        SCHEMA_DOCUMENT_ONLY,
        SCHEMA_PHASE9,
        SCHEMA_CANONICAL,
    }:
        raise DatabaseSchemaError(
            f"Canonical database schema required; found {schema}."
        )


def _require_document_schema(connection: sqlite3.Connection) -> None:
    schema = _detect_schema(connection)
    if schema not in {SCHEMA_DOCUMENT_ONLY, SCHEMA_PHASE9, SCHEMA_CANONICAL}:
        raise DatabaseSchemaError(
            f"Phase 8 document schema required; found {schema}."
        )


def _require_generated_artifact_schema(connection: sqlite3.Connection) -> None:
    schema = _detect_schema(connection)
    if schema not in {SCHEMA_PHASE9, SCHEMA_CANONICAL}:
        raise DatabaseSchemaError(
            f"Generated artifact schema required; found {schema}."
        )


def _require_agile_schema(connection: sqlite3.Connection) -> None:
    schema = _detect_schema(connection)
    if schema != SCHEMA_CANONICAL:
        raise DatabaseSchemaError(f"Accepted Agile schema required; found {schema}.")


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
                documents.document_status,
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
                document_status=DocumentStatus(row["document_status"]),
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


def _select_generated_artifact_by_id(
    connection: sqlite3.Connection,
    artifact_id: int,
) -> GeneratedArtifact | None:
    row = connection.execute(
        """
        SELECT id, acceptance_key, product_id, request, original_content,
               accepted_content, was_revised, created_at, accepted_at
        FROM generated_artifacts
        WHERE id = ?
        """,
        (artifact_id,),
    ).fetchone()
    if row is None:
        return None
    citation_rows = connection.execute(
        """
        SELECT source_number, source_product_id, source_product_name,
               document_id, document_title, document_type, section_key,
               section_title
        FROM generated_artifact_citations
        WHERE artifact_id = ?
        ORDER BY source_number
        """,
        (artifact_id,),
    ).fetchall()
    citations = tuple(
        GeneratedArtifactCitation(
            source_number=citation["source_number"],
            source_product_id=citation["source_product_id"],
            source_product_name=citation["source_product_name"],
            document_id=citation["document_id"],
            document_title=citation["document_title"],
            document_type=DocumentType(citation["document_type"]),
            section_key=citation["section_key"],
            section_title=citation["section_title"],
        )
        for citation in citation_rows
    )
    return GeneratedArtifact(
        id=row["id"],
        acceptance_key=row["acceptance_key"],
        product_id=row["product_id"],
        request=row["request"],
        original_content=row["original_content"],
        accepted_content=row["accepted_content"],
        was_revised=bool(row["was_revised"]),
        citations=citations,
        created_at=row["created_at"],
        accepted_at=row["accepted_at"],
    )


def get_generated_artifact(
    artifact_id: int,
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> GeneratedArtifact | None:
    """Return one separately stored accepted generated artifact."""

    with _open_connection(database_path) as connection:
        _require_generated_artifact_schema(connection)
        return _select_generated_artifact_by_id(connection, artifact_id)


def list_generated_artifacts_for_product(
    product_id: int,
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> list[GeneratedArtifact]:
    """List only explicitly accepted generated artifacts for one product."""

    with _open_connection(database_path) as connection:
        _require_generated_artifact_schema(connection)
        rows = connection.execute(
            """
            SELECT id FROM generated_artifacts
            WHERE product_id = ?
            ORDER BY id DESC
            """,
            (product_id,),
        ).fetchall()
        return [
            artifact
            for row in rows
            if (
                artifact := _select_generated_artifact_by_id(connection, row["id"])
            )
            is not None
        ]


def save_accepted_generated_artifact(
    *,
    acceptance_key: str,
    product_id: int,
    request: str,
    original_content: str,
    accepted_content: str,
    citations: Sequence[Mapping[str, object]],
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> tuple[GeneratedArtifact, bool]:
    """Persist one explicit acceptance, idempotently, after source revalidation."""

    key = acceptance_key.strip() if isinstance(acceptance_key, str) else ""
    normalized_request = request.strip() if isinstance(request, str) else ""
    original = original_content.strip() if isinstance(original_content, str) else ""
    accepted = accepted_content.strip() if isinstance(accepted_content, str) else ""
    if not key:
        raise GeneratedArtifactValidationError("A valid review is required.")
    if not normalized_request or len(normalized_request) > 10_000:
        raise GeneratedArtifactValidationError("The generation request is invalid.")
    if not original or len(original) > 50_000:
        raise GeneratedArtifactValidationError("The original AI output is invalid.")
    if not accepted or len(accepted) > 50_000:
        raise GeneratedArtifactValidationError(
            "Accepted content must contain 1 to 50,000 characters."
        )
    if not citations:
        raise GeneratedArtifactValidationError(
            "Accepted generated content must retain at least one citation."
        )

    with _open_connection(database_path) as connection:
        _require_generated_artifact_schema(connection)
        duplicate = connection.execute(
            "SELECT id FROM generated_artifacts WHERE acceptance_key = ?",
            (key,),
        ).fetchone()
        if duplicate is not None:
            artifact = _select_generated_artifact_by_id(connection, duplicate["id"])
            if artifact is None:
                raise RuntimeError("Saved generated artifact could not be retrieved.")
            return artifact, False

        if connection.execute(
            "SELECT 1 FROM products WHERE id = ?", (product_id,)
        ).fetchone() is None:
            raise GeneratedArtifactValidationError(
                "The selected product no longer exists. Nothing was saved."
            )

        normalized_citations: list[dict[str, object]] = []
        seen_numbers: set[int] = set()
        for supplied in citations:
            try:
                source_number = int(supplied["source_number"])
                source_product_id = int(supplied["source_product_id"])
                document_id = int(supplied["document_id"])
                document_type = DocumentType(supplied["document_type"])
                source_product_name = str(supplied["source_product_name"]).strip()
                document_title = str(supplied["document_title"]).strip()
                section_key = str(supplied["section_key"]).strip()
                section_title = str(supplied["section_title"]).strip()
            except (KeyError, TypeError, ValueError) as error:
                raise GeneratedArtifactValidationError(
                    "Citation metadata is incomplete. Nothing was saved."
                ) from error
            if source_number <= 0 or source_number in seen_numbers:
                raise GeneratedArtifactValidationError(
                    "Citation source numbers must be unique and positive."
                )
            seen_numbers.add(source_number)
            current = connection.execute(
                """
                SELECT products.id AS product_id, products.name AS product_name,
                       documents.title, documents.document_type,
                       documents.document_status, document_sections.content
                FROM documents
                INNER JOIN products ON products.id = documents.product_id
                INNER JOIN document_sections
                    ON document_sections.document_id = documents.id
                WHERE documents.id = ? AND document_sections.section_key = ?
                """,
                (document_id, section_key),
            ).fetchone()
            if (
                current is None
                or current["document_status"] != DocumentStatus.APPROVED.value
                or current["document_type"] not in {
                    DocumentType.BRD.value,
                    DocumentType.PRD.value,
                }
                or not str(current["content"]).strip()
                or current["product_id"] != source_product_id
                or current["product_name"] != source_product_name
                or current["title"] != document_title
                or current["document_type"] != document_type.value
            ):
                raise GeneratedArtifactValidationError(
                    "A cited source is no longer an eligible Approved BRD or PRD. "
                    "Nothing was saved; generate a new draft and review it again."
                )
            normalized_citations.append(
                {
                    "source_number": source_number,
                    "source_product_id": source_product_id,
                    "source_product_name": source_product_name,
                    "document_id": document_id,
                    "document_title": document_title,
                    "document_type": document_type,
                    "section_key": section_key,
                    "section_title": section_title,
                }
            )

        timestamp = _utc_now()
        cursor = connection.execute(
            """
            INSERT INTO generated_artifacts (
                acceptance_key, product_id, request, original_content,
                accepted_content, was_revised, created_at, accepted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                product_id,
                normalized_request,
                original,
                accepted,
                int(accepted != original),
                timestamp,
                timestamp,
            ),
        )
        artifact_id = int(cursor.lastrowid)
        connection.executemany(
            """
            INSERT INTO generated_artifact_citations (
                artifact_id, source_number, source_product_id,
                source_product_name, document_id, document_title,
                document_type, section_key, section_title
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    artifact_id,
                    citation["source_number"],
                    citation["source_product_id"],
                    citation["source_product_name"],
                    citation["document_id"],
                    citation["document_title"],
                    citation["document_type"].value,
                    citation["section_key"],
                    citation["section_title"],
                )
                for citation in normalized_citations
            ),
        )
        artifact = _select_generated_artifact_by_id(connection, artifact_id)
        if artifact is None:
            raise RuntimeError("Saved generated artifact could not be retrieved.")
        return artifact, True


def _select_agile_sources(
    connection: sqlite3.Connection,
    *,
    artifact_id: str | None = None,
    criterion_id: str | None = None,
) -> tuple[AgileSourceReference, ...]:
    if (artifact_id is None) == (criterion_id is None):
        raise ValueError("Select sources for exactly one Agile record.")
    if artifact_id is not None:
        link_table = "agile_artifact_sources"
        id_column = "artifact_id"
        record_id = artifact_id
    else:
        link_table = "agile_criterion_sources"
        id_column = "criterion_id"
        record_id = criterion_id
    rows = connection.execute(
        f"""
        SELECT source.reference_id, source.source_product_id,
               source.source_product_name, source.document_id,
               source.document_title, source.document_type,
               source.section_key, source.section_title
        FROM {link_table} AS link
        INNER JOIN agile_source_snapshots AS source
            ON source.id = link.source_id
        WHERE link.{id_column} = ?
        ORDER BY source.reference_id
        """,
        (record_id,),
    ).fetchall()
    return tuple(
        AgileSourceReference(
            reference_id=row["reference_id"],
            product_id=row["source_product_id"],
            product_name=row["source_product_name"],
            document_id=row["document_id"],
            document_title=row["document_title"],
            document_type=DocumentType(row["document_type"]),
            section_key=row["section_key"],
            section_title=row["section_title"],
        )
        for row in rows
    )


def _select_accepted_agile_batch(
    connection: sqlite3.Connection,
    batch_id: str,
) -> AgileArtifactBatch | None:
    run = connection.execute(
        """
        SELECT batch_id, product_id, behavior_profile, review_state,
               prompt_version, revision, created_at, updated_at, accepted_at
        FROM agile_generation_runs
        WHERE batch_id = ?
        """,
        (batch_id,),
    ).fetchone()
    if run is None:
        return None
    artifact_rows = connection.execute(
        """
        SELECT artifact_id, artifact_type, product_id, title, description,
               parent_artifact_id, position, review_state, provenance,
               revision, created_at, updated_at
        FROM agile_artifacts
        WHERE batch_id = ?
        ORDER BY position
        """,
        (batch_id,),
    ).fetchall()
    artifacts: list[AgileArtifact] = []
    for row in artifact_rows:
        criterion_rows = connection.execute(
            """
            SELECT criterion_id, position, criterion_text
            FROM agile_acceptance_criteria
            WHERE artifact_id = ?
            ORDER BY position
            """,
            (row["artifact_id"],),
        ).fetchall()
        criteria = tuple(
            AgileAcceptanceCriterion(
                criterion_id=criterion["criterion_id"],
                position=criterion["position"],
                text=criterion["criterion_text"],
                source_references=_select_agile_sources(
                    connection,
                    criterion_id=criterion["criterion_id"],
                ),
            )
            for criterion in criterion_rows
        )
        artifacts.append(
            AgileArtifact(
                artifact_id=row["artifact_id"],
                artifact_type=AgileArtifactType(row["artifact_type"]),
                product_id=row["product_id"],
                title=row["title"],
                description=row["description"],
                acceptance_criteria=criteria,
                source_references=_select_agile_sources(
                    connection,
                    artifact_id=row["artifact_id"],
                ),
                position=row["position"],
                parent_artifact_id=row["parent_artifact_id"],
                review_state=AgileReviewState(row["review_state"]),
                provenance=ContentProvenance(row["provenance"]),
                revision=row["revision"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )
    try:
        return AgileArtifactBatch(
            batch_id=run["batch_id"],
            product_id=run["product_id"],
            behavior_profile=AgileBehaviorProfile(run["behavior_profile"]),
            review_state=AgileReviewState(run["review_state"]),
            prompt_version=run["prompt_version"],
            artifacts=tuple(artifacts),
            revision=run["revision"],
            created_at=run["created_at"],
            updated_at=run["updated_at"],
            accepted_at=run["accepted_at"],
        )
    except AgileContractError as error:
        raise DatabaseSchemaError("Stored Agile data violates its contract.") from error


def get_accepted_agile_batch(
    batch_id: str,
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> AgileArtifactBatch | None:
    """Return one accepted Agile batch and its ordered, snapshotted records."""

    with _open_connection(database_path) as connection:
        _require_agile_schema(connection)
        return _select_accepted_agile_batch(connection, batch_id)


def list_accepted_agile_batches_for_product(
    product_id: int,
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> list[AgileArtifactBatch]:
    """Return accepted Agile batches for one product, newest first."""

    with _open_connection(database_path) as connection:
        _require_agile_schema(connection)
        rows = connection.execute(
            """
            SELECT batch_id
            FROM agile_generation_runs
            WHERE product_id = ?
            ORDER BY accepted_at DESC, batch_id
            """,
            (product_id,),
        ).fetchall()
        return [
            batch
            for row in rows
            if (
                batch := _select_accepted_agile_batch(connection, row["batch_id"])
            )
            is not None
        ]


def _verify_agile_source_is_current(
    connection: sqlite3.Connection,
    source: AgileSourceReference,
) -> None:
    current = connection.execute(
        """
        SELECT products.id AS product_id, products.name AS product_name,
               documents.title AS document_title, documents.document_type,
               documents.document_status, document_sections.content
        FROM documents
        INNER JOIN products ON products.id = documents.product_id
        INNER JOIN document_sections
            ON document_sections.document_id = documents.id
        WHERE documents.id = ? AND document_sections.section_key = ?
        """,
        (source.document_id, source.section_key),
    ).fetchone()
    if (
        current is None
        or current["product_id"] != source.product_id
        or current["product_name"] != source.product_name
        or current["document_title"] != source.document_title
        or current["document_type"] != source.document_type.value
        or current["document_status"] != DocumentStatus.APPROVED.value
        or not str(current["content"]).strip()
    ):
        raise AgilePersistenceError(
            "Every Agile source must be a current Approved BRD or PRD section."
        )
    section_titles = {
        definition.key: definition.label
        for definition in document_template(source.document_type)
    }
    if section_titles.get(source.section_key) != source.section_title:
        raise AgilePersistenceError(
            "Agile source section metadata does not match the approved template."
        )


def save_accepted_agile_batch(
    batch: AgileArtifactBatch,
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> tuple[AgileArtifactBatch, bool]:
    """Transactionally persist one fully accepted, traceable Agile batch."""

    if not isinstance(batch, AgileArtifactBatch):
        raise AgilePersistenceError("A validated Agile batch is required.")
    if batch.review_state is not AgileReviewState.ACCEPTED:
        raise AgilePersistenceError("Pending or rejected Agile batches cannot be saved.")
    if any(
        artifact.review_state is not AgileReviewState.ACCEPTED
        for artifact in batch.artifacts
    ):
        raise AgilePersistenceError("Every saved Agile artifact must be accepted.")

    with _open_connection(database_path) as connection:
        _require_agile_schema(connection)
        existing = _select_accepted_agile_batch(connection, batch.batch_id)
        if existing is not None:
            return existing, False
        if connection.execute(
            "SELECT 1 FROM products WHERE id = ?", (batch.product_id,)
        ).fetchone() is None:
            raise AgilePersistenceError("The Agile batch product no longer exists.")

        sources: dict[str, AgileSourceReference] = {}
        for artifact in batch.artifacts:
            for source in artifact.source_references:
                existing_source = sources.setdefault(source.reference_id, source)
                if existing_source != source:
                    raise AgilePersistenceError(
                        "A source reference ID cannot describe different sources."
                    )
            for criterion in artifact.acceptance_criteria:
                for source in criterion.source_references:
                    existing_source = sources.setdefault(source.reference_id, source)
                    if existing_source != source:
                        raise AgilePersistenceError(
                            "A source reference ID cannot describe different sources."
                        )
        for source in sources.values():
            _verify_agile_source_is_current(connection, source)

        connection.execute(
            """
            INSERT INTO agile_generation_runs (
                batch_id, product_id, behavior_profile, review_state,
                prompt_version, revision, created_at, updated_at, accepted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch.batch_id,
                batch.product_id,
                batch.behavior_profile.value,
                batch.review_state.value,
                batch.prompt_version,
                batch.revision,
                batch.created_at,
                batch.updated_at,
                batch.accepted_at,
            ),
        )
        source_ids: dict[str, int] = {}
        for source in sorted(sources.values(), key=lambda item: item.reference_id):
            cursor = connection.execute(
                """
                INSERT INTO agile_source_snapshots (
                    batch_id, reference_id, source_product_id,
                    source_product_name, document_id, document_title,
                    document_type, section_key, section_title
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch.batch_id,
                    source.reference_id,
                    source.product_id,
                    source.product_name,
                    source.document_id,
                    source.document_title,
                    source.document_type.value,
                    source.section_key,
                    source.section_title,
                ),
            )
            source_ids[source.reference_id] = int(cursor.lastrowid)

        for artifact in batch.artifacts:
            connection.execute(
                """
                INSERT INTO agile_artifacts (
                    artifact_id, batch_id, product_id, artifact_type, title,
                    description, parent_artifact_id, position, review_state,
                    provenance, revision, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.artifact_id,
                    batch.batch_id,
                    artifact.product_id,
                    artifact.artifact_type.value,
                    artifact.title,
                    artifact.description,
                    artifact.parent_artifact_id,
                    artifact.position,
                    artifact.review_state.value,
                    artifact.provenance.value,
                    artifact.revision,
                    artifact.created_at,
                    artifact.updated_at,
                ),
            )
            connection.executemany(
                """
                INSERT INTO agile_artifact_sources (artifact_id, source_id)
                VALUES (?, ?)
                """,
                (
                    (artifact.artifact_id, source_ids[source.reference_id])
                    for source in artifact.source_references
                ),
            )
            for criterion in artifact.acceptance_criteria:
                connection.execute(
                    """
                    INSERT INTO agile_acceptance_criteria (
                        criterion_id, artifact_id, position, criterion_text
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        criterion.criterion_id,
                        artifact.artifact_id,
                        criterion.position,
                        criterion.text,
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO agile_criterion_sources (criterion_id, source_id)
                    VALUES (?, ?)
                    """,
                    (
                        (criterion.criterion_id, source_ids[source.reference_id])
                        for source in criterion.source_references
                    ),
                )

        saved = _select_accepted_agile_batch(connection, batch.batch_id)
        if saved is None:
            raise RuntimeError("Saved Agile batch could not be retrieved.")
        return saved, True


def migrate_agile_database(
    database_path: str | os.PathLike[str] = DATABASE_FILE,
) -> bool:
    """Add Checkpoint 7 tables to an exact Phase 9 database, idempotently."""

    path = _database_path(database_path)
    if not path.exists():
        raise DatabaseSchemaError("Cannot migrate a missing database.")
    with _open_connection(path) as connection:
        schema = _detect_schema(connection)
        if schema == SCHEMA_CANONICAL:
            return False
        if schema != SCHEMA_PHASE9:
            raise DatabaseSchemaError(
                "Agile migration requires the exact Phase 9 canonical schema."
            )
        connection.execute("BEGIN IMMEDIATE")
        try:
            _add_agile_schema(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return True


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
        if schema not in {
            SCHEMA_PRODUCT_ONLY,
            SCHEMA_DOCUMENT_ONLY,
            SCHEMA_PHASE9,
        }:
            raise DatabaseSchemaError(
                "Document migration requires the product-only canonical schema."
            )
        connection.execute("BEGIN IMMEDIATE")
        try:
            if schema == SCHEMA_PRODUCT_ONLY:
                _add_document_schema(connection)
            if schema in {SCHEMA_PRODUCT_ONLY, SCHEMA_DOCUMENT_ONLY}:
                _create_generated_artifact_tables(connection)
            if not _agile_tables_exist(connection):
                _create_agile_tables(connection)
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
            _create_generated_artifact_tables(connection)
            _create_agile_tables(connection)

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

    if schema in {
        SCHEMA_PRODUCT_ONLY,
        SCHEMA_DOCUMENT_ONLY,
        SCHEMA_PHASE9,
        SCHEMA_CANONICAL,
    }:
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
        elif schema in {
            SCHEMA_PRODUCT_ONLY,
            SCHEMA_DOCUMENT_ONLY,
            SCHEMA_PHASE9,
            SCHEMA_CANONICAL,
        }:
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
