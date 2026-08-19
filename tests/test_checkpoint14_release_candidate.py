"""Focused release-candidate gates for Phase 10 Checkpoint 14."""

import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from streamlit.testing.v1 import AppTest

from scripts.build_release import (
    ARCHIVE_NAME,
    ARCHIVE_ROOT,
    CHECKSUM_NAME,
    build_release,
    expected_archive_members,
    load_release_manifest,
)
from src.database import list_products
from src.version import RELEASE_STATUS, RELEASE_TAG, __version__


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RELEASE_NOTES = REPOSITORY_ROOT / "docs/RELEASE_NOTES_v1.0.0.md"
EXPECTED_DIRECT_DEPENDENCIES = {
    "streamlit==1.61.1": "Apache-2.0",
    "pandas==3.0.5": "BSD-3-Clause",
    "openai==2.53.0": "Apache-2.0",
    "python-docx==1.2.0": "MIT",
    "reportlab==5.0.0": "BSD",
}


class ReleaseCandidateTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)


class ReleaseCandidateMetadataTests(ReleaseCandidateTestCase):
    def test_version_and_proposed_github_release_metadata_are_consistent(self):
        notes = RELEASE_NOTES.read_text(encoding="utf-8")
        self.assertEqual((__version__, RELEASE_TAG, RELEASE_STATUS), ("1.0.0", "v1.0.0", "planned"))
        self.assertIn("**Tag:** `v1.0.0`", notes)
        self.assertIn("**Title:** `Product Manager Central v1.0.0`", notes)
        self.assertIn(f"**Source asset:** `{ARCHIVE_NAME}`", notes)
        self.assertIn(f"**Checksum asset:** `{CHECKSUM_NAME}`", notes)

    def test_release_notes_keep_publication_separate_and_list_limitations(self):
        notes = RELEASE_NOTES.read_text(encoding="utf-8")
        normalized = " ".join(notes.split()).lower()
        for phrase in (
            "has not been tagged, published, or made available through a GitHub Release",
            "## Known limitations",
            "single-user and local only",
            "No live-provider quality claim",
            "requires a separate explicit approval",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), normalized)

    def test_compatibility_matrix_has_one_native_row_and_structural_boundaries(self):
        notes = RELEASE_NOTES.read_text(encoding="utf-8")
        self.assertIn("macOS 26.5.2 arm64 | 3.14.6 | Passed | Passed | Passed", notes)
        self.assertIn("macOS | 3.11-3.13 | Not run natively", notes)
        self.assertIn("Windows | 3.11-3.14 | Not run natively", notes)
        self.assertIn("The sole native claim", notes)

    def test_direct_dependency_versions_and_licenses_are_inventoried(self):
        requirements = set((REPOSITORY_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines())
        notes = RELEASE_NOTES.read_text(encoding="utf-8")
        self.assertEqual(requirements, set(EXPECTED_DIRECT_DEPENDENCIES))
        for requirement, license_name in EXPECTED_DIRECT_DEPENDENCIES.items():
            name, version = requirement.split("==")
            with self.subTest(requirement=requirement):
                self.assertIn(f"{name} {version}".lower(), notes.lower())
                self.assertIn(license_name.lower(), notes.lower())

    def test_checkpoint14_status_is_complete_without_release_claim(self):
        for relative_path in (
            "README.md",
            "PROJECT_SPEC.md",
            "IMPLEMENTATION_PLAN.md",
            "docs/UAT_BETA_GUIDE.md",
        ):
            with self.subTest(relative_path=relative_path):
                text = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("Checkpoint 14", text)
                self.assertIn("complete", text.lower())
                normalized = " ".join(text.split()).lower()
                self.assertTrue(any(word in normalized for word in ("not tagged", "not been tagged", "no tag")))


class ReleaseCandidateArchiveTests(ReleaseCandidateTestCase):
    def test_manifest_includes_release_notes_and_excludes_prohibited_artifacts(self):
        entries = load_release_manifest(REPOSITORY_ROOT)
        self.assertIn("docs/RELEASE_NOTES_v1.0.0.md", entries)
        forbidden = re.compile(r"(?:^|/)(?:data|backups|tests|\.git|\.venv)(?:/|$)|\.(?:db|docx|pdf|pyc|zip)$")
        self.assertFalse(any(forbidden.search(entry) for entry in entries))
        self.assertFalse(any("Screenshot 2026" in entry for entry in entries))

    def test_archive_has_exact_order_timestamps_and_permissions(self):
        result = build_release(self.root / "candidate")
        entries = load_release_manifest(REPOSITORY_ROOT)
        with zipfile.ZipFile(result.archive_path) as archive:
            infos = archive.infolist()
        self.assertEqual([info.filename for info in infos], list(expected_archive_members(entries)))
        self.assertEqual({info.date_time for info in infos}, {(2026, 1, 1, 0, 0, 0)})
        for info in infos:
            expected_mode = 0o755 if info.filename.endswith(".command") else 0o644
            self.assertEqual((info.external_attr >> 16) & 0o777, expected_mode)

    def test_checksum_matches_exact_archive_bytes_and_sidecar(self):
        result = build_release(self.root / "candidate")
        digest = hashlib.sha256(result.archive_path.read_bytes()).hexdigest()
        self.assertEqual(result.sha256, digest)
        self.assertEqual(result.checksum_path.read_text(encoding="utf-8"), f"{digest}  {ARCHIVE_NAME}\n")

    def test_candidate_build_is_byte_reproducible(self):
        first = build_release(self.root / "first")
        second = build_release(self.root / "second")
        self.assertEqual(first.sha256, second.sha256)
        self.assertEqual(first.archive_path.read_bytes(), second.archive_path.read_bytes())

    def test_archive_contains_no_key_shaped_secret_or_database_name(self):
        result = build_release(self.root / "candidate")
        key_pattern = re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")
        with zipfile.ZipFile(result.archive_path) as archive:
            for info in archive.infolist():
                with self.subTest(member=info.filename):
                    content = archive.read(info)
                    self.assertIsNone(key_pattern.search(content))
                    self.assertNotIn(b"data/pmc.db", content if info.filename.endswith("release_manifest.txt") else b"")


class ReleaseCandidateRuntimeTests(ReleaseCandidateTestCase):
    def extract_candidate(self) -> Path:
        result = build_release(self.root / "candidate")
        extraction = self.root / "extracted"
        with zipfile.ZipFile(result.archive_path) as archive:
            archive.extractall(extraction)
        return extraction / ARCHIVE_ROOT

    def test_extracted_candidate_starts_empty_without_key_or_provider_call(self):
        package = self.extract_candidate()
        database = self.root / "no-key.db"
        original_database = os.environ.get("PMC_DATABASE_FILE")
        original_key = os.environ.pop("OPENAI_API_KEY", None)
        os.environ["PMC_DATABASE_FILE"] = str(database)
        try:
            with patch("src.ai_service.OpenAIService.from_environment") as provider:
                app = AppTest.from_file(package / "app.py", default_timeout=8).run()
            self.assertEqual(list(app.exception), [])
            self.assertEqual(tuple(app.radio[0].options), (
                "Dashboard", "Create Product", "Create PRD", "Create BRD",
                "AI Assistant", "View Products", "Search Products",
            ))
            self.assertEqual(list_products(database), [])
            provider.assert_not_called()
        finally:
            if original_database is None:
                os.environ.pop("PMC_DATABASE_FILE", None)
            else:
                os.environ["PMC_DATABASE_FILE"] = original_database
            if original_key is not None:
                os.environ["OPENAI_API_KEY"] = original_key

    def test_extracted_candidate_loads_only_explicit_english_named_fictional_sample(self):
        package = self.extract_candidate()
        database = self.root / "sample.db"
        script = (
            "from src.database import initialize_database; "
            "from src.sample_data import load_fictional_sample_data; "
            f"p={str(database)!r}; initialize_database(p); r=load_fictional_sample_data(p); "
            "print(r.product.name); print(repr(r))"
        )
        environment = os.environ.copy()
        environment.pop("OPENAI_API_KEY", None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [sys.executable, "-c", script], cwd=package, env=environment,
            check=True, capture_output=True, text=True,
        )
        self.assertIn("[Fictional Sample] Trailwise", completed.stdout)
        self.assertNotIn("東京", completed.stdout)
        self.assertNotIn("李", completed.stdout)


if __name__ == "__main__":
    unittest.main()
