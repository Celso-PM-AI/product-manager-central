# Product Manager Central

## Product vision

Product Manager Central (PMC) is an AI-assisted workspace that helps product managers create high-quality product documentation, organize product information, and make better product decisions faster.

The initial user is a product manager who needs a structured place to capture product strategy, customer needs, business goals, requirements, roadmaps, and decisions.

## MVP goal

The first MVP establishes dependable product-information management. It prepares a clear foundation for future AI-assisted documentation without connecting to an external AI model.

## MVP capabilities

1. Create a product.
2. Save product information in SQLite.
3. View a list of saved products.
4. Open and view a saved product.
5. Edit an existing product.
6. Permanently delete a product after two-step confirmation.
7. Validate required fields and prevent invalid data.
8. Search saved products.
9. Display simple dashboard metrics.
10. Provide a clean, professional, single-application Streamlit interface.

Duplicate product names are allowed.

## Product fields

### Required

- `name`
- `description`
- `target_users`
- `business_goal`
- `status`

The create form defaults `status` to `discovery`.

### Optional

- `customer_problem`
- `product_strategy`
- `notes`

### System-managed

- `id`
- `created_at`
- `updated_at`

## Approved statuses

- `idea`
- `discovery`
- `planning`
- `in_development`
- `launched`
- `archived`

## Dashboard metrics

- Total products.
- Active products: products whose status is not `archived`.
- Launched products.
- Recently updated products: products updated within the previous 30 days.

Advanced charts are not part of the MVP.

## Technology and architecture

- Python
- Streamlit
- SQLite as the only active data source
- One Streamlit application in `app.py`
- Standard-library SQLite access in `src/database.py`
- Product definitions in `src/models.py`
- Reusable validation in `src/validation.py`
- Validation and database tests in `tests/`
- Isolated Streamlit workflow tests in `tests/`

The MVP deliberately avoids an ORM and additional service, view, configuration, and migration-script layers. These may be introduced later if the application becomes difficult to understand or maintain.

The application accepts an optional `PMC_DATABASE_FILE` environment variable
for isolated tests and disposable manual verification. The default and only
live data source remains `data/pmc.db`.

## Edit workflow

- Edit is available from an opened product detail.
- Every editable field is prepopulated with its current value.
- Create and edit reuse the same field-rendering, validation, and normalization
  behavior.
- Invalid input displays all discovered errors and performs no update.
- Cancel returns to the detail view without changing the database.
- A successful edit preserves `id` and `created_at`, advances `updated_at`, and
  returns to the refreshed detail view.
- Missing records and database failures receive user-safe messages.

## Delete workflow

- Delete is available from an opened product detail.
- The first action only opens a permanent-deletion warning identifying the
  product name and ID.
- Separate Confirm Delete and Cancel actions form the required second step.
- Cancel leaves the product and database unchanged.
- Confirmation deletes exactly one product by ID, prevents automatic repeated
  deletion, displays a result message, and returns to the product list.
- Missing and already-deleted IDs are handled without an unhandled error.

## Data policy

- `data/pmc.db` is the application's source of truth.
- The existing Product Manager Central database record must be preserved.
- The legacy CSV is preserved at `archive/products.csv` but is not imported or used by the application.
- The live database, backups, CSV, virtual environment, caches, and operating-system files must not be committed to Git.
- Deletion in the application is permanent and requires two-step confirmation.

## Deferred features

- External AI integration and AI generators
- AI provider abstractions
- Generated PRDs and other product artifacts
- Advanced analytics and status charts
- Authentication and multi-user permissions
- Cloud deployment
- An ORM
- Automated CSV importing
- A service or separate view layer

## Current development status

Phases 0 through 5 are complete. The application uses the canonical Product
model, centralized validation, and SQLite database layer for dashboard, create,
list, detail, search, edit, and confirmed-delete workflows.

Phase 6 has not started. Generative AI integration, external AI APIs,
authentication, RAG, cloud deployment, export functionality, and other deferred
features have not been started.

Implementation must proceed one approved phase at a time according to `IMPLEMENTATION_PLAN.md`.
