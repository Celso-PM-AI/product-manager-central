"""Deterministic checks for Phase 10 release and governance metadata."""

import re
import unittest
from pathlib import Path

from src.version import RELEASE_STATUS, RELEASE_TAG, __version__


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def repository_text(relative_path: str) -> str:
    return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")


class ReleaseVersionTests(unittest.TestCase):
    def test_version_metadata_uses_controlled_beta_patch_release(self):
        self.assertRegex(__version__, r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
        self.assertEqual(__version__, "1.0.1")
        self.assertEqual(RELEASE_TAG, "v1.0.1")
        self.assertEqual(RELEASE_STATUS, "controlled-beta")

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
                self.assertIn("v1.0.1", content)

    def test_changelog_preserves_published_baseline_and_unpublished_candidate(self):
        changelog = repository_text("CHANGELOG.md")
        self.assertIn("## [Unreleased]", changelog)
        self.assertIn("## [1.0.0] - 2026-08-19", changelog)
        self.assertIn("v1.0.1 has not been committed, tagged", " ".join(changelog.split()))


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
            "v1.0.0 is the published portfolio baseline",
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
                "python-docx==1.2.0",
                "reportlab==5.0.0",
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
        for number in range(1, 30):
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
                self.assertEqual(guide.count(required_field), 29)
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

    def test_checkpoint4_preserves_checkpoint5_and_checkpoint6_boundaries(self):
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
        self.assertIn("## Checkpoint 5:", plan)
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

    def test_checkpoint4_record_preserves_protected_screenshot_boundary(self):
        readme = repository_text("README.md")
        guide = repository_text("docs/UAT_BETA_GUIDE.md")
        manifest = repository_text("release_manifest.txt").splitlines()
        self.assertIn(
            "![Product Manager Central fictional dashboard](docs/images/pmc-v1-dashboard-fictional.png)",
            readme,
        )
        self.assertIn("Checkpoint 5", guide)
        self.assertNotIn("Screenshot 2026-08-01 at 10.54.51.png", manifest)


class Checkpoint5PortfolioTests(unittest.TestCase):
    portfolio_documents = (
        "docs/PORTFOLIO_CASE_STUDY.md",
        "docs/ARCHITECTURE.md",
        "docs/DEMO_STORYBOARD.md",
        "docs/LAUNCH_MATERIALS.md",
    )
    screenshot_paths = (
        "docs/images/pmc-v1-dashboard-fictional.png",
        "docs/images/pmc-v1-product-documents-fictional.png",
        "docs/images/pmc-v1-ai-review-fictional.png",
    )

    def test_portfolio_documents_are_complete_allowlisted_and_linked(self):
        manifest = repository_text("release_manifest.txt").splitlines()
        readme = repository_text("README.md")
        for path in (*self.portfolio_documents, *self.screenshot_paths):
            with self.subTest(path=path):
                self.assertTrue((REPOSITORY_ROOT / path).is_file())
                self.assertIn(path, manifest)
        for path in self.portfolio_documents[:3]:
            with self.subTest(readme_link=path):
                self.assertIn(path, readme)

    def test_case_study_preserves_trust_controls_and_evidence_boundaries(self):
        case_study = " ".join(
            repository_text("docs/PORTFOLIO_CASE_STUDY.md").split()
        )
        for required in (
            "Approved BRDs and PRDs",
            "visible citations",
            "explicit acceptance",
            "Eligibility is checked again at acceptance",
            "Generated artifacts remain separate",
            "never appends to, overwrites, or otherwise modifies a source BRD or PRD",
            "Windows launchers and Python 3.11 through 3.13 have structural automated coverage",
            "does not claim an external beta",
            "Checkpoint 15 improves controlled-beta onboarding",
        ):
            with self.subTest(required=required):
                self.assertIn(required, case_study)

    def test_architecture_documents_data_ai_and_package_boundaries(self):
        architecture = repository_text("docs/ARCHITECTURE.md")
        self.assertEqual(architecture.count("```mermaid"), 3)
        for required in (
            "Streamlit interface",
            "SQLite persistence",
            "Approved BRD and PRD sections",
            "Optional OpenAI boundary",
            "Revalidate cited sources again",
            "Original BRDs and PRDs",
            "Separate generated-artifact store",
            "release_manifest.txt",
            "Exact member and checksum validation",
        ):
            with self.subTest(required=required):
                self.assertIn(required, architecture)

    def test_storyboard_and_launch_materials_remain_drafts(self):
        storyboard = " ".join(repository_text("docs/DEMO_STORYBOARD.md").split())
        launch = " ".join(repository_text("docs/LAUNCH_MATERIALS.md").split())
        for required in (
            "**Target duration:** 3 minutes 20 seconds",
            "The demo video has not been recorded",
            "deterministic fake provider",
            "Accept and save",
            "stores an artifact separately",
        ):
            with self.subTest(storyboard=required):
                self.assertIn(required, storyboard)
        for required in (
            "Draft LinkedIn post",
            "Résumé bullets",
            "Interview talking points",
            "Concise portfolio summary",
            "have not been posted, sent, or uploaded",
            "no external-beta or customer outcome is claimed",
        ):
            with self.subTest(launch=required):
                self.assertIn(required, launch)

    def test_screenshots_are_exact_sanitized_png_set_without_metadata(self):
        image_directory = REPOSITORY_ROOT / "docs/images"
        self.assertEqual(
            sorted(path.name for path in image_directory.iterdir() if path.is_file()),
            sorted(Path(path).name for path in self.screenshot_paths),
        )
        forbidden_chunks = {b"tEXt", b"zTXt", b"iTXt", b"eXIf"}
        for relative_path in self.screenshot_paths:
            with self.subTest(relative_path=relative_path):
                content = (REPOSITORY_ROOT / relative_path).read_bytes()
                self.assertEqual(content[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(int.from_bytes(content[16:20], "big"), 1600)
                self.assertEqual(int.from_bytes(content[20:24], "big"), 1200)
                chunk_types = set()
                offset = 8
                while offset < len(content):
                    length = int.from_bytes(content[offset : offset + 4], "big")
                    chunk_type = content[offset + 4 : offset + 8]
                    chunk_types.add(chunk_type)
                    offset += 12 + length
                    if chunk_type == b"IEND":
                        break
                self.assertTrue(forbidden_chunks.isdisjoint(chunk_types))
                self.assertIn(b"IEND", chunk_types)

    def test_old_preview_is_removed_and_checkpoint6_is_not_started(self):
        old_path = REPOSITORY_ROOT / "docs/images/pmc-phase8-application.png"
        self.assertFalse(old_path.exists())
        manifest = repository_text("release_manifest.txt")
        readme = repository_text("README.md")
        plan = " ".join(repository_text("IMPLEMENTATION_PLAN.md").split())
        self.assertNotIn("pmc-phase8-application.png", manifest)
        self.assertNotIn("pmc-phase8-application.png", readme)
        self.assertIn(
            "Checkpoint 6: Release-candidate verification and GitHub release preparation — Not started",
            plan,
        )


if __name__ == "__main__":
    unittest.main()
