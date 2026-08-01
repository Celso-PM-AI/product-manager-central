# Product Manager Central

## Product purpose and MVP scope

Product Manager Central (PMC) is a local Streamlit workspace for product
managers to capture, find, review, update, and safely delete structured product
information and to author template-guided product documents. SQLite remains the
single local data source. Phase 8 uses deterministic BRD and PRD templates; it
does not create or integrate an LLM, call an AI API, or require API tokens.

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

- Document creation begins from an existing product detail.
- The user chooses BRD or PRD and receives template-specific guided sections.
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
  parameterized product/document persistence, metrics, the controlled
  known-legacy migration, and the additive Phase 8 migration.
- `tests/` contains temporary-database model, validation, persistence,
  presentation-helper, and Streamlit workflow tests.
- `requirements.txt` contains the Streamlit and pandas runtime dependencies.

The application accepts `PMC_DATABASE_FILE` for isolated automated or manual
verification. Without it, the only live data source is `data/pmc.db`.

Documents use normalized `documents` and `document_sections` tables. Foreign
keys are enforced, product deletion cascades to associated documents, and an
index supports product document listings. The application deliberately has no
ORM, service layer, separate view layer, general schema framework, multipage
architecture, charts, or advanced styling framework.

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

- Generative AI, external LLM APIs, RAG, and prompt management
- AI-generated content and Word/PDF document export
- Authentication, multi-user permissions, and cloud deployment
- Analytics integrations, charts, and advanced styling frameworks
- ORM, service-layer, separate view-layer, or general migration frameworks
- Automated CSV importing

## Current development status

Phases 0 through 7 are complete. Phase 8 adds the deterministic Product
Document Builder while preserving the established product workflows. Phase 8
does not use an LLM, AI API, token, authentication, cloud deployment, or export
facility.
