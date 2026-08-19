# Install and Run Product Manager Central

Product Manager Central (PMC) is a local Streamlit application. Application
files, the `.venv` Python environment, and the SQLite data file all remain on
your computer. PMC is not a hosted service.

For acceptance scenarios, beta preparation, expanded troubleshooting, known
limitations, and AI responsible-use guidance, see
[`UAT_BETA_GUIDE.md`](UAT_BETA_GUIDE.md). The external beta described there is
planned only and has not been conducted.

## Validated environment and prerequisites

The clean-install release workflow was natively validated on:

- macOS 26.5.2, Apple silicon (`arm64`)
- Python 3.14.6
- Streamlit 1.61.1, pandas 3.0.5, OpenAI 2.53.0, python-docx 1.2.0,
  and ReportLab 5.0.0

PMC's source and pinned direct dependencies require Python 3.11 through 3.14.
Python 3.11 is the dependency-imposed floor, but Python 3.11–3.13 and Windows
have automated structural coverage only and are not claimed as natively
validated. Native Windows and additional Python-version validation remain
future work.

python-docx is MIT-licensed and ReportLab is BSD-licensed. They are the only
new direct runtime dependencies for local Word and PDF export. PMC generates
both formats directly and does not require Microsoft Word, LibreOffice, a
hosted conversion service, an API key, or a network connection to export a
saved document.

Export does not require an API key. Checkpoint 13 reverified local no-key
startup, all seven application destinations, the macOS launcher, Windows
launcher structure, Draft/Approved Word and PDF export, and isolated package
startup with temporary databases. Checkpoint 14 repeated the clean candidate
installation, macOS launcher, no-key startup, complete regression,
deterministic archive, and checksum gates on that native macOS/Python
combination. This does not broaden the native-platform claim. Checkpoint 14 is
complete, and there is still no published PMC package, tag, or GitHub Release.

Install Python from [python.org](https://www.python.org/downloads/) before
starting. The setup helpers stop with an actionable error if Python is missing,
outside the prerequisite range, unable to create a virtual environment, or
unable to install the declared dependencies.

## macOS: first installation

1. Download the approved PMC source ZIP and its `.sha256` file together.
2. Verify the checksum as described below, then extract the ZIP.
3. In Finder, open the extracted `product-manager-central-1.0.0` folder and
   double-click `scripts/setup_macos.command`. The helper finds the application
   directory even when Terminal started elsewhere, creates or reuses `.venv`,
   and installs only `requirements.txt`.
4. Double-click `scripts/run_macos.command` to start PMC. Your browser should
   open the local Streamlit application.

If macOS says a downloaded script cannot be opened, first verify the archive
checksum. Then Control-click the specific `.command` file in Finder, choose
**Open**, and confirm that file. Do not disable Gatekeeper or other macOS
security protections.

From Terminal, the equivalent commands work from any current directory:

```bash
/path/to/product-manager-central-1.0.0/scripts/setup_macos.command
/path/to/product-manager-central-1.0.0/scripts/run_macos.command
```

## Windows: first installation

1. Download the approved PMC source ZIP and its `.sha256` file together.
2. Verify the checksum as described below, then extract the ZIP.
3. Open PowerShell and run the setup helper by its path:

   ```powershell
   & "C:\path\to\product-manager-central-1.0.0\scripts\setup_windows.ps1"
   ```

4. Start PMC:

   ```powershell
   & "C:\path\to\product-manager-central-1.0.0\scripts\run_windows.ps1"
   ```

The helpers resolve the application directory from their own location, create
or reuse `.venv`, install only `requirements.txt`, and launch `app.py` with the
virtual environment's Python.

If Windows blocks a downloaded script, verify the archive checksum and source
first. In File Explorer, open the specific file's **Properties** and use
**Unblock** when available, or run `Unblock-File` for only the two verified PMC
scripts. Do not weaken the machine-wide PowerShell execution policy.

## Optional OpenAI API key

Product and document workflows work without an API key. When no key is already
present, each run helper can ask whether to configure one for that run:

- macOS uses a hidden Terminal prompt.
- Windows uses PowerShell `Read-Host -AsSecureString`.

The helpers do not echo the key, put it in command arguments, or write it to a
file. A key entered this way exists only in the launcher process and the PMC
process it starts. Stopping PMC and closing that terminal session removes the
temporary key. If you decline, PMC starts normally with AI generation inactive.

Never put a real key in source code, `.env` files, screenshots, logs, databases,
release archives, or Git. Treat local product documents as sensitive and send
content to an API only when authorized.

## Start and stop PMC

After setup, use the platform's `run_...` helper from Finder, File Explorer, or
any terminal directory. The launcher prints a local URL. Keep its terminal open
while using PMC. Press **Control-C** in that terminal to stop Streamlit safely,
then close the terminal window.

## Application files and local data

- Application code, launchers, and documentation are in the extracted PMC
  directory.
- Python dependencies are isolated in `.venv` inside that directory.
- User products, BRDs, PRDs, and accepted artifacts are stored in
  `data/pmc.db` inside that directory.

The release ZIP contains no database. On first startup, PMC creates a new clean
`data/pmc.db` through its existing initialization behavior. Fictional sample
data is never automatic. To explore it, choose **Load fictional sample data** on
the Dashboard. Otherwise, create your own first product and the database stays
free of sample records.

## Back up and restore data

Always stop PMC before copying or replacing its database.

To back up, copy `data/pmc.db` from the current PMC directory to a private backup
location outside the application directory. Give the copy a date and keep it
secure. Do not place backups in Git or a release archive.

To restore:

1. Stop PMC.
2. Back up the current `data/pmc.db` first if it contains anything you may need.
3. Confirm that the backup belongs to PMC and is the file you intend to restore.
4. Copy the chosen backup to `data/pmc.db` in the intended PMC directory.
5. Start PMC and verify products and documents before deleting any backup.

Restoration intentionally remains a manual, explicit operation. No launcher
deletes or replaces a database.

## Update to a future approved release

1. Stop the current PMC process.
2. Back up its `data/pmc.db` outside the application directory.
3. Download and verify the future approved release into a new directory; do not
   extract it over the existing installation.
4. Run the new release's setup helper.
5. Follow that release's migration notes. If it explicitly supports the existing
   database, copy the backup into the new release only while PMC is stopped.
6. Start the new release and verify the data before removing the old directory.

## Remove PMC

1. Stop PMC.
2. Back up `data/pmc.db` if you may need its contents later.
3. Confirm the exact extracted PMC directory you intend to remove.
4. Delete that application directory using Finder or File Explorer.
5. Delete the separate backup only when you explicitly decide it is no longer
   needed.

PMC provides no automated uninstall or database deletion command.

## Verify the release checksum

Place the ZIP and `.sha256` file in the same directory.

macOS:

```bash
shasum -a 256 product-manager-central-v1.0.0.zip
cat product-manager-central-v1.0.0.zip.sha256
```

Windows PowerShell:

```powershell
(Get-FileHash .\product-manager-central-v1.0.0.zip -Algorithm SHA256).Hash.ToLower()
Get-Content .\product-manager-central-v1.0.0.zip.sha256
```

The two hexadecimal SHA-256 values must match exactly. Stop if they do not.

## Source-controlled builder versus an official release

`scripts/build_release.py` can create a local test ZIP from the explicit
`release_manifest.txt` allowlist. That capability does not make the output an
official release. Checkpoint 14 produced and verified a disposable local
candidate and prepared [draft v1.0.0 release notes](RELEASE_NOTES_v1.0.0.md).
A Git tag, GitHub Release, published checksum, upload, or announcement still
requires later, separate authorization.
