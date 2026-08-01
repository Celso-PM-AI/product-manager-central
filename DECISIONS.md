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
