# Product Manager Central Architecture

PMC is a local, single-user Streamlit application. Its architecture keeps
product records and source documents distinct from temporary AI output and
separately accepted generated artifacts. The Checkpoint 7 backend additionally
keeps typed accepted Agile batches separate from the existing generic accepted
artifact history.

## Application and local-data architecture

```mermaid
flowchart LR
    PM[Product Manager] --> UI[Streamlit interface<br/>app.py]
    UI --> CORE[Models and validation<br/>models.py + validation.py]
    CORE --> AGILE[Typed Agile contracts<br/>agile.py]
    AGILE --> PROFILE[Behavior profiles<br/>agile_profiles.py]
    PROFILE --> APROMPT[Structured Agile prompts<br/>agile_prompt_catalog.py]
    APROMPT --> CONTROL[Separated controls<br/>model_controls.py]
    CONTROL --> AGEN[Scoped Agile generation<br/>agile_generation.py]
    AGEN --> CLAIM[Claim support assessment<br/>claim_support.py]
    UI --> DOCS[BRD and PRD templates<br/>document_templates.py]
    UI --> PROMPTS[Approved prompt catalog<br/>prompt_catalog.py]
    CORE --> DB[SQLite persistence<br/>database.py]
    AGILE --> DB
    DOCS --> DB
    DB --> LOCAL[(Local pmc.db)]
    UI --> SEARCH[Product search and metrics]
    SEARCH --> DB
```

The interface owns navigation and transient workflow state. Models and
centralized validation define the product and document contracts. Templates
provide stable BRD/PRD sections and controlled prepopulation. Parameterized
database functions own initialization, migrations, persistence, search,
dashboard metrics, and retrieval-eligible document reads.

## Typed Agile contracts and accepted storage

Checkpoint 7 defines explicit Epic, Capability, Feature, and User Story types.
Each artifact has its own ordered structured acceptance-criterion records,
artifact- and criterion-level source references, optional parent, stable IDs,
review state, provenance, revision, and UTC timestamps. A supplied parent must
follow Epic → Capability → Feature → User Story, exist in the same product batch,
and precede its child. Any artifact type may be an independent root when no
parent is supplied.

The SQLite change is additive. Six `agile_*` tables store accepted generation
runs, typed artifacts, criteria, immutable source-provenance snapshots, and
artifact/criterion source links. The existing `generated_artifacts` and
`generated_artifact_citations` tables are neither rewritten nor reclassified.
Initialization recognizes and transactionally upgrades the exact Phase 9
schema, verifies the five pre-existing table rowsets exactly at the SQL value
level, and is idempotent after upgrade.

Accepted Agile persistence requires an accepted batch and accepted artifacts,
at least one nonblank criterion per artifact, complete product/Approved BRD or
PRD/section traceability, and valid hierarchy. Database checks, unique indexes,
foreign keys, and triggers reject malformed direct writes. Source snapshots do
not reference mutable document rows, so later document edits or deletion do not
rewrite accepted provenance. Deleting the owning product intentionally cascades
through its accepted Agile batches. Pending review remains out of accepted
storage. Profile behavior, generation, support assessment, acceptance workflow,
and UI are not part of Checkpoint 7.

## Agile profiles, prompts, and separated controls

Checkpoint 8 adds three non-persistent contract layers. The profile catalog
defines Strictly Grounded, Balanced, and Exploratory through enums and immutable
policy records, with Strictly Grounded as the fail-closed default. Profile
instructions describe grounding strictness, permitted variation, missing-source
behavior, unsupported-content treatment, citations, assumptions, and inference.
They do not claim that unsupported content has already been detected.

The versioned Agile prompt catalog contains one prompt/task definition for each
artifact type plus structured acceptance criteria. A prompt envelope preserves
separate roles for trusted application instructions, validated application
selections, Product Manager request data, untrusted Approved BRD/PRD source
records, and the output contract. Source text therefore cannot change the
selected prompt, version, profile, artifact type, source scope, or response
schema. Strict response-shape validation covers artifacts, ordered criteria,
claim/source references, missing requirements, and explicitly unsupported,
non-saveable proposals; it does not assess whether claims are supported.

`RetrievalControls.top_k` limits only retrieved Approved-source chunks.
`GenerationControls` has no Top-K field and represents Temperature and Top-P as
separate validated optional controls. Model capabilities decide whether optional
settings are included or whether required unsupported settings fail before an
API request; one control is never substituted for another. Profile behavior
remains the business rule regardless of provider settings.

The [official GPT-5.6 Terra model page](https://developers.openai.com/api/docs/models/gpt-5.6-terra)
documents Responses API and Structured Outputs support. It does not establish
Temperature or Top-P support, so PMC's default capability contract enables only
structured output and omits both sampling controls. No database migration,
provider call, Agile generation, claim-support assessment, or save-workflow
change is part of Checkpoint 8.

## Grounded Agile generation and claim support

Checkpoint 9 adds a separate in-memory workflow in `agile_generation.py`.
Trusted selections are validated before retrieval; only ranked chunks from the
selected product and selected Approved BRD/PRD document scope enter the prompt
envelope. The exact chunks are reloaded and compared before and after provider
execution. The provider is injected, receives the strict response schema and
capability-filtered generation settings, and has no persistence authority.

Structured output is validated before domain construction. Citations resolve
only to context source IDs, preserve deterministic order, and must cover each
artifact title, description, relationship, and acceptance criterion through an
owner-specific claim mapping. Criterion claims use criterion references, so an
artifact-level citation cannot prove them. Malformed output is rejected as one
unit.

`claim_support.py` assigns stable content-derived IDs to field-level claims in
artifact order and returns supported, unsupported, ambiguous, or missing-source
assessments with explicit reasons and evidence IDs. Direct normalized text
correspondence is the only supported result; contradictions, broad
non-contiguous correspondence, absent correspondence, and uncited or unresolved
references remain findings. The method is deterministic and conservative, not
a semantic guarantee. `agile_evaluation.py` reports offline source precision
and recall, artifact/criterion traceability, unsupported-claim recall,
false-positive IDs, missing-requirement recall, and profile conformance.

All Checkpoint 9 outputs remain temporary with `can_save=False`. No generation
run, candidate, assessment, gap, or proposal is written to SQLite. Checkpoint
10 remains responsible for review, revision, acceptance-time revalidation, and
authorized persistence.

The database is local application data. It is never allowlisted into a release
archive, and fictional samples are loaded only after an explicit user action.

## Approved-source generation and acceptance

```mermaid
flowchart TD
    REQUEST[Product, task, prompt, and request] --> VALIDATE[Validate selection and request]
    VALIDATE --> LOAD[Load Approved BRD and PRD sections]
    LOAD --> RANK[Chunk and semantically rank evidence]
    RANK --> RECHECK[Revalidate current source eligibility]
    RECHECK -->|No eligible evidence| EMPTY[No grounded draft]
    RECHECK -->|Eligible evidence| PROVIDER[Optional OpenAI boundary<br/>environment configured]
    PROVIDER --> DRAFT[Temporary generated draft<br/>with citations]
    DRAFT --> REVIEW[Human review]
    REVIEW -->|Reject| DISCARD[Save nothing]
    REVIEW -->|Revise| REVIEW
    REVIEW -->|Accept and save| ACCEPTCHECK[Revalidate cited sources again]
    ACCEPTCHECK -->|Changed, deleted, or Draft| BLOCK[Block persistence]
    ACCEPTCHECK -->|Still Approved| ARTIFACT[(Separate generated-artifact store)]
    SOURCE[(Original BRDs and PRDs)] --> LOAD
    SOURCE -. never automatically modified .-> ARTIFACT
```

Only Approved BRDs and PRDs are eligible for retrieval. Ranked chunks carry
product, document, type, section, and stable-ID metadata into visible citations.
A provider response remains temporary and cannot be saved directly. The Product
Manager reviews the original output, may revise or reject it, and must invoke a
separate acceptance action.

Acceptance rechecks every cited source. If any source is missing, changed, or no
longer Approved, PMC saves nothing. A successful acceptance writes content and
citation snapshots into generated-artifact tables. Original BRDs and PRDs are
never automatically modified.

The OpenAI boundary is optional. Without `OPENAI_API_KEY`, non-AI workflows stay
available and generation stops before client construction or a provider call.
Tests inject deterministic fake or mocked providers instead of making live
calls.

## Source-package boundary

```mermaid
flowchart LR
    MANIFEST[release_manifest.txt<br/>explicit allowlist] --> BUILDER[Deterministic package builder]
    BUILDER --> AUDIT[Exact member and checksum validation]
    AUDIT --> ZIP[Test source ZIP]
    EXCLUDED[Databases, sidecars, backups,<br/>archives, secrets, environment files,<br/>caches, tests, private data] -->|rejected| BUILDER
```

The builder reads one repository-relative path per manifest line. It does not
glob the repository or copy a staging tree. Member order, timestamps,
compression, and permissions are normalized for repeatable output. The builder
validates exact membership, produces a SHA-256 file, refuses accidental
overwrite, and rejects prohibited artifact classes.

This is build capability, not publication authority. An official archive, tag,
GitHub Release, or public posting requires later explicit approval.

## Responsibility map

| Area | Primary source |
|---|---|
| Streamlit navigation and review UI | `app.py` |
| Product and document models | `src/models.py` |
| Typed Agile domain contracts | `src/agile.py` |
| Grounded typed Agile generation | `src/agile_generation.py` |
| Deterministic Agile claim support | `src/claim_support.py` |
| Offline Agile evaluation | `src/agile_evaluation.py` |
| Agile behavior profiles | `src/agile_profiles.py` |
| Versioned structured Agile prompts | `src/agile_prompt_catalog.py` |
| Retrieval/generation control mapping | `src/model_controls.py` |
| Validation and normalization | `src/validation.py` |
| BRD/PRD structure | `src/document_templates.py` |
| SQLite persistence and eligible-source reads | `src/database.py` |
| Provider isolation | `src/ai_service.py` |
| Approved prompt definitions | `src/prompt_catalog.py` |
| Chunking and semantic ranking | `src/semantic_retrieval.py` |
| Grounded prompts and citations | `src/grounded_generation.py` |
| Human review and acceptance | `src/generated_content.py` |
| Offline evaluation | `src/rag_evaluation.py` |
| Deterministic source packaging | `scripts/build_release.py` |
