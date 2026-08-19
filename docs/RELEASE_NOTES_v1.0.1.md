# Product Manager Central v1.0.1 Release Notes

**Controlled-beta candidate:** Prepared for technical evaluation and separate
release approval. This source state is not tagged, packaged, uploaded, or
published as v1.0.1.

## Proposed GitHub Release metadata

- **Tag:** `v1.0.1`
- **Title:** `Product Manager Central v1.0.1`
- **Source asset:** `product-manager-central-v1.0.1.zip`
- **Checksum asset:** `product-manager-central-v1.0.1.zip.sha256`

## What changed

- A single clearly named `scripts/start_pmc_macos.command` now handles first
  setup and later launches. It finds its application directory, creates `.venv`
  when missing, installs only pinned requirements when needed, checks port 8501,
  starts PMC, and opens the local Streamlit experience.
- Normal macOS and Windows startup no longer asks about an OpenAI API key.
  Product, BRD/PRD, search, accepted-history, and export workflows remain
  available with AI inactive.
- Optional AI connection guidance now appears inside the AI Assistant and uses
  a user-controlled temporary session environment variable. The page reports
  Active or Inactive without revealing the key, identifies unavailable AI
  features, distinguishes provider authorization from company-data permission,
  and gives enterprise approval and sensitive-data guidance. Keys are never
  stored or exposed by PMC.
- Dashboard, installation, README, and portfolio materials more directly
  explain the intended AI value: helping Product Managers create and review
  Agile artifacts grounded in intentionally selected Approved BRDs and PRDs.

## Responsible-AI controls

AI does not write or approve product decisions independently. Retrieved source
citations, source-freshness checks, claim-support assessment, human review, and
explicit acceptance are deliberate controls. Draft or ineligible sources remain
excluded, acceptance revalidates current evidence, and accepted output remains
separate from source BRDs and PRDs.

## Positioning and compatibility

v1.0.1 is a controlled-beta/portfolio release suitable for technical
evaluation. It is not a commercial production application.
It is not a signed or notarized native macOS application and is not evidence of customer adoption
or outcomes. Native validation remains limited to the macOS/Python environment
recorded by Checkpoint 15. Windows remains structural-only unless separate
native execution evidence is completed.

PMC remains single-user and local only, implemented as a Streamlit/SQLite
application under the MIT
License. It has no authentication, collaboration, hosted infrastructure,
telemetry, billing, or encrypted database. Users are responsible for protecting
local product information and for authorization before sending selected content
to an optional provider.

## Install

Use the approved PMC ZIP listed under the GitHub Release's **Assets** section,
not GitHub's automatic source-code archives. Follow the short
[Quick Start for macOS](INSTALLATION.md#quick-start-for-macos). Keep Terminal
open while PMC runs and press Control-C to stop it.

The release ZIP is source-only. It contains no database, backup, API key,
environment file, cache, virtual environment, generated export, test artifact,
or Git metadata. Verify the neighboring checksum asset before extraction when
performing a controlled evaluation.

## Publication boundary

Checkpoint 15 does not modify the v1.0.0 tag, GitHub Release, or uploaded assets.
These notes and a disposable local candidate do not authorize a commit, push,
tag, upload, beta invitation, GitHub Release, or publication. Every such action
requires separate approval after the complete Checkpoint 15 verification gates.
