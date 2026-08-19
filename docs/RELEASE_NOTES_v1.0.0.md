# Product Manager Central v1.0.0 Release Notes

**Release-candidate draft:** Prepared for final human approval. PMC v1.0.0 has
not been tagged, published, or made available through a GitHub Release.

## Proposed GitHub Release metadata

- **Tag:** `v1.0.0`
- **Title:** `Product Manager Central v1.0.0`
- **Source asset:** `product-manager-central-v1.0.0.zip`
- **Checksum asset:** `product-manager-central-v1.0.0.zip.sha256`

The checksum value is generated from the exact approved candidate and must be
verified before any separately authorized publication. These notes do not
authorize creating the tag or GitHub Release.

## Highlights

- Local Product workspace with Dashboard, Product creation, BRD and PRD
  builders, AI Assistant, Product viewing, and Product search.
- Stable-ID Product create, view, search, edit, and confirmed-delete workflows.
- Draft-tolerant and Approved-strict BRD/PRD authoring with professional ordered
  outlines, structured BRD rows, and explicit PRD Epic -> Capability -> Feature
  -> User Story hierarchy.
- Independent measurable acceptance criteria at every Agile level and an
  ordered PRD Success Matrix with stable identifiers.
- Approved-document-only retrieval, visible citations, source-freshness checks,
  deterministic claim-support assessment, and fail-closed hierarchy, gap, and
  proposal gates.
- Human review, revision, rejection, and explicit acceptance with accepted
  artifacts stored separately from immutable source-document snapshots.
- Local in-memory Word and PDF export for saved Draft and Approved BRDs and
  PRDs, including structured hierarchy and Success Matrix content.
- Optional, explicit fictional Trailwise sample data. Clean startup never loads
  sample records automatically.

## Install and run

Verify the candidate ZIP against its neighboring SHA-256 file before extracting
it. On macOS, run `scripts/setup_macos.command` followed by
`scripts/run_macos.command`. Windows users can run the corresponding PowerShell
helpers. Product and document workflows require no API key; AI generation is
optional and inactive until the user supplies a key through the documented
session environment.

The release candidate contains source files only. It contains no database,
sample database, API key, environment file, backup, cache, virtual environment,
test artifact, generated export, or Git metadata.

## Verified compatibility

| Platform | Python | Pinned dependency install | Complete suite | No-key startup | Evidence |
| --- | --- | --- | --- | --- | --- |
| macOS 26.5.2 arm64 | 3.14.6 | Passed | Passed | Passed | Native Checkpoint 14 verification |
| macOS | 3.11-3.13 | Not run natively | Structural only | Structural only | Not claimed as native support |
| Windows | 3.11-3.14 | Not run natively | Structural only | Structural only | PowerShell structure only |

The sole native claim is the exact macOS/Python combination above. The pinned
runtime dependencies are Streamlit 1.61.1 (Apache-2.0), pandas 3.0.5
(BSD-3-Clause), OpenAI 2.53.0 (Apache-2.0), python-docx 1.2.0 (MIT), and
ReportLab 5.0.0 (BSD). PMC itself is licensed under the MIT License.

## Responsible-use and data boundaries

- Use only content you are authorized to store locally or send to an optional
  provider.
- Approved status controls retrieval eligibility; it does not prove accuracy,
  authorization, or recency.
- Review every generated claim and citation. Generated output can be incorrect,
  incomplete, stale, biased, or unsupported.
- Acceptance is explicit, revalidates current sources, and never modifies an
  original BRD or PRD.
- Keep `data/pmc.db` private, stop PMC before backup or restore, and never place
  databases or API keys in Git or a release archive.

## Known limitations

- Single-user and local only; no authentication, authorization roles,
  collaboration, cloud hosting, hosted backup, telemetry, or billing.
- Source launchers are not signed or notarized native installers.
- Native validation is limited to macOS 26.5.2 arm64 with Python 3.14.6.
- The optional AI workflow requires a user-supplied OpenAI API key and may incur
  separate API charges. No live-provider quality claim is made by offline UAT.
- Semantic retrieval can omit relevant evidence or rank it imperfectly, and
  citations do not prove a conclusion.
- Accepted generated artifacts are read-only and cannot be edited, deleted,
  regenerated, exported, or promoted automatically into source documents.
- Native Google Docs export, analytics integrations, external beta evidence,
  production-use evidence, and customer-outcome claims remain unavailable.

## Publication boundary

Checkpoint 14 prepares and verifies a local candidate plus these proposed
GitHub Release materials. A tag, GitHub Release, upload, announcement, package
publication, or other distribution requires a separate explicit approval.
