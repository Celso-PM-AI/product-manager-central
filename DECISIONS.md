# Product Manager Central
## Architecture & Product Decisions
- DEC-001 SQLite Database
- DEC-002 Archive CSV
- DEC-003 Simplified Architecture
- DEC-004 AI Deferred Until MVP

This document records significant product, architecture, and technical decisions made during the development of Product Manager Central (PMC).

---

## Decisions

- DEC-001 SQLite Database
- DEC-002 Archive CSV
- DEC-003 Simplified Architecture
- DEC-004 AI Deferred Until MVP

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
