# Product Manager Central

Product Manager Central (PMC) is a focused Streamlit workspace for capturing,
finding, reviewing, editing, and safely deleting structured product information.
The current MVP stores data locally in SQLite and does not connect to an
external AI service.

## MVP scope

The MVP provides dependable local product-information management for a single
user. It covers structured product records, validation, search, lifecycle
status, dashboard counts, and safe edit/delete workflows in one Streamlit
application. It does not generate product artifacts or call an AI service.

## Application Preview

![Product Manager Central application](docs/images/pmc-v1-screenshot.png)

## Current capabilities

- Dashboard metrics for total, active, launched, and recently updated products.
- Canonical creation form with required and optional product context.
- Compact product list and complete product detail views.
- Case-insensitive search across all approved text fields.
- Prepopulated editing of every appropriate product field.
- Centralized validation and normalization for both create and edit.
- Permanent ID-based deletion with an explicit two-step confirmation.
- Persistent local SQLite storage.

Duplicate product names are allowed. Updates and deletion always target the
product ID rather than its name.

## Dashboard metrics

The dashboard provides four portfolio counts:

- Total products includes every saved product.
- Active products includes every product whose status is not `archived`.
- Launched products includes products whose status is `launched`.
- Updated in the last 30 days includes products whose `updated_at` value is
  exactly at or later than the 30-day cutoff.

The dashboard intentionally contains no charts or advanced analytics.

## Product fields

Required fields:

- Name
- Description
- Target users
- Business goal
- Status

Optional fields:

- Customer problem
- Product strategy
- Notes

System-managed fields:

- ID
- Created timestamp
- Updated timestamp

Approved statuses are `idea`, `discovery`, `planning`, `in_development`,
`launched`, and `archived`. New products default to `discovery`.

## Validation rules

All editable text is trimmed at its outer edges while internal paragraphs and
line breaks are preserved. Required values cannot be empty or whitespace-only.
Blank optional fields are stored as `NULL`.

| Field | Requirement | Maximum length |
| --- | --- | ---: |
| Name | Required | 120 |
| Description | Required | 2,000 |
| Target users | Required | 1,000 |
| Business goal | Required | 2,000 |
| Status | Required; approved value only | — |
| Customer problem | Optional | 2,000 |
| Product strategy | Optional | 3,000 |
| Notes | Optional | 5,000 |

ID and timestamps are system-managed and cannot be supplied through product
forms. Validation reports all discovered field errors together.

## Architecture

PMC deliberately uses a small MVP architecture:

- `app.py` contains the single Streamlit application and workflow state.
- `src/models.py` defines the canonical `Product` and field categories.
- `src/validation.py` provides reusable validation and normalization.
- `src/database.py` owns parameterized SQLite initialization, CRUD, search,
  dashboard metrics, and controlled legacy migration.
- `tests/` contains isolated validation, database, presentation-helper, and
  Streamlit workflow tests.
- `requirements.txt` lists the Streamlit and pandas runtime dependencies.
- `data/pmc.db` is the only live application data source.

Database operations remain outside the Streamlit view code. No ORM, service
layer, separate view layer, or schema framework is used.

## Setup

Create and activate a virtual environment, then install the runtime
dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run the application:

```bash
streamlit run app.py
```

The application uses `data/pmc.db` by default. For isolated development or
manual testing, point the application at a disposable database:

```bash
PMC_DATABASE_FILE=/tmp/pmc-test.db streamlit run app.py
```

Never use the live Product Manager Central record for destructive testing.

## Tests

Run the complete suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

All automated tests use temporary databases. They do not read from or write to
`data/pmc.db`.

## Product workflows

Creating a product uses every approved editable field, defaults status to
`discovery`, validates the complete submission, and saves one canonical record.

View Products lists name, readable status, a compact target-user summary, and
updated time. Selecting a product by ID opens every stored field and both
system-managed timestamps. Search is case-insensitive across all approved text
fields; an empty query returns the complete list.

Editing loads the selected product's current values into the shared canonical
form. Invalid submissions display all discovered errors and do not update the
database. Successful edits preserve the product ID and original creation
timestamp, advance the updated timestamp, and return to the refreshed detail
view.

Deleting requires two distinct actions. The first Delete action only opens a
warning that names the product and ID. The user must then choose Delete
permanently or Cancel. Cancel does not change the database. A successful
confirmation deletes exactly one ID and returns to the product list.

The interface uses readable status labels, guided empty states, consistent
user-safe messages, and full-width detail sections so long product context
remains readable.

## Data protection

The following local data is intentionally excluded from Git:

- `data/*.db` and SQLite sidecar files
- disposable `*.db` files and their sidecars outside `data/`
- `backups/`
- `archive/products.csv`
- `pasted-text.txt`
- `.venv/`
- Python, test, and tool caches
- operating-system files
- `.env` and other secret-bearing environment files

Before application phases that could affect persistence behavior, create and
verify a permanent timestamped database backup. Verify SQLite integrity,
record counts, every product value, and checksums before and after the work.

Disposable manual testing must set `PMC_DATABASE_FILE` to a temporary database.
Disposable products must never be created in `data/pmc.db`, and permanent
backups and `archive/products.csv` must remain unchanged.

## Deferred features

- Generative AI, external LLM APIs, RAG, and prompt management
- Generated product-management artifacts and export functionality
- Authentication, multi-user permissions, and cloud deployment
- Analytics integrations, charts, and advanced styling frameworks
- ORM, service-layer, separate view-layer, or general migration frameworks

## Development status

Phases 0 through 7 are complete as of July 30, 2026. The final MVP acceptance
criteria passed with 103 automated tests and a complete disposable-database
workflow and restart walkthrough.

The Product Manager Central MVP is complete and awaiting approval to commit and
push the Phase 7 documentation and Git-safety changes. All deferred features
remain unstarted.
