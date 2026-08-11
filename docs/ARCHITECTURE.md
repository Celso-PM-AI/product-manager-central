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
