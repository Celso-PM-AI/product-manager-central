# Contributing to Product Manager Central

Product Manager Central is a local portfolio application. Contributions should
remain small, reviewable, and consistent with its single-user Streamlit and
SQLite architecture.

## Local development

1. Create and activate a virtual environment.
2. Install the direct runtime dependencies from `requirements.txt`.
3. Run the complete test suite:

   ```bash
   PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
   ```

Automated and manual destructive tests must use a temporary database selected
with `PMC_DATABASE_FILE`. Never test against `data/pmc.db`.

## Contribution expectations

- Explain the user problem and keep changes within the approved checkpoint.
- Add deterministic tests for behavior changes and keep existing tests passing.
- Preserve Approved BRD/PRD-only retrieval, complete citations, human review,
  explicit acceptance, and separation from original source documents.
- Never commit API keys, environment files, databases, SQLite sidecars,
  backups, archives, caches, virtual environments, temporary files, personal
  data, proprietary data, or the protected local screenshot.
- Do not make live OpenAI calls in automated tests.
- Run the complete suite, Python compilation, `git diff --check`, a secret scan,
  and an isolated application smoke test before requesting review.

## Version and release conventions

PMC uses Semantic Versioning. Source metadata uses `MAJOR.MINOR.PATCH`; Git tags
use the corresponding `vMAJOR.MINOR.PATCH` form. The planned first public
portfolio release is v1.0.0, but it is not released until Phase 10 verification
passes and publication is explicitly approved.

- `MAJOR` denotes an incompatible application or stored-data contract change.
- `MINOR` denotes backward-compatible user-facing capability.
- `PATCH` denotes backward-compatible fixes and documentation corrections.

Every release must update `src/version.py`, `CHANGELOG.md`, release notes, and
all user-visible version references together. Release archives are built only
from an approved allowlist, start without a production database, and receive a
SHA-256 checksum. Tags, GitHub Releases, and publication require separate
approval.
