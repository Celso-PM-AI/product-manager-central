"""Focused Checkpoint 15 onboarding and positioning checks."""

import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.version import RELEASE_STATUS, RELEASE_TAG, __version__


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
APP_FILE = REPOSITORY_ROOT / "app.py"


def repository_text(relative_path: str) -> str:
    return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")


class Checkpoint15MetadataTests(unittest.TestCase):
    def test_v101_is_controlled_beta_and_v100_history_is_preserved(self):
        self.assertEqual((__version__, RELEASE_TAG, RELEASE_STATUS), (
            "1.0.1", "v1.0.1", "controlled-beta"
        ))
        notes = repository_text("docs/RELEASE_NOTES_v1.0.1.md")
        self.assertIn("controlled-beta/portfolio release", notes)
        self.assertIn("technical evaluation", notes)
        self.assertIn("not a commercial production application", notes)
        self.assertIn("not a signed or notarized native macOS application", notes)
        self.assertIn("Windows remains structural-only", notes)
        self.assertIn("v1.0.0 tag, GitHub Release, or uploaded assets", notes)

    def test_manifest_contains_new_starter_and_release_notes(self):
        manifest = repository_text("release_manifest.txt").splitlines()
        self.assertIn("scripts/start_pmc_macos.command", manifest)
        self.assertIn("docs/RELEASE_NOTES_v1.0.1.md", manifest)
        self.assertNotIn("data/pmc.db", manifest)


class Checkpoint15DocumentationTests(unittest.TestCase):
    def test_quick_start_is_first_and_separates_optional_steps(self):
        installation = repository_text("docs/INSTALLATION.md")
        self.assertLess(
            installation.index("## Quick Start for macOS"),
            installation.index("## Validated environment and prerequisites"),
        )
        for phrase in (
            "Under **Assets**",
            "Source code (zip)",
            "scripts/start_pmc_macos.command",
            "Control-click",
            "Privacy & Security",
            "Open Anyway",
            "Do not disable or bypass Gatekeeper",
            "Keep the Terminal window open",
            "Control-C",
            "## Optional checksum verification",
            "## Optional AI setup",
            "port 8501",
            "Python is missing or unsupported",
            "`.venv` is missing or installation failed",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, installation)

    def test_normal_startup_and_ai_boundaries_are_explicit(self):
        combined = " ".join("\n".join(
            repository_text(path)
            for path in (
                "README.md",
                "docs/INSTALLATION.md",
                "docs/RELEASE_NOTES_v1.0.1.md",
                "docs/PORTFOLIO_CASE_STUDY.md",
            )
        ).split())
        for phrase in (
            "Normal startup never asks for an API key",
            "Approved BRDs and PRDs",
            "Citations",
            "source-freshness",
            "claim-support",
            "human review",
            "explicit acceptance",
            "organization-approved",
            "does not automatically provide access to company information",
            "export-controlled",
            "temporary session environment variable",
            "documents, exports, screenshots",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), combined.lower())
        self.assertIsNone(re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", combined))


class Checkpoint15InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database = Path(self.temporary_directory.name) / "checkpoint15.db"
        self.original_database = os.environ.get("PMC_DATABASE_FILE")
        self.original_key = os.environ.pop("OPENAI_API_KEY", None)
        os.environ["PMC_DATABASE_FILE"] = str(self.database)
        self.addCleanup(self._restore_environment)

    def _restore_environment(self) -> None:
        if self.original_database is None:
            os.environ.pop("PMC_DATABASE_FILE", None)
        else:
            os.environ["PMC_DATABASE_FILE"] = self.original_database
        if self.original_key is not None:
            os.environ["OPENAI_API_KEY"] = self.original_key

    def test_dashboard_and_ai_assistant_explain_value_and_no_key_mode(self):
        with patch("src.ai_service.OpenAIService.from_environment") as provider:
            app = AppTest.from_file(APP_FILE).run()
            dashboard = " ".join(item.value for item in (*app.markdown, *app.caption))
            self.assertIn("grounded AI", dashboard)
            self.assertIn("without handing product decisions to AI", dashboard)

            app.radio[0].set_value("AI Assistant").run()
            assistant = " ".join(
                item.value
                for item in (*app.markdown, *app.caption, *app.info, *app.warning)
            ).replace("**", "")
            self.assertIn("AI does not write or approve product decisions independently", assistant)
            self.assertIn("AI Assistant status: Inactive", assistant)
            self.assertIn("AI-assisted Agile generation", assistant)
            self.assertIn("General draft generation", assistant)
            self.assertIn("valid API key supplied by you", assistant)
            self.assertIn("does not give PMC or the provider automatic access", assistant)
            self.assertIn("organization-approved key", assistant)
            self.assertIn("export-controlled", assistant)
            self.assertIn("documents, exports, screenshots", assistant)
            self.assertIn("Normal startup never asks for a key", assistant)
            self.assertIn("OPENAI_API_KEY", assistant)
            self.assertIn("explicit acceptance", assistant)
            provider.assert_not_called()

    def test_active_status_does_not_display_or_use_session_key(self):
        session_key = "checkpoint15-session-only-test-value"
        os.environ["OPENAI_API_KEY"] = session_key
        with patch("src.ai_service.OpenAIService.from_environment") as provider:
            app = AppTest.from_file(APP_FILE).run()
            app.radio[0].set_value("AI Assistant").run()
            assistant = " ".join(
                item.value
                for item in (*app.markdown, *app.caption, *app.success, *app.warning)
            ).replace("**", "")
            self.assertIn("AI Assistant status: Active", assistant)
            self.assertIn("provider validates the key", assistant)
            self.assertNotIn(session_key, assistant)
            provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()
