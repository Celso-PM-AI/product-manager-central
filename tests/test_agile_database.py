"""Isolated migration and persistence tests for accepted Agile artifacts."""

import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from src.agile import (
    AgileAcceptanceCriterion,
    AgileArtifact,
    AgileArtifactBatch,
    AgileArtifactType,
    AgileBehaviorProfile,
    AgileReviewState,
    AgileSourceReference,
    ContentProvenance,
)
from src.database import (
    AGILE_TABLES,
    SCHEMA_CANONICAL,
    SCHEMA_PHASE9,
    AgilePersistenceError,
    create_document,
    create_product,
    delete_product,
    detect_database_schema,
    get_accepted_agile_batch,
    initialize_database,
    list_accepted_agile_batches_for_product,
    list_generated_artifacts_for_product,
    migrate_agile_database,
    save_accepted_agile_batch,
    save_accepted_generated_artifact,
)
from src.document_templates import document_template
from src.models import DocumentStatus, DocumentType
from tests.success_matrix_fixtures import complete_prd_agile_hierarchy, complete_success_matrix


TIMESTAMP = "2026-08-11T10:00:00.000000Z"
ACCEPTED_AT = "2026-08-11T10:01:00.000000Z"


def database_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AgileDatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "agile.db"
        initialize_database(self.database_path)
        self.product = create_product(
            {
                "name": "Atlas",
                "description": "A portfolio planning workspace.",
                "target_users": "Product leaders",
                "business_goal": "Improve planning decisions.",
                "status": "planning",
            },
            self.database_path,
        )
        sections = {
            definition.key: f"Approved evidence for {definition.label}."
            for definition in document_template(DocumentType.PRD)
        }
        self.document = create_document(
            {
                "product_id": self.product.id,
                "document_type": DocumentType.PRD,
                "title": "Atlas PRD",
                "version": "1.0",
                "document_status": DocumentStatus.APPROVED,
                "success_matrix": complete_success_matrix(),
                "agile_hierarchy": complete_prd_agile_hierarchy("agile-db"),
                "sections": sections,
            },
            self.database_path,
        )
        definition = document_template(DocumentType.PRD)[0]
        self.source = AgileSourceReference(
            reference_id="source-1",
            product_id=self.product.id,
            product_name=self.product.name,
            document_id=self.document.id,
            document_title=self.document.title,
            document_type=self.document.document_type,
            section_key=definition.key,
            section_title=definition.label,
        )

    def artifact(
        self,
        artifact_type: AgileArtifactType,
        position: int,
        parent_id: str | None = None,
    ) -> AgileArtifact:
        return AgileArtifact(
            artifact_id=f"artifact-{position}",
            artifact_type=artifact_type,
            product_id=self.product.id,
            title=f"Artifact {position}",
            description=f"Grounded description {position}.",
            acceptance_criteria=(
                AgileAcceptanceCriterion(
                    criterion_id=f"criterion-{position}",
                    position=1,
                    text=f"The observable result {position} is available.",
                    source_references=(self.source,),
                ),
            ),
            source_references=(self.source,),
            position=position,
            parent_artifact_id=parent_id,
            review_state=AgileReviewState.ACCEPTED,
            provenance=(
                ContentProvenance.AI_GENERATED
                if position == 1
                else ContentProvenance.PRODUCT_MANAGER_EDITED
            ),
            revision=position,
            created_at=TIMESTAMP,
            updated_at=TIMESTAMP,
        )

    def batch(self, batch_id: str = "batch-1") -> AgileArtifactBatch:
        return AgileArtifactBatch(
            batch_id=batch_id,
            product_id=self.product.id,
            behavior_profile=AgileBehaviorProfile.STRICTLY_GROUNDED,
            review_state=AgileReviewState.ACCEPTED,
            prompt_version="1.0.0",
            artifacts=(
                self.artifact(AgileArtifactType.EPIC, 1),
                self.artifact(AgileArtifactType.CAPABILITY, 2, "artifact-1"),
                self.artifact(AgileArtifactType.FEATURE, 3, "artifact-2"),
                self.artifact(AgileArtifactType.USER_STORY, 4, "artifact-3"),
            ),
            created_at=TIMESTAMP,
            updated_at=ACCEPTED_AT,
            accepted_at=ACCEPTED_AT,
            revision=2,
        )


class AgileSchemaTests(AgileDatabaseTestCase):
    def _drop_agile_schema(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            for table in (
                "agile_criterion_sources",
                "agile_artifact_sources",
                "agile_acceptance_criteria",
                "agile_source_snapshots",
                "agile_artifacts",
                "agile_generation_runs",
            ):
                connection.execute(f'DROP TABLE "{table}"')

    def test_clean_initialization_has_additive_tables_constraints_and_indexes(self):
        self.assertEqual(detect_database_schema(self.database_path), SCHEMA_CANONICAL)
        with closing(sqlite3.connect(self.database_path)) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_schema WHERE type = 'table'"
                )
            }
            run_foreign_keys = connection.execute(
                "PRAGMA foreign_key_list(agile_generation_runs)"
            ).fetchall()
            artifact_indexes = {
                row[1]
                for row in connection.execute("PRAGMA index_list(agile_artifacts)")
            }
        self.assertTrue(set(AGILE_TABLES).issubset(tables))
        self.assertEqual(run_foreign_keys[0][2], "products")
        self.assertEqual(run_foreign_keys[0][6].upper(), "CASCADE")
        self.assertIn("idx_agile_artifacts_batch", artifact_indexes)

    def test_repeated_initialization_is_idempotent(self):
        before = database_hash(self.database_path)
        initialize_database(self.database_path)
        self.assertEqual(database_hash(self.database_path), before)

    def test_phase9_upgrade_preserves_all_existing_rows_exactly(self):
        generic, _ = save_accepted_generated_artifact(
            acceptance_key="legacy-acceptance",
            product_id=self.product.id,
            request="Summarize the approved requirement.",
            original_content="Approved summary.",
            accepted_content="Approved summary.",
            citations=(
                {
                    "source_number": 1,
                    "source_product_id": self.product.id,
                    "source_product_name": self.product.name,
                    "document_id": self.document.id,
                    "document_title": self.document.title,
                    "document_type": self.document.document_type,
                    "section_key": self.source.section_key,
                    "section_title": self.source.section_title,
                },
            ),
            database_path=self.database_path,
        )
        with closing(sqlite3.connect(self.database_path)) as connection:
            before = {
                table: connection.execute(
                    f'SELECT * FROM "{table}" ORDER BY rowid'
                ).fetchall()
                for table in (
                    "products",
                    "documents",
                    "document_sections",
                    "generated_artifacts",
                    "generated_artifact_citations",
                )
            }
        self._drop_agile_schema()
        self.assertEqual(detect_database_schema(self.database_path), SCHEMA_PHASE9)

        self.assertTrue(migrate_agile_database(self.database_path))
        self.assertFalse(migrate_agile_database(self.database_path))

        with closing(sqlite3.connect(self.database_path)) as connection:
            after = {
                table: connection.execute(
                    f'SELECT * FROM "{table}" ORDER BY rowid'
                ).fetchall()
                for table in before
            }
        self.assertEqual(after, before)
        self.assertEqual(
            list_generated_artifacts_for_product(self.product.id, self.database_path),
            [generic],
        )

    def test_initialization_automatically_upgrades_exact_phase9_schema(self):
        self._drop_agile_schema()
        self.assertEqual(detect_database_schema(self.database_path), SCHEMA_PHASE9)

        initialize_database(self.database_path)

        self.assertEqual(detect_database_schema(self.database_path), SCHEMA_CANONICAL)
        self.assertEqual(
            create_product(
                {
                    "name": "Second product",
                    "description": "Compatibility check.",
                    "target_users": "Product managers",
                    "business_goal": "Preserve existing operations.",
                    "status": "discovery",
                },
                self.database_path,
            ).name,
            "Second product",
        )

    def test_failed_migration_rolls_back_every_new_table(self):
        self._drop_agile_schema()
        before = database_hash(self.database_path)

        def partial_failure(connection: sqlite3.Connection) -> None:
            connection.execute("CREATE TABLE agile_generation_runs (batch_id TEXT)")
            raise RuntimeError("simulated failure")

        with patch("src.database._create_agile_tables", side_effect=partial_failure):
            with self.assertRaises(RuntimeError):
                migrate_agile_database(self.database_path)

        self.assertEqual(detect_database_schema(self.database_path), SCHEMA_PHASE9)
        self.assertEqual(database_hash(self.database_path), before)


class AgilePersistenceTests(AgileDatabaseTestCase):
    def test_save_and_load_preserve_hierarchy_criteria_traceability_and_metadata(self):
        expected = self.batch()

        saved, was_created = save_accepted_agile_batch(
            expected, self.database_path
        )

        self.assertTrue(was_created)
        self.assertEqual(saved, expected)
        self.assertEqual(get_accepted_agile_batch(expected.batch_id, self.database_path), expected)
        self.assertEqual(
            list_accepted_agile_batches_for_product(
                self.product.id, self.database_path
            ),
            [expected],
        )
        self.assertEqual(
            [item.parent_artifact_id for item in saved.artifacts],
            [None, "artifact-1", "artifact-2", "artifact-3"],
        )
        self.assertEqual(saved.artifacts[3].acceptance_criteria[0].position, 1)
        self.assertEqual(
            saved.artifacts[3].acceptance_criteria[0].source_references,
            (self.source,),
        )

    def test_repeated_save_is_idempotent(self):
        batch = self.batch()
        first, first_created = save_accepted_agile_batch(batch, self.database_path)
        second, second_created = save_accepted_agile_batch(batch, self.database_path)
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(second, first)

    def test_approved_brd_traceability_is_preserved_as_well_as_prd(self):
        sections = {
            definition.key: f"Approved BRD evidence for {definition.label}."
            for definition in document_template(DocumentType.BRD)
        }
        brd = create_document(
            {
                "product_id": self.product.id,
                "document_type": DocumentType.BRD,
                "title": "Atlas BRD",
                "version": "1.0",
                "document_status": DocumentStatus.APPROVED,
                "sections": sections,
            },
            self.database_path,
        )
        definition = document_template(DocumentType.BRD)[0]
        brd_source = AgileSourceReference(
            reference_id="brd-source-1",
            product_id=self.product.id,
            product_name=self.product.name,
            document_id=brd.id,
            document_title=brd.title,
            document_type=brd.document_type,
            section_key=definition.key,
            section_title=definition.label,
        )
        original = self.batch("brd-batch")
        artifacts = tuple(
            replace(
                artifact,
                source_references=(brd_source,),
                acceptance_criteria=tuple(
                    replace(criterion, source_references=(brd_source,))
                    for criterion in artifact.acceptance_criteria
                ),
            )
            for artifact in original.artifacts
        )
        expected = replace(original, artifacts=artifacts)

        saved, _ = save_accepted_agile_batch(expected, self.database_path)

        self.assertEqual(saved, expected)
        self.assertTrue(
            all(
                source.document_type is DocumentType.BRD
                for artifact in saved.artifacts
                for source in artifact.source_references
            )
        )

    def test_pending_batches_and_pending_artifacts_are_not_persisted(self):
        accepted = self.batch()
        pending_batch = replace(
            accepted,
            review_state=AgileReviewState.PENDING_REVIEW,
            accepted_at=None,
        )
        with self.assertRaises(AgilePersistenceError):
            save_accepted_agile_batch(pending_batch, self.database_path)

        pending_artifact = replace(
            accepted.artifacts[0], review_state=AgileReviewState.PENDING_REVIEW
        )
        accepted_with_pending = replace(
            accepted,
            artifacts=(pending_artifact,) + accepted.artifacts[1:],
        )
        with self.assertRaises(AgilePersistenceError):
            save_accepted_agile_batch(accepted_with_pending, self.database_path)
        self.assertIsNone(get_accepted_agile_batch(accepted.batch_id, self.database_path))

    def test_stale_draft_or_mismatched_source_blocks_the_whole_transaction(self):
        batch = self.batch()
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute(
                "UPDATE documents SET document_status = 'draft' WHERE id = ?",
                (self.document.id,),
            )
        with self.assertRaises(AgilePersistenceError):
            save_accepted_agile_batch(batch, self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM agile_generation_runs").fetchone()[0],
                0,
            )

    def test_document_edit_or_delete_does_not_rewrite_provenance_snapshot(self):
        saved, _ = save_accepted_agile_batch(self.batch(), self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                "UPDATE documents SET title = 'Changed title' WHERE id = ?",
                (self.document.id,),
            )
            snapshot_after_edit = connection.execute(
                "SELECT document_title FROM agile_source_snapshots"
            ).fetchone()[0]
            connection.execute("DELETE FROM documents WHERE id = ?", (self.document.id,))
            snapshot_after_delete = connection.execute(
                "SELECT document_title FROM agile_source_snapshots"
            ).fetchone()[0]
        self.assertEqual(snapshot_after_edit, self.document.title)
        self.assertEqual(snapshot_after_delete, self.document.title)
        self.assertEqual(get_accepted_agile_batch(saved.batch_id, self.database_path), saved)

    def test_product_delete_cascades_all_accepted_agile_records(self):
        save_accepted_agile_batch(self.batch(), self.database_path)
        self.assertTrue(delete_product(self.product.id, self.database_path))
        with closing(sqlite3.connect(self.database_path)) as connection:
            for table in AGILE_TABLES:
                with self.subTest(table=table):
                    self.assertEqual(
                        connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0],
                        0,
                    )

    def test_database_rejects_unsafe_direct_hierarchy_and_criteria_writes(self):
        save_accepted_agile_batch(self.batch(), self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO agile_artifacts (
                        artifact_id, batch_id, product_id, artifact_type, title,
                        description, parent_artifact_id, position, review_state,
                        provenance, revision, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "unsafe-feature", "batch-1", self.product.id, "feature",
                        "Unsafe", "Wrong parent type.", "artifact-1", 5,
                        "accepted", "ai_generated", 1, TIMESTAMP, TIMESTAMP,
                    ),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO agile_acceptance_criteria
                        (criterion_id, artifact_id, position, criterion_text)
                    VALUES ('empty-criterion', 'artifact-1', 2, '   ')
                    """
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO agile_acceptance_criteria
                        (criterion_id, artifact_id, position, criterion_text)
                    VALUES ('duplicate-text', 'artifact-1', 2, ?)
                    """,
                    (self.batch().artifacts[0].acceptance_criteria[0].text.upper(),),
                )

    def test_provenance_snapshots_reject_direct_updates(self):
        save_accepted_agile_batch(self.batch(), self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE agile_source_snapshots SET document_title = 'Rewritten'"
                )


if __name__ == "__main__":
    unittest.main()
