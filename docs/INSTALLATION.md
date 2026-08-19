# Install and Run Product Manager Central

Product Manager Central (PMC) is a local portfolio application for technical
evaluation. v1.0.1 is positioned as a controlled-beta/portfolio release, not a
commercial production service or a signed or notarized native macOS app.

## Quick Start for macOS

1. Open the repository's GitHub **Releases** page and select the approved
   v1.0.1 release. Under **Assets**, download
   `product-manager-central-v1.0.1.zip`. The neighboring `.sha256` file is
   optional but recommended for checksum verification.
2. Do not use GitHub's automatically generated **Source code (zip)** or
   **Source code (tar.gz)** links. Those are not the approved, deterministic PMC
   ZIP described in these instructions.
3. Extract `product-manager-central-v1.0.1.zip`, open the extracted
   `product-manager-central-1.0.1` folder, and double-click
   `scripts/start_pmc_macos.command`.
4. Keep the Terminal window open while using PMC. The starter creates `.venv`
   and installs the pinned `requirements.txt` only when needed, then opens
   `http://localhost:8501`.
5. Press **Control-C** in that Terminal window to stop PMC safely.

The starter resolves the application folder from its own location, so it works
regardless of the current Terminal directory. From Terminal, the equivalent
command is:

```bash
/path/to/product-manager-central-1.0.1/scripts/start_pmc_macos.command
```

On the first verified launch, macOS may block the downloaded `.command` file.
Control-click `start_pmc_macos.command` in Finder, choose **Open**, then confirm
**Open**. If that choice is unavailable, try the file once, open **System
Settings → Privacy & Security**, and choose **Open Anyway** for that specific
verified file. Do not disable or bypass Gatekeeper.

## Validated environment and prerequisites

The clean-install workflow has native evidence only for macOS 26.5.2 on Apple
silicon (`arm64`) with Python 3.14.6. PMC and its pinned dependencies support
Python 3.11 through 3.14, but Python 3.11–3.13 and Windows have structural
automated coverage only and are not claimed as natively validated.

Install Python from [python.org](https://www.python.org/downloads/) if macOS does
not already provide a suitable `python3`. PMC pins Streamlit 1.61.1, pandas
3.0.5, OpenAI 2.53.0, python-docx 1.2.0, and ReportLab 5.0.0 in
`requirements.txt`. The starter installs only that file and does not install an
unbounded dependency set.

Word and PDF export is local and needs neither Microsoft Word nor an API key.
PMC remains single-user and local; application files, `.venv`, and SQLite data
stay in the extracted folder.

## Optional checksum verification

Place the approved ZIP and `.sha256` asset in the same directory before
extracting. Verification is recommended but is separate from the required
startup steps.

macOS:

```bash
shasum -a 256 product-manager-central-v1.0.1.zip
cat product-manager-central-v1.0.1.zip.sha256
```

Windows PowerShell:

```powershell
(Get-FileHash .\product-manager-central-v1.0.1.zip -Algorithm SHA256).Hash.ToLower()
Get-Content .\product-manager-central-v1.0.1.zip.sha256
```

The two hexadecimal SHA-256 values must match exactly. Stop if they do not.

## Optional AI setup

Normal startup never asks for an API key. Product management, BRD/PRD creation,
search, review history, and Word/PDF export remain available without one. AI
stays inactive until the user deliberately provides `OPENAI_API_KEY` to the
same process environment that starts PMC. The AI Assistant displays **Active**
or **Inactive** without revealing the key. When inactive, AI-assisted Agile
generation and General draft generation are unavailable.

AI-assisted generation requires a valid user-supplied API key. A key authorizes
the configured AI provider; it does not automatically provide access to company
information or permission to submit it. Enterprise users should request an
organization-approved key and data-use authorization from their IT, security,
AI-governance, or platform-administration team.

On macOS, stop PMC and use a Terminal session:

```bash
read -s OPENAI_API_KEY
export OPENAI_API_KEY
/path/to/product-manager-central-1.0.1/scripts/start_pmc_macos.command
unset OPENAI_API_KEY
```

The hidden `read` avoids showing the value on screen or placing it in the
command itself. The final `unset` runs after PMC stops. Never store or expose a
real key in source code, `.env` files, Git, SQLite, logs, documents, exports,
screenshots, or release packages. Do not send confidential, proprietary,
regulated, personal, export-controlled, or customer information to an external
provider without organizational approval.

The AI Assistant explains this optional connection in the product. When
enabled, grounded AI can help a Product Manager draft and review Agile artifacts
from intentionally selected Approved BRDs and PRDs. Citations,
source-freshness checks, claim-support assessment, human review, and explicit
acceptance remain required; AI does not approve product decisions.

## Troubleshooting macOS startup

### Gatekeeper blocks the starter

Verify the ZIP and source. Control-click only
`scripts/start_pmc_macos.command`, choose **Open**, and confirm. If necessary,
use **Privacy & Security → Open Anyway** for that specific file. Never disable
Gatekeeper globally.

### Python is missing or unsupported

Install Python 3.11 through 3.14 from python.org, then run the starter again.
The only natively validated interpreter is Python 3.14.6 on the macOS platform
listed above.

### Port 8501 is already in use

Stop the other local Streamlit or development process using port 8501, then run
the starter again. PMC intentionally uses `http://localhost:8501` and does not
silently switch ports.

### `.venv` is missing or installation failed

The starter creates a missing `.venv` automatically. If creation or pinned
dependency installation fails, check folder write access, the Python `venv`
module, and the internet connection. An incomplete environment can be repaired
by deleting only this extracted application's `.venv` and running the starter
again. Never delete `data/pmc.db` while repairing `.venv`.

## Windows structural instructions

Windows has not been natively validated. For technical inspection only, the
existing PowerShell helpers remain available:

```powershell
& "C:\path\to\product-manager-central-1.0.1\scripts\setup_windows.ps1"
& "C:\path\to\product-manager-central-1.0.1\scripts\run_windows.ps1"
```

They resolve the application directory from their own location and use the
local `.venv`. Normal startup does not ask for an API key. Do not weaken the
machine-wide PowerShell execution policy.

## Application files and local data

- Application code, launchers, and documentation are in the extracted folder.
- Python dependencies are isolated in `.venv` inside that folder.
- Products, BRDs, PRDs, and accepted artifacts are stored in `data/pmc.db`.

The approved release ZIP contains no database. First startup creates a clean
local database. Fictional sample data is loaded only when the user explicitly
chooses **Load fictional sample data** on the Dashboard.

## Back up and restore data

Always stop PMC before copying or replacing its database.

To back up, copy `data/pmc.db` to a private location outside the application
directory. Do not place a database or backup in Git or a release archive.

To restore:

1. Stop PMC.
2. Back up the current database if it contains anything you may need.
3. Confirm the intended backup belongs to PMC.
4. Copy it to `data/pmc.db` in the intended installation.
5. Start PMC and verify the data before deleting any backup.

## Update to a future approved release

1. Stop PMC and back up `data/pmc.db` outside the application directory.
2. Download and verify the future approved release into a new directory; do not
   extract it over the existing installation.
3. Follow that release's migration instructions before copying any database.
4. Verify the new installation before removing the old directory.

## Remove PMC

1. Stop PMC.
2. Back up `data/pmc.db` if it may be needed later.
3. Confirm the exact extracted PMC directory.
4. Delete that directory using Finder or File Explorer.

PMC provides no automated uninstall or database deletion command.

## Verify the release checksum

Use the optional checksum-verification steps above. The two hexadecimal
SHA-256 values must match exactly.

## Source-controlled builder versus an approved release

`scripts/build_release.py` creates a deterministic local candidate from the
explicit `release_manifest.txt` allowlist. The builder excludes databases,
backups, environment files, Git metadata, caches, tests, prior archives, and
unrelated files. A local build is not an approved GitHub Release and does not
authorize a tag, upload, publication, or beta invitation.

For acceptance scenarios, controlled-beta guidance, known limitations, and
responsible-use boundaries, see [`UAT_BETA_GUIDE.md`](UAT_BETA_GUIDE.md).
