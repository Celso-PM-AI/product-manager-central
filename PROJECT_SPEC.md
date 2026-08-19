# Product Manager Central

## Product purpose and MVP scope

Product Manager Central (PMC) is a local Streamlit workspace for product
managers to capture, find, review, update, and safely delete structured product
information and to author template-guided product documents. SQLite remains the
single local data source. Phase 9 adds an optional OpenAI
configuration/client boundary, embedding-based semantic retrieval of Approved
BRD/PRD chunks, grounded draft generation with citations, and explicit human
review with separate accepted-artifact persistence. Its final checkpoint adds
deterministic, developer-facing evaluation and release scoring.

The MVP provides:

1. Canonical product creation with centralized validation.
2. Compact product listing and complete ID-based detail views.
3. Case-insensitive search across every approved text field.
4. Prepopulated editing with cancellation and safe error handling.
5. Two-step, ID-based permanent deletion.
6. Four portfolio dashboard metrics.
7. Persistent local SQLite storage in one Streamlit application.
8. Product-associated BRD and PRD creation, preview, and stable-ID editing.

Duplicate product names are allowed. Identity-sensitive operations always use
the system-managed product ID.

## Product fields and validation

| Field | Category | Rule |
| --- | --- | --- |
| `name` | Required | Trimmed; 1–120 characters |
| `description` | Required | Trimmed; 1–2,000 characters |
| `target_users` | Required | Trimmed; 1–1,000 characters |
| `business_goal` | Required | Trimmed; 1–2,000 characters |
| `status` | Required | One approved status; defaults to `discovery` in create |
| `customer_problem` | Optional | Blank becomes `NULL`; maximum 2,000 characters |
| `product_strategy` | Optional | Blank becomes `NULL`; maximum 3,000 characters |
| `notes` | Optional | Blank becomes `NULL`; maximum 5,000 characters |
| `id` | System-managed | SQLite integer primary key |
| `created_at` | System-managed | Set on creation and preserved during edits |
| `updated_at` | System-managed | Set on creation and advanced during edits |

Outer whitespace is removed while internal spaces, paragraphs, Unicode, and
line breaks are preserved. Whitespace-only required fields are invalid.
Validation reports all discovered errors together, rejects unknown fields, and
does not allow forms to supply system-managed fields.

Approved statuses are:

- `idea`
- `discovery`
- `planning`
- `in_development`
- `launched`
- `archived`

## Implemented workflows

### Create

- Displays every editable field and clearly identifies required fields.
- Defaults status to `discovery`.
- Uses centralized validation and creates exactly one row after a valid submit.
- Displays all validation errors without creating invalid data.

### List and detail

- Lists products in descending ID order with name, readable status, compact
  target-user context, and updated time.
- Selects and opens records by ID, so duplicate names remain unambiguous.
- Displays every field plus created and updated timestamps.
- Shows friendly values for unpopulated optional fields.

### Search

- Searches name, description, target users, business goal, customer problem,
  product strategy, and notes.
- Is case-insensitive and treats `%`, `_`, backslashes, and apostrophes safely.
- Returns the normal product list when the query is blank.

### Edit

- Opens a prepopulated form from product detail.
- Reuses create-field rendering, validation, and normalization.
- Cancel leaves the database unchanged.
- Invalid edits leave the complete stored record unchanged.
- Successful edits preserve `id` and `created_at`, advance `updated_at`, and
  return to refreshed detail.

### Confirmed delete

- The first Delete action only opens a warning naming the product and ID.
- Separate `Delete permanently` and Cancel actions provide confirmation.
- Cancel leaves the record unchanged.
- Confirmation deletes exactly one ID and returns to the product list.
- Missing, already-deleted, and database-error cases use user-safe messages.
- The confirmation reports how many associated documents will also be
  permanently deleted through the database cascade.

### Product document builder

- Primary navigation provides separate Create PRD and Create BRD options.
- Each primary path requires an explicit ID-safe product selection before the
  appropriate template form appears; the first product is never auto-selected.
- When no products exist, the page explains that a product must be created
  first and provides a route to Create Product without rendering a document
  form.
- An existing product detail retains Create Document as a secondary pathway,
  where the user chooses BRD or PRD.
- Both pathways use the same template-specific guided form and saved-document
  preview/edit behavior.
- Title, version `1.0`, and Draft status receive deterministic defaults.
- High-confidence product context is copied once into the approved template
  sections; later product edits do not rewrite saved documents.
- Draft documents require valid metadata but may retain empty body sections.
- Approved documents require content in every section and identify each
  incomplete section in validation messages.
- Each document has a stable SQLite ID and remains associated with one product.
- A product may have multiple BRDs and PRDs.
- Saved documents have formatted previews and ID-based editing.
- Document deletion controls are not included. Checkpoint 12 adds read-only
  Word and PDF downloads for saved documents.

Document title is limited to 200 characters, version to 50 characters, and
each long-form section to 10,000 characters. Version is nonblank free text.
Document types are `BRD` and `PRD`; statuses are `draft` and `approved` in
storage and appear as Draft and Approved in the interface.

### Phase 9 AI Assistant

- AI configuration is optional and reads only `OPENAI_API_KEY` from the process
  environment. Status reporting never returns or logs the key.
- `OPENAI_MODEL` may override the documented default model without a code
  change.
- `OPENAI_EMBEDDING_MODEL` may override the documented embedding model without
  a code change.
- The OpenAI service uses the official Python SDK's Responses and Embeddings
  APIs through an injectable client boundary. Automated tests use mocks and
  make no API calls.
- Deterministic retrieval returns sections only from documents whose status is
  `approved` and whose type is `BRD` or `PRD`. Drafts and unsupported types are
  excluded.
- Every retrieved section includes product ID/name, document ID/title/type,
  approval status, section key/title, and unchanged section content.
- Approved sections are divided deterministically at meaningful paragraph and
  word boundaries. Every chunk retains a stable ID, chunk index, unchanged
  source text, and the complete section citation metadata.
- An injectable embedding provider creates ordered vectors. Cosine similarity
  ranks chunks in descending order, with configurable result limits and minimum
  similarity. Automated tests use deterministic fake or mocked embeddings.
- Eligibility is checked again after embeddings are created. Deleted, missing,
  edited, Draft, unsupported, and no-longer-approved sources cannot be returned
  as trusted results.
- Retrieval reports distinct empty states when no Approved BRD/PRD sources are
  available or when none meet the relevance threshold.
- A clean generation service validates a Product Manager's request, retrieves
  relevant Approved sources, constructs a source-numbered prompt, and sends it
  through the existing injectable OpenAI Responses API boundary.
- Generated output is clearly labeled as AI-generated and is returned
  separately from structured citations containing product name/ID, document
  title/ID/type, and section title/key.
- No approved retrieval context means no generation call and no claim that a
  response is grounded.
- Original BRDs and PRDs are never modified by AI. Generated content remains
  pending and unsaved until a Product Manager explicitly accepts it.
- Review displays the original AI output and supporting citations. The reviewer
  may accept unchanged, apply a human revision that remains pending until a
  separate acceptance, or reject without saving an approved artifact.
- Explicit acceptance stores a separate generated artifact associated with its
  product. It preserves the request, original AI output, accepted content,
  revision status, source document relationships, and citation snapshots.
- Acceptance revalidates cited documents as current Approved BRDs or PRDs and
  uses an idempotency key to prevent duplicate saves during reruns.
- Generated artifacts never update, overwrite, append to, or otherwise modify
  an original BRD, PRD, or document section.
- Approved prompts are immutable source-controlled definitions with stable IDs,
  public names/descriptions, supported tasks, semantic versions, hidden system
  instructions, deterministic user templates, and required input fields.
- The existing grounded-draft behavior is the only supported assistant task and
  uses only its mapped approved built-in prompt.
- Product, task, prompt, and required request input are validated before
  retrieval or generation. Approved evidence is required before prompt
  rendering and text generation.
- The interface displays prompt name, description, and version but never hidden
  instructions, credentials, or provider exception details.
- Streamlit reruns reuse the completed submission state rather than repeating
  generation, while accepted-content persistence remains idempotent.
- Offline Phase 9 evaluation uses deterministic cases, fake providers, and
  temporary databases. It never requires a live API call or real API key.
- Evaluation scores retrieval precision, retrieval recall, source trust,
  citation completeness, citation/source correspondence, grounded generation,
  human control, and source separation. Criteria are averaged without weights
  and reported from 0 through 100.
- Release requires an overall score of at least 80 plus perfect source-trust,
  citation-completeness, human-control, and source-separation scores.
- Evaluation has no Streamlit dashboard, LLM-as-a-judge, persistent results,
  database migration, or schema change.

## Dashboard metrics

- **Total products:** every saved product.
- **Active products:** every product whose status is not `archived`.
- **Launched products:** every product whose status is `launched`.
- **Updated in last 30 days:** every product whose `updated_at` is exactly at
  or later than the inclusive 30-day cutoff.

Charts and advanced analytics are not part of the MVP.

## Technology and file responsibilities

- Python is the implementation language.
- Streamlit provides the single application in `app.py`.
- SQLite is the only active data source.
- `src/models.py` owns the `Product` model, status enum, and field categories.
- `src/document_templates.py` owns persistent document section keys, labels,
  guidance, order, and one-time product prepopulation.
- `src/document_export.py` owns the shared ordered export model, safe filenames,
  and local in-memory Word and PDF renderers.
- `src/validation.py` owns normalization and reusable validation.
- `src/database.py` owns schema detection, canonical initialization,
  parameterized product/document persistence, approved-source retrieval,
  metrics, the controlled known-legacy migration, and the additive Phase 8
  migration.
- `src/ai_service.py` owns non-secret OpenAI configuration status and the
  injectable Responses and Embeddings API service boundary.
- `src/semantic_retrieval.py` owns stable chunking, similarity ranking, result
  limits, live eligibility revalidation, and semantic-retrieval empty states.
- `src/grounded_generation.py` owns request validation, grounded prompt
  construction, temporary generated-draft results, and structured citations.
- `src/generated_content.py` owns pending review, revision, rejection, and
  explicit acceptance orchestration.
- `src/prompt_catalog.py` owns approved task/prompt definitions, mappings,
  validation, lookup, and deterministic rendering.
- `src/rag_evaluation.py` owns offline criterion scoring, suite aggregation,
  and the Phase 9 release decision.
- `tests/` contains temporary-database model, validation, persistence,
  presentation-helper, and Streamlit workflow tests.
- `requirements.txt` contains the pinned Streamlit, pandas, official OpenAI
  Python SDK, python-docx, and ReportLab runtime dependencies.

The application accepts `PMC_DATABASE_FILE` for isolated automated or manual
verification. Without it, the only live data source is `data/pmc.db`.

Documents use normalized `documents` and `document_sections` tables. Accepted
generated content uses separate `generated_artifacts` and
`generated_artifact_citations` tables. Foreign
keys are enforced, product deletion cascades to associated documents, and an
index supports product document listings. The application deliberately has no
ORM, general service/view framework, general schema framework, multipage
architecture, charts, or advanced styling framework. Phase 9 keeps API access
and semantic retrieval behind narrow, testable boundaries.

Keyword search and semantic retrieval serve different needs. Product keyword
search performs literal, case-insensitive substring matching over product
fields. Semantic retrieval embeds a natural-language query and approved source
chunks, then ranks conceptual similarity even when the wording differs.

## Data-protection policy

- The preserved Product Manager Central record in `data/pmc.db` must not be
  edited or deleted during testing.
- Automated tests use new temporary databases and never use the live database.
- Manual destructive testing uses disposable products in a disposable database
  selected with `PMC_DATABASE_FILE`.
- Permanent backups under `backups/` and the unused preserved legacy CSV at
  `archive/products.csv` remain local and unchanged.
- Databases and sidecars, backups, the CSV, virtual environments, Python/test/
  tool caches, operating-system files, `pasted-text.txt`, and secret-bearing
  `.env` files are excluded from Git.

## Deferred beyond the revised Phase 10 scope

- Evaluation dashboards, LLM-as-a-judge, live benchmark services, and
  persisted evaluation history
- User-authored/editable prompts, database prompt storage, prompt history,
  product-specific prompts, sharing, import/export, experiments, and optimization
- AI-generated document updates and automatic modification of source BRDs/PRDs
- Native Google Docs export
- Authentication, multi-user permissions, and cloud deployment
- Analytics integrations, charts, and advanced styling frameworks
- ORM, service-layer, separate view-layer, or general migration frameworks
- Automated CSV importing

## Current development status

Phases 0 through 8 and all six Phase 9 checkpoints are complete. Secure
OpenAI boundaries, stable approved-source retrieval, and temporary grounded
draft generation with citations, explicit human review, and separate accepted
artifact persistence, the code-controlled prompt catalog, and hardened assistant
workflow are implemented. Deterministic offline scoring and end-to-end release
evaluation validate the complete Phase 9 workflow without live API calls or
production-database access.

## Phase 10 portfolio release policy

Phase 10 prepares a local, source-based Product Manager Central portfolio
release and, before release, adds governed Agile-artifact generation and BRD/PRD
export. v1.0.0 was published under the MIT License on August 19, 2026 after its
verified candidate passed the approved gates. Checkpoint 15 prepares v1.0.1 as
an untagged, unpublished controlled-beta/portfolio candidate. The product name
and current working visual identity remain unchanged.

The approved distribution target is a GitHub Release ZIP with Mac and Windows
setup and launch helpers. Native installers, cloud deployment, authentication,
multi-user infrastructure, hosted databases, billing, telemetry, and enterprise
operations are outside Phase 10.

Environment support is evidence-based. An operating-system and Python-version
combination is supported only after a clean virtual environment installs all
direct runtime dependencies and passes the complete test suite and isolated
application smoke test without an API key. Native clean-install evidence covers
macOS 26.5.2 arm64 with Python 3.14.6. Windows and Python 3.11–3.13 retain
structural coverage only and are not claimed as natively validated. The
existing environment's test result alone is not a broader support claim.

`requirements.txt` continues to list direct runtime dependencies. Direct
versions will be pinned only after compatibility evidence exists. Phase 10 does
not require a general dependency-management framework or a platform-specific
transitive lock unless validation demonstrates a release-blocking need.

The release must omit all production databases, prebuilt sample databases,
backups, archives, SQLite sidecars, secrets, environment files, caches, virtual
environments, personal data, and proprietary data. Clean startup is the default;
fictional sample data will be optional and user-triggered in a later checkpoint.
The repository-local `data/pmc.db` approach remains approved for v1.0.

Checkpoint 1 is complete. It establishes license, planned version metadata,
governance, release/version conventions, environment and dependency policies,
and deterministic metadata tests.

### Checkpoint 2 first-time experience

Checkpoint 2 adds Getting Started guidance to the default Dashboard. It explains
PMC's local operation and the safe sequence from product creation through BRD or
PRD drafting, human document approval, Approved-only retrieval, citation review,
and explicit acceptance, revision, or rejection of generated content. It also
explains that source documents are never changed by accepting generated content
and that users provide their own OpenAI API key only through a secure local
environment setting.

The optional fictional workspace is `[Fictional Sample] Trailwise`. It is loaded
only after the user chooses **Load fictional sample data**. It contains one
Approved fictional PRD for trusted-source and citation exploration and one Draft
fictional BRD that remains excluded from retrieval. A source-controlled marker
makes repeat activation idempotent and supports retrying an interrupted initial
load. PMC does not match or replace user data by name, load samples
automatically, or distribute a sample database. The user can identify the
`[Fictional Sample]` product in View Products and remove it through the existing
manual product-deletion workflow.

Normal product detail includes a read-only accepted-artifact history. Accepted
content remains in the separate generated-artifact store and is not mixed with
or written into BRDs and PRDs. The history shows the request, accepted content,
whether a human revision occurred, the retained original output when relevant,
dates, product association, and citations with product, document title and ID,
document type, and section. It offers no artifact edit, delete, regeneration,
or source-update action.

Checkpoint 2 is complete. Verification passed 11 focused tests and the complete
225-test suite without production-database access or live OpenAI calls. It adds
no schema, dependency, packaged data, or live-AI-test requirement. Checkpoints
3 through 6 were not started by Checkpoint 2.

### Checkpoint 3 installation and source packaging

Checkpoint 3 provides location-relative Mac and Windows setup and run helpers.
Setup creates or reuses `.venv`, validates Python prerequisites, installs only
the three pinned direct dependencies, and fails visibly on missing Python,
unsupported Python, virtual-environment failure, or dependency failure. Run
helpers validate the virtual environment and launch `app.py`. Optional OpenAI
keys are entered through masked prompts, inherited only by the launcher and PMC
process, never echoed or persisted, and unnecessary for non-AI workflows.

The validated native environment is macOS 26.5.2 arm64 with Python 3.14.6,
Streamlit 1.61.1, pandas 3.0.5, and OpenAI 2.53.0. Python 3.11 is the practical
dependency floor. Python 3.11–3.13 and Windows have automated structural
coverage only and are not claimed as natively validated.

The source-release builder reads the explicit `release_manifest.txt` allowlist
and rejects unsafe, missing, duplicate, or forbidden entries. Archive membership
must exactly equal that manifest. It includes the runtime, launchers, license,
governance, installation guidance, and existing portfolio image; it excludes
tests, production and sample databases, sidecars, backups, CSV archives,
environment files, secrets, Git metadata, caches, virtual environments, build
output, the protected screenshot, and unrelated files.

The planned filename is `product-manager-central-v1.0.0.zip`, with a neighboring
`.sha256` file. Fixed member order, timestamps, compression, and permissions make
identical source inputs byte-for-byte reproducible. The builder refuses an
existing named output unless `--force` is explicitly supplied. Archives built
during tests remain isolated temporary artifacts.

The package starts without a database; existing initialization creates a clean
local `data/pmc.db` at first run. Fictional sample loading remains an explicit
Dashboard action. `docs/INSTALLATION.md` documents installation, security
prompts, API-key handling, startup, shutdown, backup, restore, update, uninstall,
data location, optional samples, and checksum verification.

Checkpoint 3 is complete. Verification passed 241 tests in both the development
and fresh pinned environments, native Mac setup and launch, deterministic
archive and checksum validation, and extracted no-key clean-database startup.
It does not create an official release candidate, tag, GitHub Release,
installer, or publication. At Checkpoint 3 completion, Checkpoints 4 through 6
were not started.

### Checkpoint 4 UAT and beta preparation

Checkpoint 4 consolidates internal user acceptance testing, a planned
four-to-six-Product-Manager beta, troubleshooting, known limitations, and
responsible-use guidance in `docs/UAT_BETA_GUIDE.md`. Every UAT scenario records
an ID, preconditions, steps, expected result, pass/fail criteria, evidence, and
status. Internal validation uses temporary databases, deterministic fake or
mocked providers, and no real API key or live OpenAI call.

The guide distinguishes automated checks and internal UAT from external beta
work. It does not claim that participants were contacted or that the beta was
conducted. Native validation remains limited to macOS 26.5.2 arm64 with Python
3.14.6; Windows and Python 3.11–3.13 remain structurally tested but not natively
validated.

Checkpoint 4 does not change application code, the database schema,
dependencies, launchers, or packaging logic. It preserves Approved-only
retrieval, visible citations, human review, explicit acceptance,
acceptance-time source revalidation, generated/source-content separation,
clean startup, and explicit fictional sample loading. Recruiter materials and
sanitized screenshots remain Checkpoint 5 work; release-candidate and GitHub
Release preparation remain Checkpoint 6 work.

Checkpoint 4 is complete. Seventeen documented UAT scenarios passed at their
approved internal or structural evidence level, supported by 126 focused tests
and the complete 246-test suite. Python and shell syntax, deterministic archive
and checksum validation, extracted no-key clean startup, secret and prohibited-
artifact review, and protected-file comparisons passed. The external beta was
not conducted, no native Windows or additional Python-version claim was made,
and Checkpoint 5 had not started at Checkpoint 4 completion.

### Checkpoint 5 recruiter portfolio materials

Checkpoint 5 adds a concise recruiter-facing case study, compact Mermaid
architecture diagrams, a 3-minute-20-second demo storyboard and privacy
checklist, and clearly labeled draft LinkedIn, résumé, interview, and portfolio
copy. The demo video has not been recorded, and no material has been posted,
published, sent, or uploaded.

Three 1600×1200 portfolio screenshots show the Dashboard and product overview,
the product-document workflow with an Approved fictional PRD and Draft
fictional BRD, and a pending AI-generated-content review with traceable
citations and an explicit acceptance control. They contain only deterministic
fictional Trailwise data created in an isolated temporary database. The review
image uses a deterministic temporary harness without an API key or live OpenAI
call. The old Phase 8 browser screenshot is removed.

Portfolio claims remain evidence-qualified. PMC has not completed an external
beta, native Windows validation, or native Python 3.11–3.13 validation and does
not claim real users, adoption, revenue, customer outcomes, production usage,
measured performance improvement, a recorded demo, or a published release.
Native validation remains limited to macOS 26.5.2 arm64 with Python 3.14.6.

Checkpoint 5 changes documentation, images, the release allowlist, and metadata
tests only. Approved-only retrieval, visible citations, human review, explicit
acceptance, acceptance-time source revalidation, generated/source separation,
clean startup, and explicit sample loading remain unchanged.

Checkpoint 5 is complete after 6 focused portfolio tests, all 20 release-
metadata tests, and the complete 252-test suite passed with compilation, script
checks, deterministic 38-member archive verification, extracted no-key startup,
secret and prohibited-artifact review, image/privacy inspection, and protected-
file comparisons. At Checkpoint 5 completion, Checkpoint 6 had not started.

### Checkpoint 6 requirements reconciliation and impact assessment

Checkpoint 6 expands Phase 10 without reopening or invalidating Checkpoints 1
through 5. Those checkpoints remain completed at recovery reference
`674ee62e3dd68e4174a1c1fd16e2c72eafd5b41b`; their release governance,
onboarding, packaging, UAT, privacy, and portfolio evidence remain the baseline.
Checkpoint 6 changes planning and requirements only. It adds no application
feature, schema migration, dependency, production-data change, package, tag,
release, external post, or provider call.

#### Governed Agile-artifact generation requirements

- PMC must generate Epics, Capabilities, Features, and User Stories only from
  one or more Product-Manager-selected Approved BRDs or PRDs. Source selection
  is constrained to the selected product so evidence from another product
  cannot enter the generation context accidentally.
- Each generated item is a typed Agile artifact with its own title,
  description, acceptance criteria, artifact-level source links, and an
  optional parent relationship that supports the order Epic → Capability →
  Feature → User Story. Every artifact type requires at least one nonblank,
  testable acceptance criterion; a batch is invalid if any item lacks one.
- Every artifact and acceptance criterion must retain traceability to the
  source product ID and name, source document ID and title, document type, and
  relevant section key and title. The review view must expose that traceability
  before acceptance, and accepted records must retain immutable provenance
  snapshots sufficient for later audit.
- Generation produces a temporary review batch. No generated artifact is saved
  merely because a model returned it or because a reviewer edited it. The
  Product Manager must review the artifacts, acceptance criteria, traceability,
  unsupported-claim findings, and missing-source findings, then perform a
  separate explicit acceptance action.
- Existing generic accepted generated artifacts remain readable and separate
  from BRDs and PRDs. The new Agile-artifact schema and migration must be
  additive, preserve every existing product, document, section, accepted
  artifact, citation, timestamp, and relationship, and keep original BRDs/PRDs
  unchanged.

#### Grounding profiles and unsupported-content policy

- The supported behavior profiles are **Strictly Grounded**, **Balanced**, and
  **Exploratory**. Agile-artifact generation defaults to Strictly Grounded on
  first load, rerun, and invalid or missing profile input.
- Strictly Grounded may restate, decompose, and format only explicit source
  requirements. Balanced may make conservative requirement-preserving
  refinements but must label any source gap rather than fill it. Exploratory may
  propose hypotheses, alternatives, or questions, but must label them as
  unsupported proposals. Profiles change generation behavior, not source
  eligibility, traceability, review, or save-time safety gates.
- Retrieval Top-K is an independent retrieval control. It limits the number of
  ranked source chunks supplied as evidence and must not select a behavior
  profile or silently change model-generation settings. Profile and any later
  model-generation controls are represented, validated, tested, and displayed
  separately from Top-K.
- An **unsupported claim** is a substantive statement in an artifact title,
  description, relationship, or acceptance criterion that cannot be mapped to
  cited text in a currently eligible Approved BRD/PRD section. New numeric
  targets, dates, actors, scope, dependencies, constraints, outcomes, or
  requirement relationships are unsupported unless the cited source supports
  them. Merely attaching a citation does not make a claim supported.
- Unsupported-claim detection must return claim-level findings with artifact
  location, explanation, and available source references. Missing requirements
  must be reported explicitly as source gaps or questions; the model must not
  invent values or silently convert gaps into requirements.
- Any unsupported claim, unlabeled proposal, missing acceptance criterion,
  incomplete traceability, stale/ineligible source, malformed structured
  output, or unresolved source gap blocks acceptance and persistence for the
  affected review batch. This invariant is enforced again at the trusted
  service/persistence boundary so a UI bypass cannot save unsafe content.
- Human revision does not waive grounding. Revised content is rechecked before
  acceptance. Exploratory proposals become saveable only after the missing
  requirement is added to and approved in a source BRD/PRD, followed by fresh
  generation or revalidation against that source.

#### BRD and PRD export requirements

- Any saved BRD or PRD may be exported on demand as a Word `.docx` file or PDF.
  Export is a read-only operation and must preserve document title, product,
  type, version, status, ordered section labels and content, and generated-at
  metadata without changing the database or source document.
- Export filenames must be deterministic and sanitized. User content is treated
  as data, not markup or executable instructions. Export failures are
  user-safe, create no partial database state, expose no local path or secret,
  and do not require a network call.
- Native Google Docs export is explicitly deferred until after the revised
  Phase 10 sequence unless separately approved.

#### Interface, security, and verification requirements

- The interface must provide an intentional workflow for product and Approved
  source selection, artifact-type selection, behavior profile, independent
  Top-K, generation status, structured artifact review, acceptance criteria,
  traceability, unsupported claims, missing requirements, revision, rejection,
  explicit acceptance, accepted-artifact history, and Word/PDF export.
- Prompt-injection-like text inside a source document remains untrusted data.
  Provider errors, hidden instructions, credentials, local paths, and raw SQL
  are never displayed or persisted. No source content is sent before the user
  initiates generation, and only the selected eligible source material needed
  for that request crosses the optional provider boundary.
- Verification must use temporary databases, deterministic fake or mocked AI
  providers, and fixture documents. It must cover additive migration and
  rollback, artifact hierarchy and validation, profile defaults and boundaries,
  Top-K independence, source scoping, structured-output failures, claim-level
  support checks, missing-requirement reporting, revision revalidation,
  persistence bypass attempts, stale-source rejection, traceability, exports,
  UI reruns/idempotency, source separation, no-key behavior, and regression of
  all completed Checkpoints 1 through 5.

#### Implementation impact assessment

| Area | Current baseline | Required later-checkpoint change |
| --- | --- | --- |
| Data model | Generic generated text and citation snapshots | Typed Agile artifacts, ordered criteria, hierarchy, batches, profiles, support findings, source gaps, and richer provenance |
| Database | `generated_artifacts` plus section-level citations | Additive accepted-Agile tables, constraints, indexes, idempotent transactional save, preservation migration, and fail-closed write validation |
| AI services | Unstructured Responses API text and embeddings | Versioned structured output, profile-aware prompt contracts, safe parsing, source scoping, and separate retrieval versus generation settings |
| Grounded workflow | Query-wide Approved-source retrieval and citation display | Intentional document selection, claim-level support assessment, missing-requirement reporting, revision rechecks, and batch-level save blocking |
| UI | One generic grounded-draft form and text review | Artifact/source/profile/Top-K controls, hierarchy and criteria review, traceability and finding panels, explicit batch acceptance, history, and exports |
| Export | No document export | Local read-only Word and PDF renderers, downloads, safe filenames, layout/content verification, and dependency/package review |
| Tests and evaluation | 252 deterministic tests and Phase 9 grounding scores | Migration, contracts, profiles, Top-K isolation, structured failures, unsupported claims, gaps, bypasses, UI, export, security, and full regression cases |
| Security | Approved-only retrieval, secret isolation, source revalidation | Cross-product isolation, source prompt-injection defense, output/schema limits, claim/save gates, export/path safety, and stale-source race coverage |
| Documentation | Checkpoints 1–5 release and portfolio records | Revised architecture, responsible use, UAT, install/dependencies, release manifest, case study, demo, changelog, and final release evidence after implementation |

Checkpoint 6 is complete as a requirements-reconciliation checkpoint on August
10, 2026. The existing 252-test suite passed before document changes. No new
feature is represented as implemented; implementation begins only in the
additional checkpoints defined in `IMPLEMENTATION_PLAN.md`, and the original
release-candidate checkpoint moves to the end of that revised sequence.

#### Checkpoint 7 implementation record

Checkpoint 7 is complete on August 11, 2026. PMC now has validated contracts
for typed Epic, Capability, Feature, and User Story records; ordered structured
acceptance criteria; optional hierarchy; artifact- and criterion-level Approved
BRD/PRD section traceability; review state; profile identity; provenance;
revision; and UTC timestamps. Six additive SQLite tables store only accepted
Agile batches, artifacts, criteria, immutable source snapshots, and source
links. The exact Phase 9 schema upgrades transactionally and idempotently while
preserving all existing rows and generic accepted-artifact behavior. Pending
review, generation/profile behavior, claim-support assessment, acceptance
workflow changes, UI, and export remain assigned to later checkpoints.

Checkpoint 7 verification uses temporary databases only: 24 focused tests and
the complete 276-test suite pass. The production database and backups were not
opened or modified, and Checkpoint 8 was not started.

#### Checkpoint 8 implementation record

Checkpoint 8 is complete on August 11, 2026. PMC now has immutable definitions
for Strictly Grounded, Balanced, and Exploratory behavior, with Strictly
Grounded as the fail-closed default. Five versioned prompt/task definitions
cover Epics, Capabilities, Features, User Stories, and structured acceptance
criteria. Their envelopes separate trusted instructions and application
selections from Product Manager request and untrusted Approved BRD/PRD source
data, while strict response contracts require typed artifacts or criteria,
claim/source references, missing requirements, and labeled proposals.

Retrieval Top-K is represented only by `RetrievalControls`. Temperature and
Top-P are separate optional `GenerationControls`, and an explicit provider/model
capability contract deterministically includes, omits, or rejects them without
substitution. Provider parameters remain implementation hints rather than a
grounding guarantee. Existing Phase 9 prompts and AI service calls are
unchanged, and Checkpoint 7 persistence requires no schema change.

Checkpoint 8 verification uses mocks and local deterministic data only: 17
focused tests and the complete 293-test suite pass. No API call or production
database access occurred. Grounded Agile generation, claim-support assessment,
save blocking, UI, and export remain assigned to later checkpoints; Checkpoint
9 was not started.

#### Checkpoint 9 implementation record

Checkpoint 9 is complete on August 11, 2026. PMC now performs read-only,
Product-and-document-scoped retrieval from Approved BRDs and PRDs, revalidates
the exact ranked chunks before and after the injected provider boundary, and
creates temporary typed Epics, Capabilities, Features, User Stories, or
structured acceptance criteria through the Checkpoint 8 prompts and controls.
Strict response validation resolves artifact-, criterion-, and claim-level
citations only against the supplied generation context and rejects malformed,
duplicate, fabricated, cross-scope, or incomplete mappings.

The application deterministically extracts field-level claims from titles,
descriptions, parent relationships, and acceptance criteria, gives them stable
content-derived IDs, and applies a conservative text-correspondence assessment.
The approved outcomes are supported, unsupported, ambiguous, and missing
source; contradiction and uncited/unresolved citation conditions are explicit
reasons within those outcomes. Citation presence or keyword overlap alone is
never support. This deterministic method is intentionally labeled as neither a
probabilistic score nor a semantic guarantee; ambiguous and unsupported output
remains blocked for later review.

Strictly Grounded is the default. Balanced may report gaps without filling
them, and Exploratory alone may return clearly labeled unsupported,
non-saveable proposals. Every profile retains identical source, citation, and
support-integrity controls. All results remain in memory with `can_save=False`;
Checkpoint 9 adds no schema or accepted-storage write path.

Checkpoint 9 verification uses injected providers and temporary databases
only: 22 focused tests and the complete 315-test suite pass. No live provider
call or production-database access occurred. At Checkpoint 9 completion,
Checkpoint 10 review, revision, acceptance, and persistence had not started.

#### Checkpoint 10 implementation record

Checkpoint 10 is complete on August 13, 2026. A generated Agile result now
enters an immutable, in-memory pending review containing its original and
current structured artifacts, criteria, traceability, exact source chunks,
profile, prompt, Top-K, gaps, proposals, claims, assessments, gates, version,
reviewer events, timestamps, and reasons. Generation is never acceptance.

A changed review revision increments the version and reruns hierarchy,
metadata, source-scope/freshness, citation, claim, criterion, gap, and proposal
checks. Unchanged content is a deterministic no-op. Rejection requires a reason
and remains unsaved. Acceptance requires the current revision, current
assessment, explicit reviewer action, and every gate to pass. Immediately
before saving, sources are revalidated again; the database entry point
independently reassesses all claims and criteria and checks exact full-section
digests within the accepted-batch transaction. Failed and repeated operations
produce zero partial or duplicate rows.

Checkpoint 10 reuses the additive Checkpoint 7 accepted Agile schema. Pending,
revised, blocked, and rejected evidence remains in memory as approved; only the
fully accepted batch, typed hierarchy, criteria, provenance, revisions, and
source snapshots enter accepted storage. Verification uses 24 focused tests
and the complete 339-test suite with temporary databases and no provider call.
#### Checkpoint 11 implementation record

Checkpoint 11 implements the guided seven-destination Product workspace,
Dashboard onboarding, approved nine-group BRD and PRD builders, and the governed
Agile generation/review interface over the existing Checkpoints 7–10 services.
The interface intentionally selects a Product, Approved BRD/PRD sources, Agile
type, applicable parent, approved profile, and separate retrieval Top-K; it
shows prompt identity, structured artifacts and criteria, citations, claim
support, gates, and accept/revise/reject actions. Revisions reassess and every
failed gate remains fail-closed.

PRDs now include a separate ordered Success Matrix whose entries contain stable
IDs, requirement/outcome, metric, optional baseline, target, minimum acceptance
threshold, measurement method, data source, evaluation period, validation
owner, and status. Draft rows may be incomplete; approval requires at least one
entry and every measurable field except baseline. Existing document content is
not rewritten, and the additive child table initializes empty for old PRDs.
Temperature, Top-P, GEPA, and hallucination flags are internal controls rather
than PRD fields. Grounding quality is expressed as a measurable outcome.

The PRD builder also provides repeatable Epic, Capability, Feature, and User
Story records using the shared typed parent map. Each record has a stable ID,
deterministic type-relative order, explicit parent where required, and its own
repeatable acceptance criteria. Drafts may be incomplete; approval requires all
four levels, valid Epic → Capability → Feature → User Story relationships,
complete artifact content, and measurable criteria for every entry. General
functional requirements and existing user-story or acceptance-criteria text
remain separate preserved outline sections.

The completed Product Manager review keeps PRD hierarchy counts informational,
shows Success Matrix counts separately, adds help-only tracking/telemetry
examples, and uses repeatable Contributors/Roles and combined Date/Milestone
pairs. BRDs use repeatable Epic-to-User-Story hierarchy rows with independently
owned criteria at every level and linked Business Risk/Mitigation rows. Drafts
may keep incomplete rows; Approved documents validate structured completeness,
parent relationships, and measurable criteria. Additive persistence and safe
legacy initialization preserve all existing section text without copying or
overwriting it.

At Checkpoint 11 completion, Checkpoint 12 remained not started. Its Word/PDF
exports were required to include the Success Matrix, and no export
implementation was part of Checkpoint 11.

#### Checkpoint 12 implementation record

Checkpoint 12 is complete on August 14, 2026. Every saved Draft or Approved BRD
and PRD preview now offers Word and PDF downloads. One shared ordered export
model preserves associated Product metadata, document title/type/ID/version/
status, generated-at time, all stable professional-outline sections, PRD
Contributors and Roles, Key Dates and Milestones, PRD Agile hierarchy and
owner-specific criteria, the PRD Success Matrix, BRD hierarchy and criteria,
and linked Business Risk/Mitigation rows. Legacy-derived structured content is
emitted once; distinct legacy section content is labeled and preserved.

`python-docx==1.2.0` generates macro-free Open XML with explicit Letter-page
geometry, styles, fixed-width tables, metadata, and page furniture. ReportLab
5.0.0 generates local PDFs from the same content model with embedded Unicode
font data, wrapping, repeated headers, and multi-page flow. Both formats are
returned as in-memory bytes through sanitized deterministic filenames. Export
does not write the database, create a schema migration, call a provider, require
an API key, invoke Microsoft Word, or use a hosted converter. Native Google Docs
export remains deferred.

#### Checkpoint 13 integrated verification record

Checkpoint 13 is complete on August 15, 2026. Integrated UAT covers the
Dashboard and all seven destinations; Product CRUD/search/safe deletion; Draft
and Approved BRD/PRD creation, editing, preview, structured hierarchy, separate
acceptance criteria, and PRD Success Matrix behavior; Approved-only retrieval;
no-key and empty states; governed Agile generation, review, revision,
rejection, acceptance, and every claim/citation/freshness/hierarchy/gap/proposal
gate; accepted/source separation; fictional onboarding; local launchers; and
Draft/Approved Word/PDF export content, formatting, and safe filenames.

Security review and deterministic adversarial regression cover prompt injection,
cross-product leakage, malformed structured output, unsupported-content bypass,
stale-source races, input limits, export/path injection, repository temporary
files, and provider-error redaction. Verification used temporary databases,
fictional records, injected providers, and no real key or live provider call.
Fourteen focused Checkpoint 13 tests, 397 complete-regression tests, 20 release-
metadata tests, 10 package tests, and 6 launcher tests passed. PDF visual review
covered all 19 generated pages and DOCX package/content validation passed. The
user subsequently opened and approved the regenerated four DOCX and four PDF
files in their associated macOS applications, including content, English-name
display, and formatting.
No application code, schema, dependency, screenshot, or release-manifest change
was required; documentation drift and the disposable manual-review fixture's
non-English personal names were corrected. Unicode export coverage remains in
isolated automated test data. Checkpoint 14 release-candidate verification is
complete. A deterministic local candidate and checksum were prepared outside
the repository, installed into a fresh extracted environment, and exercised
without an API key using only fictional data and disposable databases. The
manifest, permissions, checksums, dependency licenses, compatibility claims,
integrated workflows, exports, and draft GitHub Release materials passed review.
v1.0.0 was tagged and published after separate approval on August 19, 2026.
Its tag, GitHub Release, and assets are immutable inputs to Checkpoint 15.

#### Checkpoint 15 controlled-beta onboarding requirements

Checkpoint 15 prepares v1.0.1 as a controlled-beta/portfolio release suitable
for technical evaluation. One macOS starter must create or reuse `.venv`,
install only pinned requirements when needed, open the local application on
port 8501, and work from any current Terminal directory. Normal startup must
not ask for an API key. Optional AI remains process-environment-only and is
explained inside the AI Assistant.

The Dashboard and portfolio materials must describe grounded Agile assistance
from Approved BRDs/PRDs and the citation, freshness, claim-support, human-review,
and explicit-acceptance controls. They must not claim independent AI decisions,
commercial production readiness, adoption, customer outcomes, signed/notarized
macOS packaging, or native Windows validation. Checkpoint 15 changes no schema,
source-of-record behavior, grounding gate, review rule, acceptance boundary, or
export contract.
