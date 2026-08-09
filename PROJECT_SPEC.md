# Product Manager Central

## Product purpose and MVP scope

Product Manager Central (PMC) is a local Streamlit workspace for product
managers to capture, find, review, update, and safely delete structured product
information and to author template-guided product documents. SQLite remains the
single local data source. Phase 9 Checkpoints 1 through 4 add an optional OpenAI
configuration/client boundary, embedding-based semantic retrieval of Approved
BRD/PRD chunks, grounded draft generation with citations, and explicit human
review with separate accepted-artifact persistence.

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
- Export and document deletion controls are not included in Phase 8.

Document title is limited to 200 characters, version to 50 characters, and
each long-form section to 10,000 characters. Version is nonblank free text.
Document types are `BRD` and `PRD`; statuses are `draft` and `approved` in
storage and appear as Draft and Approved in the interface.

### Phase 9 Checkpoints 1 through 4 AI Assistant

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
- `tests/` contains temporary-database model, validation, persistence,
  presentation-helper, and Streamlit workflow tests.
- `requirements.txt` contains the Streamlit, pandas, and official OpenAI Python
  SDK runtime dependencies.

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

## Deferred features

- Prompt management and RAG evaluation
- AI-generated document updates and automatic modification of source BRDs/PRDs
- Word/PDF document export
- Authentication, multi-user permissions, and cloud deployment
- Analytics integrations, charts, and advanced styling frameworks
- ORM, service-layer, separate view-layer, or general migration frameworks
- Automated CSV importing

## Current development status

Phases 0 through 8 and Phase 9 Checkpoints 1 through 4 are complete. Secure
OpenAI boundaries, stable approved-source retrieval, and temporary grounded
draft generation with citations, explicit human review, and separate accepted
artifact persistence are implemented. Checkpoints 5 and 6 are not started;
there is no prompt management, workflow hardening, or RAG evaluation.
