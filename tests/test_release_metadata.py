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
            "docs/INSTALLATION.md",
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

    def test_license_is_mit_for_celso_goncalves_guerra(self):
        license_text = repository_text("LICENSE")
        self.assertTrue(license_text.startswith("MIT License"))
        self.assertIn(
            "Copyright (c) 2026 Celso Gonçalves Guerra",
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

    def test_direct_dependencies_match_clean_install_validation(self):
        requirements = repository_text("requirements.txt").splitlines()
        self.assertEqual(
            requirements,
            [
                "streamlit==1.61.1",
                "pandas==3.0.5",
                "openai==2.53.0",
            ],
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


class Checkpoint4DocumentationTests(unittest.TestCase):
    def test_checkpoint4_guide_has_complete_scenarios_and_evidence_boundaries(self):
        guide = repository_text("docs/UAT_BETA_GUIDE.md")
        normalized_guide = " ".join(guide.split())
        for number in range(1, 18):
            scenario = f"UAT-{number:02d}"
            with self.subTest(scenario=scenario):
                self.assertEqual(guide.count(f"### {scenario} —"), 1)
        for required_field in (
            "**Preconditions:**",
            "**Steps:**",
            "**Expected result:**",
            "**Pass/fail:**",
            "**Evidence:**",
            "**Status:**",
        ):
            with self.subTest(required_field=required_field):
                self.assertEqual(guide.count(required_field), 17)
        for required_statement in (
            "four to six Product Managers",
            "no participant was contacted",
            "have **not** been natively validated",
            "does not use a real API key or make a live OpenAI API call",
            "Approved-only",
            "explicit acceptance",
            "source-document mutation",
        ):
            with self.subTest(required_statement=required_statement):
                self.assertIn(required_statement, normalized_guide)

    def test_checkpoint4_guide_is_linked_and_allowlisted(self):
        guide_path = "docs/UAT_BETA_GUIDE.md"
        self.assertIn(guide_path, repository_text("release_manifest.txt").splitlines())
        self.assertIn(guide_path, repository_text("README.md"))
        self.assertIn("UAT_BETA_GUIDE.md", repository_text("docs/INSTALLATION.md"))

    def test_checkpoint4_preserves_later_checkpoint_boundaries(self):
        plan = repository_text("IMPLEMENTATION_PLAN.md")
        self.assertIn(
            "## Checkpoint 4: UAT, beta preparation, and responsible use",
            plan,
        )
        self.assertIn("the complete 246-test suite", plan)
        self.assertIn(
            "Checkpoint 5: Recruiter case study, architecture diagram, sanitized",
            plan,
        )
        self.assertIn(
            "Checkpoint 6: Release-candidate verification and GitHub release preparation",
            plan,
        )
        self.assertNotIn("## Checkpoint 5:", plan)
        self.assertNotIn("## Checkpoint 6:", plan)

    def test_checkpoint4_operational_guidance_preserves_local_data_safeguards(self):
        installation = repository_text("docs/INSTALLATION.md")
        normalized_installation = " ".join(installation.split())
        for heading in (
            "## Back up and restore data",
            "## Update to a future approved release",
            "## Remove PMC",
            "## Verify the release checksum",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, installation)
        for safeguard in (
            "Always stop PMC before copying or replacing its database.",
            "do not extract it over the existing installation",
            "PMC provides no automated uninstall or database deletion command.",
            "The two hexadecimal SHA-256 values must match exactly.",
        ):
            with self.subTest(safeguard=safeguard):
                self.assertIn(safeguard, normalized_installation)

    def test_checkpoint4_keeps_existing_preview_and_defers_screenshot_work(self):
        readme = repository_text("README.md")
        guide = repository_text("docs/UAT_BETA_GUIDE.md")
        manifest = repository_text("release_manifest.txt").splitlines()
        self.assertIn(
            "![Product Manager Central application](docs/images/pmc-phase8-application.png)",
            readme,
        )
        self.assertIn("deferred to Phase 10 Checkpoint 5", guide)
        self.assertNotIn("Screenshot 2026-08-01 at 10.54.51.png", manifest)


if __name__ == "__main__":
    unittest.main()
