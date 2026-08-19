"""Build a deterministic PMC source ZIP from an explicit allowlist."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Sequence


REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.version import RELEASE_STATUS, RELEASE_TAG, __version__  # noqa: E402


MANIFEST_NAME: Final[str] = "release_manifest.txt"
ARCHIVE_ROOT: Final[str] = f"product-manager-central-{__version__}"
ARCHIVE_NAME: Final[str] = f"product-manager-central-{RELEASE_TAG}.zip"
CHECKSUM_NAME: Final[str] = f"{ARCHIVE_NAME}.sha256"
FIXED_ZIP_TIMESTAMP: Final[tuple[int, int, int, int, int, int]] = (
    2026,
    1,
    1,
    0,
    0,
    0,
)
PROTECTED_SCREENSHOT: Final[str] = "Screenshot 2026-08-01 at 10.54.51.png"
FORBIDDEN_PARTS: Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        ".cache",
        "backups",
        "data",
        "dist",
        "build",
    }
)
FORBIDDEN_SUFFIXES: Final[tuple[str, ...]] = (
    ".db",
    ".db-wal",
    ".db-shm",
    ".db-journal",
    ".sqlite",
    ".sqlite3",
    ".bak",
    ".backup",
    ".csv",
    ".env",
    ".pyc",
    ".pyo",
    ".zip",
    ".tar",
    ".tar.gz",
)
REQUIRED_RELEASE_FILES: Final[frozenset[str]] = frozenset(
    {
        "app.py",
        "requirements.txt",
        "LICENSE",
        "README.md",
        "docs/INSTALLATION.md",
        "release_manifest.txt",
        "scripts/start_pmc_macos.command",
        "scripts/setup_macos.command",
        "scripts/run_macos.command",
        "scripts/setup_windows.ps1",
        "scripts/run_windows.ps1",
        "src/__init__.py",
        "src/database.py",
        "src/version.py",
    }
)


class ReleaseBuildError(RuntimeError):
    """Raised when a release cannot be built safely from the allowlist."""


@dataclass(frozen=True)
class ReleaseBuildResult:
    """Paths and checksum for one locally built test archive."""

    archive_path: Path
    checksum_path: Path
    sha256: str
    members: tuple[str, ...]


def _is_forbidden(relative_path: str) -> bool:
    path = PurePosixPath(relative_path)
    lowered = relative_path.lower()
    return (
        relative_path == PROTECTED_SCREENSHOT
        or any(part in FORBIDDEN_PARTS for part in path.parts)
        or any(lowered.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES)
        or path.name.startswith(".env")
    )


def load_release_manifest(repository_root: Path = REPOSITORY_ROOT) -> tuple[str, ...]:
    """Load and validate the explicit source-release allowlist."""

    manifest_path = repository_root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ReleaseBuildError(f"Required manifest is missing: {MANIFEST_NAME}")
    entries = tuple(
        line.strip()
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not entries:
        raise ReleaseBuildError("The release manifest is empty.")
    if len(entries) != len(set(entries)):
        raise ReleaseBuildError("The release manifest contains a duplicate path.")
    missing_required = sorted(REQUIRED_RELEASE_FILES.difference(entries))
    if missing_required:
        raise ReleaseBuildError(
            "The release manifest omits required files: "
            + ", ".join(missing_required)
        )

    for entry in entries:
        path = PurePosixPath(entry)
        if path.is_absolute() or ".." in path.parts or str(path) != entry:
            raise ReleaseBuildError(f"Unsafe release-manifest path: {entry}")
        if _is_forbidden(entry):
            raise ReleaseBuildError(f"Forbidden release-manifest path: {entry}")
        source = repository_root / Path(*path.parts)
        if not source.is_file() or source.is_symlink():
            raise ReleaseBuildError(f"Required release file is missing: {entry}")
    return tuple(sorted(entries))


def expected_archive_members(entries: Sequence[str]) -> tuple[str, ...]:
    """Return the only archive members permitted by the manifest."""

    return tuple(f"{ARCHIVE_ROOT}/{entry}" for entry in sorted(entries))


def validate_archive(
    archive_path: Path,
    entries: Sequence[str],
) -> tuple[str, ...]:
    """Fail closed unless every ZIP member exactly matches the allowlist."""

    expected = expected_archive_members(entries)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            actual = tuple(sorted(archive.namelist()))
            bad_member = archive.testzip()
    except (OSError, zipfile.BadZipFile) as error:
        raise ReleaseBuildError("The release archive is unreadable.") from error
    if bad_member is not None:
        raise ReleaseBuildError(f"The release archive contains a corrupt file: {bad_member}")
    if actual != expected:
        raise ReleaseBuildError(
            "Archive members do not exactly match the approved release manifest."
        )
    if any(_is_forbidden(PurePosixPath(member).name) for member in actual):
        raise ReleaseBuildError("The release archive contains a forbidden file.")
    return actual


def sha256_file(path: Path) -> str:
    """Return a lowercase SHA-256 digest without loading the archive into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_archive(
    archive_path: Path,
    repository_root: Path,
    entries: Sequence[str],
) -> None:
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for entry in sorted(entries):
            source = repository_root / Path(*PurePosixPath(entry).parts)
            info = zipfile.ZipInfo(
                filename=f"{ARCHIVE_ROOT}/{entry}",
                date_time=FIXED_ZIP_TIMESTAMP,
            )
            info.create_system = 3
            mode = 0o755 if entry.endswith(".command") else 0o644
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes(), compresslevel=9)


def build_release(
    output_directory: Path,
    *,
    repository_root: Path = REPOSITORY_ROOT,
    force: bool = False,
) -> ReleaseBuildResult:
    """Build and verify one allowlisted source archive and checksum."""

    if RELEASE_STATUS != "controlled-beta" or RELEASE_TAG != f"v{__version__}":
        raise ReleaseBuildError("Release version metadata is inconsistent.")
    entries = load_release_manifest(repository_root)
    output_directory.mkdir(parents=True, exist_ok=True)
    archive_path = output_directory / ARCHIVE_NAME
    checksum_path = output_directory / CHECKSUM_NAME
    if not force and (archive_path.exists() or checksum_path.exists()):
        raise ReleaseBuildError(
            "Release output already exists. Choose an empty directory or pass "
            "--force to replace only these named release outputs."
        )

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{ARCHIVE_NAME}.",
            suffix=".tmp",
            dir=output_directory,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        _write_archive(temporary_path, repository_root, entries)
        validate_archive(temporary_path, entries)
        os.replace(temporary_path, archive_path)
        temporary_path = None
        digest = sha256_file(archive_path)
        checksum_path.write_text(
            f"{digest}  {ARCHIVE_NAME}\n",
            encoding="utf-8",
        )
        members = validate_archive(archive_path, entries)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
    return ReleaseBuildResult(archive_path, checksum_path, digest, members)


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an allowlisted local PMC source-release test archive.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for the versioned ZIP and SHA-256 file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace only an existing ZIP/checksum with the exact release names.",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    options = parse_arguments(arguments)
    try:
        result = build_release(options.output_dir, force=options.force)
    except ReleaseBuildError as error:
        print(f"Release build failed: {error}", file=sys.stderr)
        return 1
    print(f"Archive: {result.archive_path}")
    print(f"SHA-256: {result.sha256}")
    print(f"Checksum file: {result.checksum_path}")
    print(f"Validated members: {len(result.members)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
