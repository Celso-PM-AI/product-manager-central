"""Deterministic tests for the explicit-allowlist PMC release builder."""

import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from scripts.build_release import (
    ARCHIVE_NAME,
    ARCHIVE_ROOT,
    CHECKSUM_NAME,
    PROTECTED_SCREENSHOT,
    ReleaseBuildError,
    build_release,
    expected_archive_members,
    load_release_manifest,
    sha256_file,
    validate_archive,
)
from src.database import list_products


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ReleasePackageTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    def copy_allowlisted_repository(self) -> Path:
        copied = self.root / "repository"
        entries = load_release_manifest(REPOSITORY_ROOT)
        for entry in entries:
            source = REPOSITORY_ROOT / entry
            destination = copied / entry
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        return copied


class ManifestValidationTests(ReleasePackageTestCase):
    def test_local_release_outputs_are_ignored(self):
        ignore_lines = (REPOSITORY_ROOT / ".gitignore").read_text(
            encoding="utf-8"
        ).splitlines()
        self.assertIn("/dist/", ignore_lines)
        self.assertIn("/build/", ignore_lines)
        self.assertIn("/product-manager-central-v*.zip", ignore_lines)
        self.assertIn("/product-manager-central-v*.zip.sha256", ignore_lines)

    def test_manifest_is_explicit_complete_and_contains_no_forbidden_artifacts(self):
        entries = load_release_manifest(REPOSITORY_ROOT)

        self.assertIn("app.py", entries)
        self.assertIn("requirements.txt", entries)
        self.assertIn("scripts/setup_macos.command", entries)
        self.assertIn("scripts/start_pmc_macos.command", entries)
        self.assertIn("scripts/setup_windows.ps1", entries)
        self.assertIn("src/sample_data.py", entries)
        self.assertIn("src/document_export.py", entries)
        self.assertNotIn("data/pmc.db", entries)
        self.assertNotIn(PROTECTED_SCREENSHOT, entries)
        self.assertFalse(any("*" in entry for entry in entries))
        self.assertFalse(any(entry.startswith("tests/") for entry in entries))

    def test_forbidden_manifest_entry_fails_closed(self):
        copied = self.copy_allowlisted_repository()
        with (copied / "release_manifest.txt").open("a", encoding="utf-8") as manifest:
            manifest.write("data/pmc.db\n")

        with self.assertRaisesRegex(ReleaseBuildError, "Forbidden"):
            load_release_manifest(copied)

    def test_missing_required_source_file_fails_closed(self):
        copied = self.copy_allowlisted_repository()
        (copied / "app.py").unlink()

        with self.assertRaisesRegex(ReleaseBuildError, "missing"):
            load_release_manifest(copied)


class ArchiveBuildTests(ReleasePackageTestCase):
    def test_build_uses_version_name_checksum_and_exact_allowlist(self):
        output = self.root / "output"
        result = build_release(output)
        entries = load_release_manifest(REPOSITORY_ROOT)

        self.assertEqual(result.archive_path.name, ARCHIVE_NAME)
        self.assertEqual(result.checksum_path.name, CHECKSUM_NAME)
        self.assertEqual(result.sha256, sha256_file(result.archive_path))
        self.assertEqual(result.members, expected_archive_members(entries))
        self.assertEqual(
            result.checksum_path.read_text(encoding="utf-8"),
            f"{result.sha256}  {ARCHIVE_NAME}\n",
        )
        validate_archive(result.archive_path, entries)
        self.assertFalse(any(member.endswith(".db") for member in result.members))
        self.assertFalse(any(PROTECTED_SCREENSHOT in member for member in result.members))

    def test_build_is_byte_reproducible(self):
        first = build_release(self.root / "first")
        second = build_release(self.root / "second")

        self.assertEqual(first.sha256, second.sha256)
        self.assertEqual(first.archive_path.read_bytes(), second.archive_path.read_bytes())

    def test_unexpected_repository_file_cannot_enter_archive(self):
        copied = self.copy_allowlisted_repository()
        unexpected = copied / "private-notes.txt"
        unexpected.write_text("This unrelated file must not be packaged.")

        result = build_release(self.root / "output", repository_root=copied)

        self.assertFalse(any("private-notes.txt" in member for member in result.members))

    def test_existing_output_requires_explicit_force(self):
        output = self.root / "output"
        first = build_release(output)

        with self.assertRaisesRegex(ReleaseBuildError, "already exists"):
            build_release(output)
        replaced = build_release(output, force=True)

        self.assertEqual(replaced.sha256, first.sha256)

    def test_archive_validation_rejects_an_unexpected_member(self):
        result = build_release(self.root / "output")
        with zipfile.ZipFile(result.archive_path, "a") as archive:
            archive.writestr(f"{ARCHIVE_ROOT}/unexpected.txt", "unexpected")

        with self.assertRaisesRegex(ReleaseBuildError, "exactly match"):
            validate_archive(
                result.archive_path,
                load_release_manifest(REPOSITORY_ROOT),
            )

    def test_extracted_package_starts_clean_without_sample_or_openai_call(self):
        result = build_release(self.root / "output")
        extraction = self.root / "extracted"
        with zipfile.ZipFile(result.archive_path) as archive:
            archive.extractall(extraction)
        package = extraction / ARCHIVE_ROOT
        database = self.root / "clean-start.db"
        original_database = os.environ.get("PMC_DATABASE_FILE")
        original_key = os.environ.get("OPENAI_API_KEY")
        os.environ["PMC_DATABASE_FILE"] = str(database)
        os.environ.pop("OPENAI_API_KEY", None)
        try:
            with patch("src.ai_service.OpenAIService.from_environment") as openai:
                app = AppTest.from_file(package / "app.py").run()
            self.assertEqual(list(app.exception), [])
            self.assertEqual(list_products(database), [])
            openai.assert_not_called()
        finally:
            if original_database is None:
                os.environ.pop("PMC_DATABASE_FILE", None)
            else:
                os.environ["PMC_DATABASE_FILE"] = original_database
            if original_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = original_key


if __name__ == "__main__":
    unittest.main()
