"""Structural and safe executable tests for Mac and Windows launch helpers."""

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MAC_SETUP = REPOSITORY_ROOT / "scripts" / "setup_macos.command"
MAC_RUN = REPOSITORY_ROOT / "scripts" / "run_macos.command"
WINDOWS_SETUP = REPOSITORY_ROOT / "scripts" / "setup_windows.ps1"
WINDOWS_RUN = REPOSITORY_ROOT / "scripts" / "run_windows.ps1"


class LauncherStructureTests(unittest.TestCase):
    def test_mac_helpers_are_executable_and_resolve_the_application_directory(self):
        for path in (MAC_SETUP, MAC_RUN):
            with self.subTest(path=path.name):
                content = path.read_text(encoding="utf-8")
                self.assertTrue(path.stat().st_mode & stat.S_IXUSR)
                self.assertIn('dirname -- "$0"', content)
                self.assertIn('cd "$APP_DIR"', content)
                self.assertNotIn(str(REPOSITORY_ROOT), content)

        setup = MAC_SETUP.read_text(encoding="utf-8")
        run = MAC_RUN.read_text(encoding="utf-8")
        self.assertIn('"$PYTHON_COMMAND" -m venv .venv', setup)
        self.assertIn('-m pip install --disable-pip-version-check -r requirements.txt', setup)
        self.assertIn('"$VENV_PYTHON" -m streamlit run "$APP_DIR/app.py"', run)

    def test_windows_helpers_resolve_paths_and_use_the_venv_python(self):
        setup = WINDOWS_SETUP.read_text(encoding="utf-8")
        run = WINDOWS_RUN.read_text(encoding="utf-8")
        for content in (setup, run):
            self.assertIn("Split-Path -Parent $PSScriptRoot", content)
            self.assertIn("Set-Location $AppDir", content)
            self.assertNotIn(str(REPOSITORY_ROOT), content)
            self.assertNotIn("/bin/", content)

        self.assertIn("-m venv", setup)
        self.assertIn("-m pip install", setup)
        self.assertIn('Join-Path $AppDir "requirements.txt"', setup)
        self.assertIn("-m streamlit run", run)
        self.assertIn('Join-Path $AppDir "app.py"', run)

    def test_helpers_enforce_python_range_and_have_actionable_errors(self):
        for path in (MAC_SETUP, MAC_RUN, WINDOWS_SETUP, WINDOWS_RUN):
            with self.subTest(path=path.name):
                content = path.read_text(encoding="utf-8")
                self.assertIn("(3, 11)", content)
                self.assertIn("(3, 14)", content)
                self.assertIn("Python 3.11 through 3.14", content)

        result = subprocess.run(
            [str(MAC_SETUP)],
            cwd="/",
            env={**os.environ, "PMC_PYTHON": "/missing/pmc-python"},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python was not found", result.stderr)

    def test_api_key_prompts_are_masked_temporary_and_never_persisted(self):
        mac = MAC_RUN.read_text(encoding="utf-8")
        windows = WINDOWS_RUN.read_text(encoding="utf-8")
        self.assertIn("read -r -s", mac)
        self.assertIn("unset OPENAI_API_KEY", mac)
        self.assertNotIn("echo $OPENAI_API_KEY", mac)
        self.assertIn("-AsSecureString", windows)
        self.assertIn("Remove-Item Env:OPENAI_API_KEY", windows)
        for content in (mac, windows):
            self.assertNotIn(".env", content)
            self.assertNotIn("Set-Content", content)
            self.assertNotIn("Out-File", content)


class MacLauncherExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name) / "package"
        self.scripts = self.root / "scripts"
        self.venv_bin = self.root / ".venv" / "bin"
        self.scripts.mkdir(parents=True)
        self.venv_bin.mkdir(parents=True)
        self.launcher = self.scripts / MAC_RUN.name
        self.launcher.write_bytes(MAC_RUN.read_bytes())
        self.launcher.chmod(0o755)
        (self.root / "app.py").write_text("# isolated launcher fixture\n")

    def _write_fake_python(self, body: str) -> Path:
        fake = self.venv_bin / "python"
        fake.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        fake.chmod(0o755)
        return fake

    def test_missing_dependencies_stop_with_actionable_error(self):
        self._write_fake_python(
            'case "$*" in *"import openai"*) exit 7;; *) exit 0;; esac\n'
        )
        result = subprocess.run(
            [str(self.launcher)],
            cwd="/",
            stdin=subprocess.DEVNULL,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dependencies are missing or incomplete", result.stderr)

    def test_launcher_uses_its_application_directory_and_does_not_expose_key(self):
        log = Path(self.temporary_directory.name) / "launch.log"
        self._write_fake_python(
            'case "$*" in\n'
            '  *"import sys"*|*"import openai"*) exit 0;;\n'
            '  *) printf "%s\\n%s\\n" "$PWD" "$*" > "$PMC_LAUNCH_LOG"; exit 0;;\n'
            "esac\n"
        )
        fake_key = "test-only-placeholder-not-a-real-key"
        result = subprocess.run(
            [str(self.launcher)],
            cwd="/",
            stdin=subprocess.DEVNULL,
            env={
                **os.environ,
                "OPENAI_API_KEY": fake_key,
                "PMC_LAUNCH_LOG": str(log),
            },
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        recorded = log.read_text(encoding="utf-8")
        self.assertEqual(recorded.splitlines()[0], str(self.root))
        self.assertIn(f"-m streamlit run {self.root / 'app.py'}", recorded)
        self.assertNotIn(fake_key, result.stdout + result.stderr + recorded)


if __name__ == "__main__":
    unittest.main()
