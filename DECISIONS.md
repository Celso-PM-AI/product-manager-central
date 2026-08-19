# Product Manager Central
## Architecture & Product Decisions
- DEC-001 SQLite Database
- DEC-002 Archive CSV
- DEC-003 Simplified Architecture
- DEC-004 AI Deferred Until MVP
- DEC-005 Deterministic Templates and Normalized Document Storage
- DEC-006 Isolated OpenAI and Approved-Source Boundaries
- DEC-007 Revalidated Semantic Retrieval
- DEC-008 Cited Generated Drafts Without Persistence
- DEC-009 Separate, Idempotent Human-Accepted Generated Artifacts
- DEC-010 Code-Controlled Prompt Catalog and Explicit Assistant Selection
- DEC-011 Deterministic Offline RAG Evaluation and Mandatory Release Gates
- DEC-012 Local Portfolio Release Governance and Distribution
- DEC-013 Optional Fictional Onboarding Data and Read-Only Artifact History
- DEC-014 Allowlisted Cross-Platform Source Packaging
- DEC-015 Evidence-Qualified Portfolio Materials and Fictional Visuals
- DEC-016 Typed Agile Expansion Before Release
- DEC-017 Conservative Grounded Agile Support Assessment
- DEC-018 Re-grounded Agile Review and Fail-Closed Acceptance
- DEC-019 Guided Workspace, Professional Document Builders, and PRD Success Matrix
- DEC-020 Explicit PRD Agile Hierarchy
- DEC-021 Local In-Memory Word and PDF Export

This document records significant product, architecture, and technical decisions made during the development of Product Manager Central (PMC).

---

## Decisions

- DEC-001 SQLite Database
- DEC-002 Archive CSV
- DEC-003 Simplified Architecture
- DEC-004 AI Deferred Until MVP
- DEC-005 Deterministic Templates and Normalized Document Storage
- DEC-006 Isolated OpenAI and Approved-Source Boundaries
- DEC-007 Revalidated Semantic Retrieval
- DEC-008 Cited Generated Drafts Without Persistence
- DEC-009 Separate, Idempotent Human-Accepted Generated Artifacts
- DEC-010 Code-Controlled Prompt Catalog and Explicit Assistant Selection
- DEC-011 Deterministic Offline RAG Evaluation and Mandatory Release Gates
- DEC-012 Local Portfolio Release Governance and Distribution
- DEC-013 Optional Fictional Onboarding Data and Read-Only Artifact History
- DEC-014 Allowlisted Cross-Platform Source Packaging
- DEC-015 Evidence-Qualified Portfolio Materials and Fictional Visuals
- DEC-016 Typed Agile Expansion Before Release
- DEC-017 Conservative Grounded Agile Support Assessment
- DEC-018 Re-grounded Agile Review and Fail-Closed Acceptance
- DEC-019 Guided Workspace, Professional Document Builders, and PRD Success Matrix
- DEC-020 Explicit PRD Agile Hierarchy
- DEC-021 Local In-Memory Word and PDF Export

## Decision 001

**Date:** July 19, 2026

**Category:** Database

**Title:** SQLite will be the primary database

**Decision:**
SQLite will be the sole database used for the Product Manager Central MVP.

**Reason:**
- Lightweight
- Easy to install
- No separate database server
- Perfect for an MVP

**Alternatives Considered:**
- CSV
- PostgreSQL

**Impact:**
SQLite becomes the single source of truth for all product information.

**Status:**
Approved

# Product Manager Central

## Architecture & Product Decisions

### Decisions


...

## Decision 005

**Date:** August 1, 2026

**Category:** Product documents and data architecture

**Title:** Phase 8 uses deterministic templates and normalized document storage

**Decision:**
Product Manager Central will author BRDs and PRDs through deterministic,
user-completed templates. Stable section keys, labels, guidance, and display
order are centralized in `src/document_templates.py`. Document metadata is
stored in `documents`, and section content is stored in `document_sections`.
Every document has a stable database ID and a foreign-key association to one
product. Foreign keys are enforced, and product deletion cascades to associated
documents and sections.

Draft documents may contain empty body sections. Approved documents require
content in every section. Product prepopulation is copied only when a new
document form is opened and does not remain synchronized with later product
edits.

Phase 8 does not create or integrate an LLM, call an AI API, require API tokens,
or generate document content. It does not add Word or PDF export.

**Reason:**
- Deterministic templates keep behavior inspectable, repeatable, and testable.
- Normalized section rows avoid a wide table of type-specific nullable columns.
- Stable IDs make multiple same-product documents and safe editing unambiguous.
- An additive transaction preserves existing product records and workflows.

**Alternatives Considered:**
- One wide document table containing every BRD and PRD section.
- JSON-encoded section content in the document row.
- LLM-generated document content.

**Impact:**
Template section keys become persistent schema identifiers. Existing canonical
databases receive the two document tables and product index through a narrow,
transactional migration. Deleting a product also permanently deletes its
associated documents, which the UI must disclose before confirmation.

**Status:**
Approved

## Decision 006

**Date:** August 4, 2026

**Category:** AI architecture and security

**Title:** Phase 9 begins with isolated OpenAI and approved-source boundaries

**Decision:**
PMC will use the official OpenAI Python SDK and the Responses API behind a small,
injectable service. The optional API key is read only from `OPENAI_API_KEY` in
the process environment; configuration status contains no key value. The model
uses a documented default and can be overridden with `OPENAI_MODEL` without a
source change.

Retrieval remains deterministic and read-only in Checkpoint 1. Only sections
from Approved BRDs and PRDs are eligible. Drafts and unsupported types are
excluded. Results carry product ID/name, document ID/title/type, and section
key/title/content so future answers can cite the source precisely. The existing
schema is sufficient and will not change for this checkpoint.

Original source documents must never be modified automatically. AI-generated
content must remain separate and cannot be saved until a human reviews and
explicitly accepts it.

**Reason:**
- Environment-only credentials keep secrets out of source control and logs.
- Dependency injection provides token-free, network-free automated tests.
- Approved-only retrieval establishes a narrow trust boundary before RAG is
  implemented.
- Reusing normalized sections avoids an unnecessary schema migration.

**Alternatives Considered:**
- Storing an API key in source, configuration files, or the database.
- Retrieving Draft documents or arbitrary document types.
- Adding embeddings or generated-content tables before their workflows exist.
- Allowing generated text to overwrite approved source documents.

**Impact:**
Phase 9 can build later assistant capabilities on explicit service and source
boundaries. Embeddings, semantic search, the full interface, answer generation,
generated-content acceptance, and RAG evaluation remain deferred.

**Status:**
Approved

## Decision 007

**Date:** August 5, 2026

**Category:** Semantic retrieval and source trust

**Title:** Phase 9 semantic retrieval revalidates approved source chunks

**Decision:**
PMC will create deterministic, paragraph-aware chunks only from Approved BRDs
and PRDs. Each chunk retains product ID/name, document ID/title/type/approval
status, section key/title, chunk index, stable content-derived ID, and unchanged
source text. Embeddings use the existing injectable official OpenAI client
boundary, and the embedding model is configurable with
`OPENAI_EMBEDDING_MODEL`.

Semantic results use cosine similarity, descending rank order, a configurable
result limit, and a configurable minimum similarity. PMC re-reads eligible
sources after embedding and excludes any chunk whose source was deleted,
edited, made Draft, or otherwise became ineligible. Empty source sets and empty
relevance sets produce distinct results.

Keyword search remains literal product-field substring matching. Semantic
retrieval is a separate approved-document capability that can find conceptual
similarity despite different wording.

**Reason:**
- Stable meaningful chunks make ranking repeatable and citations precise.
- Dependency injection keeps tests deterministic, network-free, and token-free.
- Live eligibility revalidation prevents stale embeddings from bypassing the
  Approved-only trust boundary.
- Keeping retrieval separate from generation prevents source documents from
  being treated as generated or editable output.

**Alternatives Considered:**
- Retrieving whole documents as single embeddings.
- Persisting embeddings before an invalidation design is required.
- Including Draft documents and filtering them only in a future interface.
- Combining semantic document retrieval with existing product keyword search.

**Impact:**
Checkpoint 2 requires no schema migration and never writes to products or
documents. The assistant interface, answer generation, generated-content
acceptance/saving, prompt management, and RAG evaluation remain deferred.

**Status:**
Approved

## Decision 008

**Date:** August 5, 2026

**Category:** Grounded AI generation and human control

**Title:** Checkpoint 3 returns cited generated drafts without persistence

**Decision:**
PMC will accept generation requests through a Streamlit-independent service,
retrieve only currently Approved BRD and PRD chunks, construct a source-numbered
grounded prompt, and call the Responses API through the existing injectable
OpenAI boundary. The result carries immutable structured citations containing
the product name/ID, document title/ID/type, and section title/key.

Generated text is explicitly identified as an AI-generated draft and remains
separate from source documents. When no approved or relevant context is found,
PMC will not call text generation and will not claim grounding. Checkpoint 3
provides no save or acceptance operation. Original BRDs and PRDs are never
modified, overwritten, or appended by this workflow; later saving requires
human review and explicit acceptance in Checkpoint 4.

**Reason:**
- Deterministic citations keep generated claims traceable to trusted sources.
- A service boundary makes prompt construction and safety behavior testable
  without Streamlit, a network, or a real API key.
- No-result short-circuiting prevents unsupported output from being presented
  as grounded.
- Deferring persistence preserves human control and avoids a schema change.

**Alternatives Considered:**
- Generating when retrieval returns no Approved context.
- Including Draft or unsupported documents in the prompt.
- Letting model output update or append to original BRDs or PRDs.
- Adding generated-content storage and acceptance controls in Checkpoint 3.

**Impact:**
The AI Assistant can produce temporary cited drafts. Provider and malformed
response failures are reported with safe messages, tests remain fully mocked,
and the database schema and source documents remain unchanged. Generated-draft
review, explicit acceptance, and saving remain Checkpoint 4 work.

**Status:**
Approved

## Decision 009

**Date:** August 9, 2026

**Category:** Generated-content review and persistence

**Title:** Checkpoint 4 stores only explicitly accepted generated artifacts

**Decision:**
PMC will keep grounded generation, human review, and persistence as separate
steps. A generated draft enters an in-memory pending review that displays its
original AI output and immutable structured citations. A Product Manager may
reject it, revise it while it remains pending, or explicitly choose **Accept and
save**. No pending or rejected review creates a saved artifact.

Explicitly accepted content is stored in separate `generated_artifacts` and
`generated_artifact_citations` tables rather than in `documents` or
`document_sections`. The artifact retains its target product, request, original
AI output, accepted text, revision indicator, timestamps, and citation snapshots
with source product, document, type, and section IDs/metadata. Acceptance
revalidates every cited source as a current Approved BRD or PRD. A unique review
key makes repeated submissions and Streamlit reruns idempotent.

**Reason:**
- Explicit acceptance keeps the Product Manager in control of persistence.
- Separate tables prevent generated content from overwriting or being confused
  with original BRDs and PRDs.
- Preserving original and accepted text makes human revision auditable.
- Source revalidation maintains the Approved-only trust boundary through save.
- Idempotent acceptance prevents duplicate artifacts during UI reruns.

**Alternatives Considered:**
- Automatically saving generated drafts before review.
- Updating a cited BRD or PRD with accepted generated text.
- Persisting rejected and pending reviews as approved product artifacts.
- Replacing the original AI output after a human revision.

**Impact:**
Checkpoint 4 adds a narrow additive schema migration and a review service that
can be tested with deterministic generated results. Original source documents
remain unchanged. Prompt management, workflow hardening, and RAG evaluation
remain deferred to Checkpoints 5 and 6.

**Status:**
Approved

## Decision 010

**Date:** August 9, 2026

**Category:** Prompt management and assistant workflow safety

**Title:** Checkpoint 5 uses a code-controlled prompt catalog

**Decision:**
PMC will define approved assistant prompts as immutable source-controlled
definitions. Each prompt has a stable ID, public name and description,
supported assistant task, explicit semantic version, hidden system
instructions, deterministic user-prompt template, and required input fields.
The existing grounded-draft rules move into the initial catalog entry without
changing their approved-only evidence boundary or citation requirements.

The AI Assistant requires explicit product, task, prompt, and request selection
before retrieval or generation. Only built-in prompts mapped to the selected
task are eligible. The interface displays public prompt metadata but never
system instructions, API credentials, or provider exception details. Streamlit
session state distinguishes a completed submission from a rerun so generation
is not repeated accidentally; Checkpoint 4 acceptance remains idempotent.

Prompts are not editable in the UI, stored in SQLite, product-specific, shared,
imported, exported, optimized, or experimentally varied. No schema change is
authorized.

**Reason:**
- Version-controlled prompts are reviewable and reproducible.
- Explicit task/prompt selection prevents unsupported prompt execution.
- Deterministic validation stops incomplete requests before retrieval or API use.
- Public metadata explains the selected behavior without exposing hidden
  instructions.
- Rerun hardening avoids duplicate provider actions while preserving explicit
  human review and acceptance.

**Alternatives Considered:**
- User-authored or user-editable prompts.
- Database-backed prompt storage and version history.
- Product-specific prompts, prompt sharing, and import/export.
- Prompt experimentation, automated optimization, and evaluation scoring.

**Impact:**
Checkpoint 5 adds a source-only catalog and hardens the existing assistant
workflow without modifying the database or original BRDs/PRDs. RAG evaluation,
benchmarking, dashboards, and LLM-as-a-judge remain Checkpoint 6 work.

**Status:**
Approved

## Decision 011

**Date:** August 9, 2026

**Category:** RAG evaluation and release verification

**Title:** Checkpoint 6 uses deterministic offline scoring with mandatory safety gates

**Decision:**
PMC will evaluate the completed Phase 9 workflow through developer-facing,
code-controlled cases. Retrieval precision and recall compare expected and
returned stable chunk IDs. Source trust, grounded generation, human control,
and source separation are binary scores. Citation completeness and
citation/source correspondence are fractional scores across citations.

The eight criteria are averaged without weights and reported on a 0–100 scale.
A release passes only with at least 80 overall and perfect source-trust,
citation-completeness, human-control, and source-separation scores. Suites
average each criterion across their cases before applying the same gates.

Evaluation uses deterministic fake providers and temporary databases. It does
not use a live OpenAI request, real API key, LLM-as-a-judge, Streamlit dashboard,
database persistence, or schema change.

**Reason:**
- Stable chunk IDs make retrieval precision and recall reproducible.
- Separate citation scores expose missing metadata and incorrect source links.
- Mandatory safety gates prevent a high average from masking a trusted-source,
  citation, human-control, or source-separation failure.
- Offline cases validate success, failure, empty, stale-source, and boundary
  behavior without cost, network variability, or production-data risk.

**Alternatives Considered:**
- LLM-as-a-judge scoring.
- A Streamlit evaluation dashboard.
- Persisted evaluation history or a database-backed benchmark catalog.
- Weighted criteria or allowing aggregate scores to override safety failures.
- Live-provider calls during automated evaluation.

**Impact:**
Checkpoint 6 completes Phase 9 with deterministic scoring and end-to-end release
verification. It changes no application workflow, source document, database
schema, or production data. Future live-quality studies and evaluation
dashboards remain outside the approved scope.

**Status:**
Approved

## Decision 012

**Date:** August 9, 2026

**Category:** Portfolio release and distribution

**Title:** Phase 10 prepares a governed local v1.0.0 source release

**Decision:**
Product Manager Central will prepare v1.0.0 as its first public portfolio
release under the MIT License. Distribution will be a source-based GitHub
Release ZIP with Mac and Windows setup and launch helpers. It will remain a
single-user local Streamlit and SQLite application; native signed installers,
cloud hosting, authentication, hosted databases, billing, and enterprise
operations are excluded.

The release package will never contain the existing production database, a
prebuilt sample database, secrets, environment files, backups, archives,
caches, or personal data. Clean startup remains the default. Fictional sample
data will be optional and user-triggered. The repository-local `data/pmc.db`
location remains the v1.0 approach, with launchers required to use the correct
application directory and documentation required to protect data during updates
and uninstalling.

Python and operating-system support will be claimed only after a clean virtual
environment can install every direct runtime dependency, pass the complete
automated suite, and pass an isolated application smoke test on that exact
combination. Direct dependencies will be pinned only after this evidence exists;
Phase 10 will not add an unnecessary transitive lock or packaging framework.

Phase 10 also authorizes no-secret CI, a four-to-six-PM beta plan, a read-only
accepted-artifact history, sanitized fictional screenshots, recruiter-facing
materials, and an exact `.gitignore` rule for the protected local screenshot.
None of those later-checkpoint deliverables is started by Checkpoint 1.

**Reason:**
- Clear licensing and versioning make the portfolio release usable and
  reviewable by others.
- Evidence-based compatibility claims avoid misleading Mac and Windows users.
- A source ZIP is transparent and maintainable without installer signing or
  notarization complexity.
- Clean and fictional-only data boundaries prevent production or personal data
  from entering a public artifact.
- Separate publication approval prevents planning metadata from being mistaken
  for an actual release.

**Alternatives Considered:**
- Native Mac and Windows installers.
- Cloud or hosted distribution.
- Bundling the production or a prebuilt sample database.
- Automatically loading sample data.
- Claiming Python support from the existing development environment alone.
- Pinning dependencies before clean-install evidence is available.

**Impact:**
Checkpoint 1 adds governance and planned v1.0.0 metadata without changing the
application, dependency set, database schema, or Phase 9 safeguards. Later
Phase 10 checkpoints remain subject to separate implementation and verification.
Checkpoint 1 verification passed with 214 tests and no production-data change.

**Status:**
Approved

## Decision 013

**Date:** August 9, 2026

**Category:** First-time experience and artifact visibility

**Title:** Fictional onboarding data is explicit and accepted-artifact history is read-only

**Decision:**
The default Dashboard provides plain-language Getting Started guidance covering
the local product/document workflow, Draft versus Approved status, Approved-only
AI sources, citations, human review, explicit acceptance, source-document
separation, and secure local API-key configuration.

A user may explicitly load one deterministic fictional Trailwise workspace. PMC
never loads it automatically and never distributes a prebuilt database. A
source-controlled marker identifies the sample without relying on a product name
that a user might also choose. Repeated activation returns the existing marked
sample instead of creating another. If an interrupted first load left the marked
sample incomplete, a retry creates only a missing sample document and then marks
the sample ready. Existing user products and documents are never updated or
replaced.

Normal product detail displays separately persisted, explicitly accepted AI
artifacts. The history is read-only and includes purpose, accepted content,
revision context, acceptance timestamps, product association, and complete
citation metadata. It provides no artifact edit, delete, regenerate, or
source-update action. Original BRDs and PRDs remain unchanged.

**Reason:**
- New Product Managers need the safety model before trying AI-assisted work.
- Optional fictional data makes the workflow explorable without exposing or
  copying production information.
- A deterministic marker makes repeat loading safe while avoiding changes to
  user-authored records.
- Read-only history makes accepted work discoverable without weakening human
  control or source separation.

**Alternatives Considered:**
- Automatically loading sample data into every new database.
- Shipping a prebuilt SQLite sample database.
- Matching sample data by product name alone.
- Adding artifact editing, deletion, or regeneration controls.
- Mixing accepted artifacts into the BRD/PRD document list.

**Impact:**
Checkpoint 2 adds application guidance, an optional source-controlled fictional
dataset, and a read-only view over the existing generated-artifact tables. It
does not change the schema, dependencies, AI provider behavior, or Phase 9
safeguards.

**Status:**
Approved

## Decision 014

**Date:** August 9, 2026

**Category:** Local installation and release packaging

**Title:** PMC uses pinned direct dependencies and an explicit source-release allowlist

**Decision:**
PMC's direct runtime dependencies are pinned to the versions that passed a
clean installation, full suite, and no-key smoke test: Streamlit 1.61.1, pandas
3.0.5, and OpenAI 2.53.0. Python 3.11 is the dependency-imposed prerequisite
floor, and launchers accept Python 3.11 through 3.14. Native support is claimed
only for the validated macOS 26.5.2 arm64 and Python 3.14.6 combination.
Windows and Python 3.11–3.13 remain structurally tested but not natively
validated.

Mac and Windows setup helpers resolve the application directory from their own
location, create or reuse `.venv`, install only `requirements.txt`, and stop on
failed prerequisites. Separate run helpers use the virtual environment and
launch `app.py`. Optional API keys use masked, process-only prompts and are
never echoed, persisted, or passed as command arguments.

The release builder reads only `release_manifest.txt`; it never discovers files
through broad directory inclusion. Manifest entries are validated as safe,
relative, existing regular files. The ZIP's exact member list is checked against
the manifest, forbidden data and secret classes are rejected, timestamps and
permissions are normalized, and a SHA-256 checksum is produced. Existing named
outputs require an explicit `--force`. This capability creates local test
archives only; it does not authorize a tag, GitHub Release, or publication.

**Reason:**
- Direct-version pins make clean installation reproducible without introducing
  a transitive lock or packaging framework.
- Location-relative launchers reduce first-run errors on Mac and Windows.
- Session-only masked key entry avoids committed or persistent credentials.
- An allowlist fails closed and prevents the production database or unrelated
  local files from entering a release by omission rules alone.
- Deterministic ZIP metadata makes identical inputs byte-for-byte reproducible.

**Alternatives Considered:**
- Native signed or notarized installers.
- Broad repository zipping with exclusion patterns.
- Shipping a database or automatically loading fictional data.
- Persisting API keys in `.env` or launcher configuration.
- Claiming Windows and older Python support from simulated tests alone.
- Adding a transitive dependency lock before evidence requires one.

**Impact:**
Checkpoint 3 adds source-controlled installation, launch, packaging, checksum,
and operating guidance. It changes no schema or product workflow and preserves
clean database startup, optional sample loading, and all Phase 9 safeguards.

**Status:**
Approved

## Decision 015

**Date:** August 10, 2026

**Category:** Portfolio evidence and privacy

**Title:** Recruiter materials use evidence-qualified claims and isolated fictional visuals

**Decision:**
Checkpoint 5 presents PMC through a concise case study, source-controlled
Mermaid architecture diagrams, three sanitized fictional screenshots, a
2–4 minute demo storyboard, and clearly labeled draft launch materials. These
assets describe implemented and verified behavior without claiming an external
beta, native Windows or Python 3.11–3.13 validation, production use, measured
customer outcomes, a recorded video, or publication.

Every screenshot is created from an isolated temporary database containing only
the deterministic fictional Trailwise workspace. The AI-review image uses a
deterministic fake provider or safe prepared review state, never a live OpenAI
call or real API key. Images include only the application viewport and are
reviewed at full resolution for browser chrome, names, paths, credentials,
notifications, private data, and identifying metadata.

The README uses the new fictional dashboard screenshot. The outdated Phase 8
image is removed from source and the explicit release manifest. The protected
local screenshot remains ignored and untouched.

**Reason:**
- Recruiters need a short, navigable account of the product problem, decisions,
  safeguards, architecture, evidence, and limitations.
- Source-controlled diagrams and documents are reviewable and remain aligned
  with implementation evidence.
- Isolated fictional capture prevents production or personal data from entering
  public-facing assets.
- Qualified claims distinguish completed engineering work from planned external
  validation and publication.

**Alternatives Considered:**
- Reusing the Phase 8 browser screenshot.
- Capturing screenshots from the production database.
- Using a live provider or real API key to prepare portfolio visuals.
- Publishing launch copy or recording a demo during Checkpoint 5.
- Presenting structural platform tests as native validation.

**Impact:**
Checkpoint 5 changes documentation, portfolio images, the release allowlist,
and metadata tests only. It changes no application behavior, schema,
dependency, launcher, or packaging logic and preserves every Phase 9 trust and
human-control safeguard.

**Status:**
Approved

## Decision 016

**Date:** August 10, 2026

**Category:** Governed Agile generation and document export

**Title:** Phase 10 expands before release with typed, fail-closed Agile artifacts

**Decision:**
Phase 10 will add generation of Epics, Capabilities, Features, and User Stories
from intentionally selected Approved BRDs or PRDs associated with the selected
product. Each generated artifact will have at least one testable acceptance
criterion and preserve traceability to the source product, document ID/title,
BRD/PRD type, and relevant sections. Generation remains temporary until a
Product Manager reviews it and performs a separate explicit acceptance action.

The generation profiles are Strictly Grounded, Balanced, and Exploratory, with
Strictly Grounded as the fail-closed default. Retrieval Top-K remains a distinct
retrieval parameter and will not double as a model-generation or profile
control. Profiles may change how the model presents source gaps and proposals,
but they do not weaken Approved-source eligibility, traceability, review,
source-freshness checks, or save-time safety.

A substantive claim is unsupported when its cited Approved source text does not
support the stated requirement, actor, value, date, metric, constraint, outcome,
scope, dependency, relationship, or acceptance condition. Citation presence
alone is insufficient. Unsupported and ambiguous claims, unlabeled exploratory
proposals, missing acceptance criteria, incomplete traceability, stale sources,
and unresolved missing requirements make a review batch non-saveable. Human
revision triggers the same checks. The invariant is enforced at the trusted
acceptance/persistence boundary, not only in Streamlit.

The schema change will be additive. Existing products, BRDs, PRDs, generic
accepted artifacts, citations, and portfolio history remain valid and readable.
Typed accepted Agile artifacts, ordered criteria, hierarchy, generation
metadata, and immutable provenance snapshots will use explicit validated
contracts and transactional persistence. Pending output stays out of accepted
storage, and generated content never modifies a source BRD or PRD.

Saved BRDs and PRDs will gain read-only Word and PDF export. Export preserves
metadata and ordered sections, sanitizes filenames, treats user text as data,
requires no provider/network call, and never changes database state. Native
Google Docs export remains deferred.

The formerly planned Phase 10 final-release checkpoint moves behind the new
implementation, integrated verification, security, documentation, and UAT work.
Checkpoint 6 records requirements and impact only; Checkpoints 7–13 implement
and verify the expansion, and Checkpoint 14 becomes release-candidate
verification and GitHub release preparation.

**Reason:**
- Typed structures and per-item acceptance criteria make generated output useful
  in an Agile planning workflow rather than as undifferentiated draft text.
- Source-scoped provenance and claim-level support checks make grounding
  auditable and prevent citations from becoming a cosmetic safety signal.
- One invariant across all behavior profiles avoids an Exploratory-mode bypass
  of the no-unsupported-content acceptance requirement.
- Separating Top-K from generation behavior keeps retrieval breadth observable
  and prevents one control from having hidden, unrelated effects.
- Additive storage preserves completed Phase 9 and Phase 10 work while enabling
  hierarchy and richer audit data.
- Local read-only Word/PDF export meets the approved portability need without
  adding cloud authorization or Google Docs complexity.

**Alternatives Considered:**
- Reusing the generic generated-artifact text field without typed artifacts,
  hierarchy, or structured acceptance criteria.
- Allowing the selected profile or Top-K value to weaken save-time validation.
- Treating every model-supplied citation as proof that its claim is supported.
- Saving exploratory proposals with warning labels.
- Replacing or destructively migrating existing generated-artifact tables.
- Exporting through a hosted conversion service or implementing Google Docs in
  the same increment.
- Keeping release-candidate preparation as Checkpoint 6 before the approved
  product expansion is implemented and verified.

**Impact:**
Checkpoint 6 changes `PROJECT_SPEC.md`, `IMPLEMENTATION_PLAN.md`, and
`DECISIONS.md` only. Later checkpoints require additive models and schema,
source-scoped retrieval, profile and prompt contracts, structured generation,
claim-support assessment, review and persistence gates, Streamlit workflows,
Word/PDF services and likely minimal export dependencies, expanded offline
evaluation and security tests, documentation updates, packaging review, and a
new final release regression. The existing 252-test baseline and all completed
Checkpoint 1–5 behavior remain mandatory regression gates.

**Status:**
Approved

## Decision 017

**Date:** August 11, 2026

**Category:** Grounded Agile generation and support assessment

**Title:** Checkpoint 9 uses conservative field-level correspondence and keeps all output unsaved

**Decision:**
Checkpoint 9 implements Agile generation as an in-memory workflow over only the
selected product's selected Approved BRD/PRD documents. Ranked chunks are
revalidated immediately before and after the injected structured-provider
boundary. Provider output must match the versioned Checkpoint 8 contract and
the Checkpoint 7 artifact contracts, including valid hierarchy, ordered
criteria, and resolvable artifact-, criterion-, and claim-level references.

Assessable claims are deterministically extracted in artifact order from each
title, description, parent relationship, and acceptance criterion. Stable
claim IDs derive from artifact identity, location, and text. The support
boundary returns the approved supported, unsupported, ambiguous, or
missing-source outcome, with contradiction and uncited or unresolved citations
recorded as reasons. Direct normalized text correspondence is supported;
opposite modal/negation correspondence is contradicted; broad non-contiguous
token correspondence is ambiguous; and weaker correspondence is unsupported.
A citation or isolated keyword match is never sufficient.

This method is deliberately conservative and deterministic for offline testing.
Its records explicitly state that it is not a semantic guarantee. It can
produce false negatives for valid paraphrases, so ambiguous or unsupported
content is preserved as a finding and is never silently rewritten as grounded.
Strictly Grounded and Balanced cannot return proposals; Exploratory may return
only labeled unsupported, non-saveable proposals. Missing requirements and
proposals block the result under every profile.

Checkpoint 9 does not add persistence. Generated candidates, findings, gaps,
and proposals always retain `can_save=False`; Checkpoint 10 will own review,
revision, acceptance-time re-grounding, and any authorized accepted-storage
write.

**Reason:**
- A conservative deterministic boundary is reproducible without an LLM judge
  and does not overstate heuristic text comparison as truth.
- Claim locations and owner-specific citations prevent artifact references from
  automatically proving acceptance criteria.
- Revalidation on both sides of provider execution closes approval, deletion,
  content-change, and cross-scope races during Checkpoint 9 generation.
- Keeping persistence absent preserves the approved Checkpoint 9/10 lifecycle
  boundary.

**Alternatives Considered:**
- Treating citations or keyword overlap as sufficient evidence.
- Asking the generation provider to judge its own support without a separate
  deterministic application boundary.
- Using probabilistic semantic similarity while presenting it as proof.
- Persisting pending generation runs or support findings before Checkpoint 10.
- Allowing Balanced or Exploratory behavior to weaken source eligibility or
  support integrity.

**Impact:**
Three source modules implement generation, support assessment, and offline
evaluation. The source-release allowlist and focused tests expand accordingly.
There is no dependency, schema, database-write, Phase 9 interface, UI, or export
change. Valid paraphrases may remain ambiguous until a later approved method or
human review resolves them.

**Status:**
Approved

## Decision 018

**Date:** August 13, 2026

**Category:** Re-grounded Agile review and acceptance

**Title:** Checkpoint 10 keeps review evidence in memory and repeats every safety gate at acceptance

**Decision:**
Checkpoint 10 adds an immutable in-memory Agile review batch rather than a
pending-review database schema. It preserves the original and current
artifacts, generation request, profile, retrieval Top-K, prompt identity,
selected chunks, claims, assessments, gaps, proposals, structured gates,
versions, reviewer events, timestamps, and rejection reasons. Any changed
artifact or criterion revision increments the review version and reruns the
Checkpoint 9 structural, source, citation, and support boundaries. Unchanged
content is a deterministic no-op.

Acceptance is a distinct reviewer action. It requires the current version and
assessment and every gate to pass under every profile. Sources are revalidated
immediately before saving. The reviewed database entry point then independently
reassesses every artifact and criterion claim and compares full-section digests
inside the existing Checkpoint 7 accepted-batch transaction. Rejection,
unsupported content, gaps, proposals, stale sources, invalid hierarchy,
malformed citations, stale reviews, and failed writes remain entirely outside
accepted storage. Repeated acceptance returns the existing batch without
duplicates.

Checkpoint 10 does not add a schema migration. The existing accepted Agile
tables already provide transactional hierarchy, criterion, provenance,
revision, prompt-version, profile, timestamp, and immutable source-snapshot
storage. Pending, revised, rejected, and detailed gate history remains in the
approved in-memory review boundary until a later explicitly authorized design
requires durable review-session storage.

**Reason:**
- Reassessment prevents edited content from inheriting stale grounding.
- Independent service and database checks close UI/session-state bypasses and
  source changes between review and commit.
- Full-section fingerprints detect source edits beyond the cited substring.
- Reusing the accepted schema avoids persisting unsafe intermediate content or
  introducing an unnecessary migration.

**Alternatives Considered:**
- Reusing generation-time support after Product Manager edits.
- Treating reviewer approval as a substitute for source support.
- Saving pending and rejected sessions in new tables without authorization.
- Checking only citation presence, current document status, or cited substrings.
- Partially saving safe artifacts from an unsafe batch.

**Impact:**
One review service module, full-section retrieval fingerprints, a strengthened
reviewed persistence entry point, focused tests, documentation, and the release
allowlist are added. Existing Product, document, generic Phase 9 acceptance,
Checkpoint 7 persistence, Checkpoint 8 controls, and Checkpoint 9 generation
interfaces remain compatible. There is no UI, export, dependency, live
provider, production-data, or release operation change.

**Status:**
Approved

## Decision 019

**Date:** August 13, 2026

**Category:** Guided workspace, product documents, and Agile review interface

**Title:** Checkpoint 11 uses additive professional templates and a separate measurable PRD Success Matrix

**Decision:**
Checkpoint 11 presents one ordered Product workspace navigation group: Dashboard,
Create Product, Create PRD, Create BRD, AI Assistant, View Products, and Search
Products. The BRD and PRD builders retain every existing stable section key and
add the approved professional outline fields in deterministic group order.
Existing rows are never rewritten during initialization; absent new sections
render blank and are inserted only by an explicit document save.

PRDs additionally own zero or more ordered Success Matrix entries in the
additive `prd_success_matrix_entries` table. Each entry has a stable ID and
position plus requirement/outcome, metric, optional baseline, target, minimum
acceptance threshold, measurement method, data source, evaluation period,
validation owner, and status. Draft entries may be incomplete. Approved PRDs
require at least one entry and every measurable field except baseline. This
matrix remains distinct from user-story acceptance criteria.

The completed Product Manager review keeps hierarchy counts informational and
shows the Success Matrix count separately. PRD Contributors and Roles and Key
Dates and Milestones are repeatable structured pairs with stable IDs and
Draft-tolerant editing. Tracking Strategy and Analytics Events or Telemetry
retain their stable section keys and provide examples as help text only.
Legacy contributor, date, and milestone text remains unchanged and initializes
the structured editor without being overwritten.

Temperature, generation Top-P, GEPA settings, and hallucination flags remain
internal controls. Retrieval Top-K is exposed only in the governed Agile
workflow and never as a PRD field. Grounding quality is authored as a measurable
product outcome. The AI Assistant calls the existing Checkpoints 7–10 generation,
claim-support, review, and accepted-persistence services; revision reassesses,
every failed gate blocks acceptance, and rejected or pending output remains
outside accepted storage.

**Reason:**
- Additive keys and a child table preserve existing document IDs, associations,
  content, and approval states without lossy mapping.
- A structured outcome matrix makes approval criteria measurable without mixing
  product success with story-level acceptance conditions.
- Reusing trusted Agile service boundaries prevents UI logic from weakening
  source, citation, claim, hierarchy, staleness, or transaction gates.

**Alternatives Considered:**
- Replacing or merging old section content into the new outline automatically.
- Storing Success Matrix rows as free-form text or acceptance criteria.
- Exposing model tuning or a hallucination checkbox in the PRD.
- Reimplementing generation and acceptance decisions in `app.py`.

**Impact:**
The document template, validation, model, SQLite, Streamlit, sample-data,
documentation, screenshot, and focused-test surfaces change. The migration is
additive and idempotent. Checkpoint 12 export is not implemented; its future
Word/PDF contract must include the Success Matrix.

**Status:**
Approved

## Decision 020

**Date:** August 13, 2026

**Category:** PRD Agile authoring hierarchy

**Title:** PRDs use the explicit Epic → Capability → Feature → User Story hierarchy

**Decision:**
The PRD builder owns repeatable, ordered Epic, Capability, Feature, and User
Story authoring records. It reuses the shared Agile artifact types and parent
map: Capabilities belong to Epics, Features belong to Capabilities, and User
Stories belong to Features. Functional requirements remain a separate
professional-outline section and are not a hierarchy level.

Every hierarchy entry owns zero or more independently identified and ordered
acceptance criteria. Draft PRDs may keep incomplete entries. Approved PRDs
require every level, valid parents, complete artifact content, and at least one
measurable criterion per entry. Criteria are never copied between levels or
treated as proof for another artifact. Additive child tables initialize empty
for existing PRDs; legacy user-story, functional-requirement, and
acceptance-criteria section text remains unchanged and editable.

The completed Product Manager review also represents BRD Agile content as
repeatable Epic → Capability → Feature → User Story rows with independently
owned acceptance criteria at every level and an eight-field preview table.
Business Risk and Mitigation Strategy use linked repeatable rows and a
two-column preview. One additive, typed-payload document-row table persists
contributors, milestones, BRD hierarchy rows, and BRD risk rows with stable
IDs and deterministic order. Legacy section text is retained as a compatibility
source and is never copied across hierarchy levels.

**Reason:**
- One explicit hierarchy avoids presenting functional requirements as an Agile
  level or peer.
- Shared types and parent rules prevent a conflicting second hierarchy model.
- Independent criteria preserve the distinct validation intent of each level.
- Additive storage preserves existing PRD content and approval state.

**Impact:**
The PRD model, validation, additive SQLite schema, builder, preview, fictional
sample, documentation, and focused tests expand. Accepted generated Agile
artifacts retain their existing Checkpoints 7–10 lifecycle and storage.
Checkpoint 12 export remains unimplemented.

**Status:**
Approved

## Decision 021

**Date:** August 14, 2026

**Category:** Product-document export and local file safety

**Title:** Saved BRDs and PRDs use local in-memory Word and PDF exporters

**Decision:**
Checkpoint 12 exports any saved Draft or Approved BRD or PRD through one shared,
ordered content model. The model preserves product and document metadata,
generated-at time, every stable template section, PRD Contributors and Roles,
Key Dates and Milestones, the explicit PRD Agile hierarchy and independently
owned criteria, the PRD Success Matrix, the BRD Agile hierarchy and criteria,
and linked Business Risk/Mitigation rows. Legacy section text remains available:
legacy-derived structured rows are emitted once, while genuinely distinct
legacy text is labeled as preserved content rather than discarded or silently
duplicated.

Word files are generated directly with `python-docx` using the
`standard_business_brief` design preset and a restrained memo masthead. They use
US Letter pages, explicit margins and style spacing, fixed-width tables,
running status/page furniture, macro-free Open XML, no external template, and
scrubbed personal metadata. PDFs are generated directly with ReportLab using
the same content order, embedded local Unicode font data, repeated table
headers, page-flow handling, and visible status/page furniture. Neither format
uses Microsoft Word, a hosted converter, an OpenAI service, or a network call.

Exports are built entirely in memory and returned to Streamlit download
controls. Deterministic, sanitized filenames contain only a safe product slug,
document type and ID, version slug, and approved extension. User content is
escaped where a renderer accepts markup-like syntax and is otherwise treated
only as document data. Export errors cross the UI as one user-safe message.
The service accepts already-loaded records and has no database write or provider
boundary; source records and schema remain unchanged.

The minimum direct runtime dependency set expands by `python-docx==1.2.0` and
`reportlab==5.0.0`. Both were installed into the project environment and are
included through the existing pinned-requirements and explicit-manifest package
workflow. Native Google Docs export remains deferred.

**Reason:**
- One shared content model prevents Word and PDF section-order drift.
- Direct local renderers avoid cloud authorization, conversion services, and
  Microsoft Word automation.
- In-memory bytes and sanitized filenames eliminate repository or arbitrary
  path writes during a normal download.
- Explicit legacy handling preserves Checkpoint 11 backward compatibility.
- Fixed geometry and render inspection make document quality testable.

**Alternatives Considered:**
- Microsoft Word or LibreOffice as a runtime export dependency.
- A hosted document-conversion API.
- HTML-to-document conversion.
- A single wide table for all Success Matrix or BRD hierarchy fields.
- Temporary repository files or user-controlled output paths.
- Native Google Docs export in Checkpoint 12.

**Impact:**
One export module, two pinned direct dependencies, document-preview download
controls, focused tests, package allowlisting, and documentation are added.
There is no database migration or schema change, no source-document mutation,
no live provider call, and no Checkpoint 13 implementation.

**Status:**
Approved

## Decision 022

**Date:** August 15, 2026

**Category:** Release-candidate verification and publication boundary

**Title:** v1.0.0 uses a verified deterministic local candidate with separate publication approval

**Decision:**
Checkpoint 14 prepares one local v1.0.0 source-release candidate and checksum
outside the repository from the explicit allowlist. Candidate readiness requires
exact version and proposed GitHub metadata, direct dependency/license review,
normalized archive membership/order/timestamps/permissions, byte
reproducibility, checksum agreement, clean extraction, fresh pinned installation,
native macOS launcher and no-key startup, integrated fictional-data workflow and
export UAT, full regression, and data/secret/prohibited-artifact integrity gates.

Native compatibility remains limited to macOS 26.5.2 arm64 with Python 3.14.6,
the only available interpreter and environment completing those gates. Windows
and Python 3.11 through 3.13 remain structural-only evidence. No compatibility
claim may be inferred from declared Python ranges or launcher structure alone.

The candidate ZIP, checksum, extraction, virtual environment, databases,
exports, and render output remain disposable review artifacts outside the
repository. `RELEASE_STATUS` remains `planned`. Creating a Git tag, GitHub
Release, upload, publication, announcement, or external beta requires a later
explicit authorization and is not part of Checkpoint 14.

**Reason:**
- Deterministic source packaging makes the exact review artifact reproducible.
- Fresh installation and no-key startup test the user boundary rather than only
  the development environment.
- Explicit compatibility evidence prevents platform and Python overclaims.
- A separate publication decision keeps verification reversible and reviewable.

**Alternatives Considered:**
- Tagging or publishing immediately after automated tests.
- Claiming every declared Python version or Windows from structural tests.
- Bundling a virtual environment, database, sample database, or generated
  exports in the candidate.
- Recording a candidate-specific checksum inside its own source archive.

**Impact:**
Checkpoint 14 adds focused release-candidate tests, draft v1.0.0 release notes,
and evidence/status documentation. It changes no application runtime, database
schema, dependency, product workflow, grounding boundary, export implementation,
or protected artifact.

**Status:**
Approved
