"""Deterministic checks for Phase 10 release and governance metadata."""

import re
import unittest
from pathlib import Path

from src.version import RELEASE_STATUS, RELEASE_TAG, __version__


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def repository_text(relative_path: str) -> str:
    return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")


class ReleaseVersionTests(unittest.TestCase):
    def test_version_metadata_uses_planned_semantic_v1_release(self):
        self.assertRegex(__version__, r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
        self.assertEqual(__version__, "1.0.0")
        self.assertEqual(RELEASE_TAG, "v1.0.0")
        self.assertEqual(RELEASE_STATUS, "planned")

    def test_version_is_consistent_across_release_documents(self):
        for filename in (
            "CHANGELOG.md",
            "CONTRIBUTING.md",
            "IMPLEMENTATION_PLAN.md",
            "PROJECT_SPEC.md",
            "README.md",
            "SECURITY.md",
        ):
            with self.subTest(filename=filename):
                content = repository_text(filename)
                self.assertIn("v1.0.0", content)

    def test_changelog_does_not_claim_the_planned_release_is_published(self):
        changelog = repository_text("CHANGELOG.md")
        self.assertIn("## [Unreleased]", changelog)
        self.assertIn("has not been tagged or published", changelog)


class GovernanceFileTests(unittest.TestCase):
    def test_required_governance_files_exist_and_are_not_empty(self):
        for filename in ("LICENSE", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md"):
            with self.subTest(filename=filename):
                path = REPOSITORY_ROOT / filename
                self.assertTrue(path.is_file())
                self.assertTrue(path.read_text(encoding="utf-8").strip())

    def test_license_is_mit_for_celso_guerra(self):
        license_text = repository_text("LICENSE")
        self.assertTrue(license_text.startswith("MIT License"))
        self.assertIn(
            "Copyright (c) 2026 Celso Guerra",
            license_text,
        )
        self.assertIn("Permission is hereby granted, free of charge", license_text)
        self.assertIn('THE SOFTWARE IS PROVIDED "AS IS"', license_text)

    def test_security_policy_documents_local_and_optional_ai_boundaries(self):
        security = repository_text("SECURITY.md")
        normalized_security = " ".join(security.split())
        for required in (
            "single-user local application",
            "No published version is currently supported",
            "process environment",
            "Approved BRD and PRD content is sent",
            "Never include a real OpenAI API key",
        ):
            self.assertIn(required, normalized_security)

    def test_direct_dependency_policy_preserves_the_checkpoint_1_baseline(self):
        requirements = repository_text("requirements.txt").splitlines()
        self.assertEqual(
            requirements,
            ["streamlit", "pandas", "openai>=2.45.0,<3.0.0"],
        )
        contributing = repository_text("CONTRIBUTING.md")
        self.assertIn("direct runtime dependencies", contributing)

    def test_protected_screenshot_has_an_exact_ignore_rule(self):
        ignore_lines = repository_text(".gitignore").splitlines()
        self.assertIn(
            "/Screenshot 2026-08-01 at 10.54.51.png",
            ignore_lines,
        )
        self.assertEqual(
            sum(
                line == "/Screenshot 2026-08-01 at 10.54.51.png"
                for line in ignore_lines
            ),
            1,
        )

    def test_governance_documents_contain_no_key_shaped_secret(self):
        key_pattern = re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")
        for filename in ("LICENSE", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md"):
            with self.subTest(filename=filename):
                self.assertIsNone(key_pattern.search(repository_text(filename)))


if __name__ == "__main__":
    unittest.main()
