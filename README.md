# Product Manager Central

Product Manager Central (PMC) is a focused Streamlit workspace for capturing,
finding, reviewing, editing, and safely deleting structured product information.
The current MVP stores data locally in SQLite and does not connect to an
external AI service.
## Application Preview

![Product Manager Central application](docs/images/pmc-v1 screenshot.png)

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

## Architecture

PMC deliberately uses a small MVP architecture:

- `app.py` contains the single Streamlit application and workflow state.
- `src/models.py` defines the canonical `Product` and field categories.
- `src/validation.py` provides reusable validation and normalization.
- `src/database.py` owns parameterized SQLite initialization, CRUD, search,
  dashboard metrics, and controlled legacy migration.
- `tests/` contains isolated validation, database, presentation-helper, and
  Streamlit workflow tests.
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

## Edit and delete behavior

Editing loads the selected product's current values into the shared canonical
form. Invalid submissions display all discovered errors and do not update the
database. Successful edits preserve the product ID and original creation
timestamp, advance the updated timestamp, and return to the refreshed detail
view.

Deleting requires two distinct actions. The first Delete action only opens a
warning that names the product and ID. The user must then choose Confirm Delete
or Cancel. Cancel does not change the database. A successful confirmation
deletes exactly one ID and returns to the product list.

## Data protection

The following local data is intentionally excluded from Git:

- `data/*.db` and SQLite sidecar files
- `backups/`
- `archive/products.csv`
- `.venv/`
- caches, operating-system files, secrets, and local environment files

Before application phases that could affect persistence behavior, create and
verify a permanent timestamped database backup. Verify SQLite integrity,
record counts, every product value, and checksums before and after the work.

## Development status

Phases 0 through 5 are complete as of July 29, 2026.

Phase 6 has not started. Generative AI integration has not started. External AI
APIs, authentication, RAG, cloud deployment, export functionality, advanced
analytics services, and generated product-management artifacts remain deferred.
