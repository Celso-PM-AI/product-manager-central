# Revised Product Manager Central MVP Implementation Plan

## Plan conventions

- `src/**init**.py` is interpreted as the standard Python package file `src/__init__.py`.
- SQLite is the only active application data source.
- “Active products” means every product whose status is not `archived`.
- “Recently updated” means updated within the previous 30 days.
- The existing legacy creation timestamp will be preserved exactly during migration rather than reinterpreted as a timezone.
- New timestamps will use one consistent format. UTC ISO 8601 is recommended.
- Automated tests will use Python’s standard `unittest` and temporary databases, avoiding `requirements-dev.txt` and `conftest.py`.

## Current phase status

**Updated:** August 9, 2026

- Phases 0 through 8 and all six Phase 9 checkpoints are complete.
- The Product Manager Central MVP acceptance criteria passed.
- Secure OpenAI configuration/client, approved-source boundaries, embeddings,
  semantic retrieval, and temporary grounded draft generation are implemented;
  human-reviewed acceptance, separate generated-artifact saving, and
  deterministic offline release evaluation are complete.

The dashboard originally listed under the planned Phase 6 scope was delivered
during Phase 4. Phase 6 completed its required coverage and interface-polish
work without expanding the product scope.

## Final MVP structure

```text
product-manager-central/
├── app.py
├── PROJECT_SPEC.md
├── README.md
├── requirements.txt
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── database.py
│   ├── models.py
│   └── validation.py
├── tests/
│   ├── test_validation.py
│   └── test_database.py
├── data/
│   └── pmc.db
└── archive/
    └── products.csv
```

Malformed file-named directories will first be preserved under an archive location. They will not be permanently deleted during restructuring.

# Phase 0: Protect existing data

## 1. Purpose

Create a verified recovery point before changing the project structure, application, or database schema.

This phase makes no application changes and does not migrate the database.

## 2. Files created or changed

Application and source files changed: none.

Future backup artifacts:

- A timestamped backup of `data/pmc.db`.
- A record of the backup verification.
- `products.csv` remains in its current location during this phase.

The backup must be stored in a location that will later be excluded by `.gitignore`.

## 3. Exact expected result

- Streamlit is stopped before backup work begins.
- The original `data/pmc.db` remains unchanged.
- A consistent, timestamped SQLite backup exists.
- SQLite integrity checks pass for both the original and backup.
- The backup contains the existing `Product Manager Central` record.
- Original and backup row counts match.
- `products.csv` remains unchanged and is not imported.
- No source code or project behavior changes.

The baseline should record:

- Database filename and size.
- Integrity-check result.
- Product count.
- Existing product ID and name.
- Database checksum.
- CSV checksum.

## 4. Manual tests

- Confirm the Streamlit process is stopped.
- Confirm the original database still exists.
- Open the backup in read-only mode.
- Confirm the backup contains the `Product Manager Central` product.
- Compare the original and backup product counts.
- Confirm `products.csv` still exists and still contains its original record.
- Confirm the application files have not changed.

## 5. Automated tests

Not applicable. This is a data-protection and verification phase.

SQLite integrity and row-count checks are operational checks, not application tests.

## 6. Approval checkpoint

Before Phase 1:

- Review the backup location and timestamp.
- Review the integrity results and product count.
- Confirm that the existing product is recoverable.
- Confirm that `products.csv` is preserved.

No restructuring begins until this checkpoint is approved.

# Phase 1: Repair the project structure

## 1. Purpose

Correct malformed directories, establish valid Python and test-file locations, protect generated data from Git, and align documentation with the approved MVP.

Application behavior must remain unchanged.

## 2. Files created or changed

Create or correct:

- `README.md`
- `.gitignore`
- `PROJECT_SPEC.md`
- `src/__init__.py`
- `src/models.py`
- `src/validation.py`
- `tests/test_validation.py`
- `tests/test_database.py`
- `archive/`

Preserve malformed directories before replacing them:

- Existing `README.md` directory.
- Existing `src/_init_.py` directory.
- Existing `src/models.py` directory.
- Existing `src/validation.py` directory.
- Existing `src/generators.py` directory.
- Existing `tests/test_validation.py` directory.

After the Phase 0 backup is verified:

- Move `data/products.csv` to `archive/products.csv`.
- Do not import, edit, or delete it.
- Ensure `archive/products.csv` is excluded from Git.

The premature `generators.py` placeholder will be archived and will not be recreated for the MVP.

## 3. Exact expected result

- Every intended `.py` path is a real file rather than a directory.
- `src/__init__.py` has the correct standard spelling.
- `products.csv` is preserved at `archive/products.csv`.
- The SQLite application continues to use only `data/pmc.db`.
- Existing create/list behavior remains operational.
- Documentation describes the approved MVP fields, statuses, phases, and limitations.
- `.gitignore` excludes at minimum:
  - `.venv/`
  - `__pycache__/`
  - `*.pyc`
  - `.DS_Store`
  - `data/*.db`
  - SQLite `-wal` and `-shm` files
  - Backup directories and database backups
  - `archive/products.csv`
  - Test and tool caches
- Git is not initialized yet.
- No malformed directory is permanently deleted.

## 4. Manual tests

- Inspect the project tree and confirm all intended Python paths are files.
- Confirm malformed placeholders remain preserved in an archive location.
- Confirm `archive/products.csv` exists and has unchanged content.
- Confirm `data/products.csv` is no longer treated as an active data source.
- Launch the existing application.
- Create a temporary test product only if explicitly approved for the live database; otherwise verify the existing list display without creating data.
- Confirm the existing `Product Manager Central` record is still displayed.
- Confirm the application still uses SQLite.

## 5. Automated tests

No functional automated tests are required yet.

A basic test-discovery check may confirm that the test files are discoverable, even if they do not contain substantive tests yet.

## 6. Approval checkpoint

Before Phase 2:

- Review the repaired project tree.
- Review `.gitignore`.
- Review the updated README and specification.
- Confirm the CSV was preserved after the verified backup.
- Confirm application behavior and database contents did not change.

# Phase 2: Create the product model and centralized validation

## 1. Purpose

Define product data consistently and move validation rules into reusable, testable functions.

The Streamlit application does not need to use the new validation module yet. The database schema remains unchanged.

## 2. Files created or changed

- `src/models.py`
- `src/validation.py`
- `tests/test_validation.py`

No changes to:

- `data/pmc.db`
- Database schema
- CSV data
- Streamlit workflows

## 3. Exact expected result

### Product model

`models.py` defines:

- The `Product` data structure.
- Approved product statuses.
- A stable way to distinguish required, optional, and system-managed fields.

Approved statuses:

- `idea`
- `discovery`
- `planning`
- `in_development`
- `launched`
- `archived`

### Validation and normalization

`validation.py` validates and normalizes:

| Field | Rule |
|---|---|
| `name` | Required, trimmed, maximum 120 characters |
| `description` | Required, trimmed, maximum 2,000 characters |
| `target_users` | Required, trimmed, maximum 1,000 characters |
| `business_goal` | Required, trimmed, maximum 2,000 characters |
| `status` | Required and must be an approved value |
| `customer_problem` | Optional, maximum 2,000 characters |
| `product_strategy` | Optional, maximum 3,000 characters |
| `notes` | Optional, maximum 5,000 characters |

Additional rules:

- Whitespace-only required values are invalid.
- Blank optional values normalize to `None`.
- Leading and trailing whitespace is removed.
- Internal paragraphs and line breaks are preserved.
- Status defaults to `discovery` at the UI boundary.
- System-managed fields cannot be supplied as editable form fields.
- Validation returns all relevant errors together rather than stopping after the first error.

## 4. Manual tests

Review validation behavior using representative examples:

- Complete valid product.
- Blank required fields.
- Required fields containing only spaces.
- Optional fields left blank.
- Valid Unicode, bullets, emoji, and multiline text.
- Invalid status.
- Values at their maximum lengths.
- Values one character over their maximum lengths.
- Leading and trailing whitespace.

Confirm that Phase 2 does not change the database or application behavior.

## 5. Automated tests

`tests/test_validation.py` should cover:

- Every required field individually.
- All required fields missing together.
- Whitespace-only values.
- Trimming and normalization.
- Optional blank-to-`None` conversion.
- Every approved status.
- Invalid and incorrectly cased status values.
- Maximum-length boundaries.
- Over-limit values.
- Unicode and multiline content.
- Preservation of internal spacing and line breaks.
- Absence of database or Streamlit dependencies in validation tests.

## 6. Approval checkpoint

Before Phase 3:

- Review the Product model.
- Review every validation rule and maximum length.
- Review automated test results.
- Confirm that the live database schema remains unchanged.
- Confirm that no Streamlit workflow has changed.

# Phase 3: Update the SQLite database layer

## 1. Purpose

Expand SQLite from create/list storage into a safe, tested CRUD and search layer while preserving the existing database record.

All schema and database operations must first be tested against temporary databases and a copy of the existing database.

## 2. Files created or changed

- `src/database.py`
- `tests/test_database.py`

Eventually, after a separate approval within this phase:

- `data/pmc.db` schema

No migration script or schema framework will be added.

## 3. Exact expected result

### Database operations

`database.py` provides small, clearly named operations for:

- Initialize an empty database.
- Create a product.
- List products.
- Retrieve one product by ID.
- Update a product.
- Delete a product by ID.
- Search products.
- Retrieve simple dashboard metrics.

All queries use parameters for user-controlled values.

Database functions accept a database path so tests can use temporary databases without touching `data/pmc.db`.

### Target schema

The resulting `products` table contains:

- `id`
- `name`
- `description`
- `target_users`
- `business_goal`
- `status`
- `customer_problem`
- `product_strategy`
- `notes`
- `created_at`
- `updated_at`

Database constraints should reinforce:

- Required text values.
- Approved status values.
- Non-null timestamps.

Duplicate names remain allowed.

### Controlled legacy migration

The migration logic remains limited to recognizing the one known legacy schema. It is not a general schema-version framework.

On a legacy database copy, it should:

1. Begin one transaction.
2. Create the approved replacement schema.
3. Copy the existing record with this mapping:

| Legacy field | MVP field |
|---|---|
| `product_name` | `name` |
| `product_idea` | `description` |
| `target_user` | `target_users` |
| `business_goal` | `business_goal` |
| `date_created` | `created_at` |
| none | `status = discovery` |
| none | Optional fields set to `NULL` |
| none | `updated_at = created_at` |

4. Preserve the existing product ID.
5. Preserve the legacy timestamp text exactly.
6. Verify the copied row count.
7. Replace the old table only if every step succeeds.
8. Roll back completely on failure.

Newly created and updated records use consistent UTC timestamps.

### Compatibility during the phase

Until Phase 4 updates the Streamlit application, the database layer should preserve the current create/list behavior where practical. Existing four-field creation can assign `discovery` as the default status.

## 4. Manual tests

Against an empty temporary database:

- Initialize the database.
- Initialize it again.
- Create a product.
- List products.
- Open one product.
- Update it.
- Search for it.
- Delete it.
- Confirm it no longer exists.

Against a copy of the legacy database:

- Confirm the copy initially contains the existing product.
- Run the proposed migration against the copy.
- Confirm the product ID and content are preserved.
- Confirm status is `discovery`.
- Confirm optional fields are empty.
- Confirm both timestamps exist.
- Confirm the database integrity check passes.
- Confirm migration failure would leave the legacy table intact.
- Confirm repeating initialization does not duplicate the record.

The live database must remain untouched during these tests.

## 5. Automated tests

`tests/test_database.py` should use a new temporary database for each test or test group.

Tests should cover:

- Empty-database initialization.
- Repeated initialization.
- Create and retrieve.
- List ordering.
- Retrieve missing ID.
- Update all editable fields.
- Preserve `created_at` during update.
- Change `updated_at` during update.
- Delete existing product.
- Delete missing product.
- Duplicate product names.
- Search by:
  - Name.
  - Description.
  - Target users.
  - Business goal.
  - Optional fields.
- Case-insensitive search.
- Empty search.
- Search containing apostrophes.
- Search containing `%` and `_`.
- Valid status storage.
- Invalid status rejection.
- Required-value constraint rejection.
- Dashboard metric calculations.
- Empty-database metrics.
- Legacy-schema migration using a synthetic legacy database.
- Rollback behavior for a failed operation.

## 6. Approval checkpoint

This phase has two approvals.

### Dry-run approval

Before touching `data/pmc.db`:

- Review all automated test results.
- Review the migrated database-copy results.
- Compare the copied legacy record before and after migration.
- Confirm integrity and row counts.

### Live-migration approval

Only after dry-run approval:

- Stop Streamlit.
- Confirm the Phase 0 backup again.
- Apply the tested migration to the live database.
- Recheck integrity and the existing product.
- Confirm no CSV interaction occurred.

Phase 4 cannot begin until the live migration result is reviewed and approved.

# Phase 4: Build create, list, open, and search workflows

## 1. Purpose

Create the primary user experience for adding, finding, and viewing products in one Streamlit application.

## 2. Files created or changed

- `app.py`
- Potential adjustments to:
  - `src/database.py`
  - `src/models.py`
  - `src/validation.py`
  - Related tests

No new UI modules or multipage structure will be introduced.

## 3. Exact expected result

The single Streamlit application has sidebar navigation for:

- Dashboard
- Products
- Create Product

### Create Product

- Uses all approved fields.
- Clearly identifies required and optional fields.
- Defaults status to `discovery`.
- Uses centralized validation.
- Preserves entered values after validation failure.
- Creates exactly one product after valid submission.
- Shows a success message and a route to the saved product.

### Products list

- Shows saved products in a compact, readable format.
- Includes name, status, target-user summary, and updated date.
- Provides an Open action for each result.
- Does not display every long-text field in the list.

### Product detail

- Displays all populated product fields.
- Displays created and updated timestamps.
- Shows optional fields gracefully when empty.
- Provides Edit and Delete actions for Phase 5.

### Search

- Searches approved text fields.
- Is case-insensitive.
- Shows the result count.
- Clearing the search restores the full product list.
- Does not execute unsafe SQL.

## 4. Manual tests

Create workflow:

- Create a complete valid product.
- Confirm the default status is `discovery`.
- Create a product with all optional fields blank.
- Create a product with all optional fields populated.
- Submit missing required fields.
- Submit whitespace-only fields.
- Submit over-limit fields.
- Confirm invalid submission creates no row.
- Create two products with the same name.

List and detail:

- Confirm the existing migrated product is listed.
- Open every product.
- Confirm displayed details match stored values.
- Confirm empty optional fields are handled cleanly.
- Confirm long and multiline content remains readable.

Search:

- Search by each supported field.
- Search using different letter casing.
- Search using an apostrophe.
- Search using `%` and `_`.
- Search for text that has no matches.
- Clear the search.
- Confirm the full list returns.

Persistence:

- Restart Streamlit.
- Confirm products remain available.

## 5. Automated tests

Existing validation and database tests remain the primary automated coverage.

Add or adjust tests if UI implementation exposes new normalization or database edge cases. Streamlit UI automation is deferred; workflows are manually tested.

## 6. Approval checkpoint

Before Phase 5:

- Demonstrate create, list, open, and search.
- Review the form labels and field order.
- Confirm duplicate names work.
- Confirm the legacy product remains intact.
- Confirm invalid input creates no data.
- Confirm the interface remains understandable without service or view layers.

## Phase 4 completion record

**Completed:** July 28, 2026

The prototype behavior was documented before editing: one page displayed four
legacy-labeled inputs, a create button with inline duplicate validation, and a
full saved-products dataframe. It had no navigation, canonical optional fields,
status selection, dashboard, detail view, or search.

The completed Phase 4 application provides:

- Sidebar navigation for Dashboard, Create Product, View Products, and Search
  Products.
- The four available dashboard metrics.
- Canonical creation fields with `discovery` as the default status.
- Centralized validation with all errors displayed and no invalid save.
- Compact product lists and ID-based complete product details.
- Case-insensitive search through the existing parameterized database API.
- User-safe database errors with no direct SQLite operations in `app.py`.

A permanent pre-change backup was created at
`backups/phase4/pmc-20260728T120247Z.db` and verified as canonical with a
successful integrity check, one preserved row, and the original ID 1 values.
Edit and delete controls remain deferred to Phase 5; no Phase 5 implementation
or generative AI work was started.

# Phase 5: Build edit and delete workflows

## 1. Purpose

Complete product management by allowing controlled updates and permanent deletion.

## 2. Files created or changed

- `app.py`
- `src/database.py`, only if an operation needs correction
- `src/validation.py`, only if edit testing finds a validation gap
- `tests/test_database.py`
- `tests/test_validation.py`, where applicable

## 3. Exact expected result

### Edit

- User opens an existing product.
- Edit form is prepopulated.
- The create and edit forms reuse the same field-rendering logic where practical.
- The same centralized validation applies.
- Cancel returns to the detail view without saving.
- Successful edit:
  - Updates all intended fields.
  - Preserves `id`.
  - Preserves `created_at`.
  - Advances `updated_at`.
  - Returns to the refreshed detail view.

### Delete

Deletion uses two distinct actions:

1. User selects Delete.
2. Streamlit displays:
   - Product name.
   - Permanent-deletion warning.
   - Cancel action.
   - Final “Delete permanently” action.

No deletion occurs on the first action.

After confirmation:

- Exactly one intended product is deleted.
- User returns to the product list.
- A clear success message appears.
- Canceling or navigating away does not delete anything.

## 4. Manual tests

Edit:

- Edit each field individually.
- Edit all fields together.
- Change the status.
- Clear optional fields.
- Attempt to clear a required field.
- Attempt an over-limit edit.
- Cancel a valid edit.
- Confirm `created_at` is unchanged.
- Confirm `updated_at` changes.
- Restart Streamlit and verify persistence.

Delete:

- Select Delete and then Cancel.
- Confirm the product still exists.
- Select Delete and confirm permanently.
- Confirm only the intended product was removed.
- Attempt to open a product that was already deleted.
- Confirm a missing product produces a useful message.
- Confirm duplicate-name products are deleted by ID, not by name.
- Confirm the existing Product Manager Central record is not used for deletion testing unless explicitly approved.

## 5. Automated tests

Database tests should verify:

- Valid updates.
- Invalid update status.
- Missing update ID.
- Timestamp behavior.
- Delete existing ID.
- Delete missing ID.
- Duplicate names do not affect ID-based update or deletion.
- Deleting one duplicate leaves the other unchanged.
- Search and metrics reflect edits and deletions.

## 6. Approval checkpoint

Before Phase 6:

- Demonstrate a successful edit.
- Demonstrate a canceled edit.
- Demonstrate canceled deletion.
- Demonstrate confirmed deletion using a disposable test product.
- Review confirmation wording.
- Confirm ID-based operations protect duplicate-name records.
- Confirm the preserved product and backup remain available.

## Phase 5 completion record

**Completed:** July 29, 2026

The completed Phase 5 application provides:

- Edit and Delete actions from each ID-based product detail.
- One reusable canonical field renderer for create and edit.
- Prepopulated editing of every editable field.
- Centralized validation with all errors displayed and no invalid database
  update.
- Successful edits that preserve `id` and `created_at`, advance `updated_at`,
  display confirmation, and return to the refreshed detail.
- Explicit two-step permanent deletion that identifies the product name and ID.
- Separate Delete permanently and Cancel actions.
- Safe handling for missing, already-deleted, and database-error cases.
- Widget-safe session cleanup, success messages, and return navigation after
  deletion.

A permanent pre-change backup was created at
`backups/phase5/pmc-pre-phase5-20260729T164045Z.db`. The live original and
backup both had SHA-256
`7577ddf8dc7db112a295ab862102c4e89e2485b21b8a274969dedeffbdd9f049`.
Both passed SQLite integrity checks, contained one canonical product record,
and produced the matching complete-rowset SHA-256
`2b77fbbfcb5fe4914897cacf6d5f1784dd426ade8af5a1beb61e12f2601825c1`.
The Product Manager Central record retained ID 1 and every field value.

The complete automated suite passed 97 tests. Coverage includes all editable
fields, validation immutability, system-field timestamp behavior, successful
and repeated deletion, cancellation, missing records, database failures, and
Phase 4 dashboard/create/list/detail/search regressions.

A separate disposable-database Streamlit walkthrough passed 10 checks for edit
prepopulation, invalid edit behavior, successful edit, search, first-step
delete safety, canceled deletion, confirmed deletion, missing/repeated deletion,
navigation, and persistence in a fresh session. The temporary Streamlit server
was then stopped, restarted against the same temporary database, and returned a
healthy status with the expected remaining record.

No live product was edited or deleted. No schema migration was needed.
`src/database.py`, `src/models.py`, and `src/validation.py` required no Phase 5
application changes.

Phase 6 was not started. Generative AI, authentication, RAG, cloud deployment,
export functionality, new product artifacts, and unrelated architecture work
were not started.

# Phase 6: Add simple dashboard metrics and polish

## 1. Purpose

Provide a useful overview of saved products and apply consistent, professional Streamlit presentation without introducing advanced analytics.

## 2. Files created or changed

- `app.py`
- `src/database.py`
- `tests/test_database.py`
- `README.md` or `PROJECT_SPEC.md` if metric definitions need clarification

## 3. Exact expected result

Dashboard displays four metrics:

- **Total products:** All products.
- **Active products:** Products whose status is not `archived`.
- **Launched products:** Products whose status is `launched`.
- **Recently updated products:** Products updated within the previous 30 days.

No charts are included.

Polish includes:

- Consistent headings and spacing.
- Clear primary and secondary actions.
- Readable status labels.
- Friendly empty states.
- Consistent success, warning, validation, and database-error messages.
- Sensible display of long text.
- No advanced styling framework.
- No AI, authentication, cloud, or analytics integrations.

## 4. Manual tests

Dashboard:

- Compare each metric to known database records.
- Test with no products.
- Test with only archived products.
- Test with one launched product.
- Test with active and archived products.
- Test the 30-day recent-update boundary.
- Confirm edits affect the recent-update metric.
- Confirm deletions update metrics immediately.

Interface:

- Review Dashboard, Products, Create, Detail, and Edit screens.
- Confirm navigation does not unexpectedly lose important form state.
- Confirm empty states provide a next action.
- Confirm long content remains readable.
- Confirm user-safe errors do not expose raw SQL.

## 5. Automated tests

Database metric tests should cover:

- Zero products.
- Total count.
- Active count excluding only `archived`.
- Launched count.
- Recently updated count.
- Records exactly on either side of the 30-day boundary.
- Counts after create, edit, status change, and delete.

## 6. Approval checkpoint

Before Phase 7:

- Review and approve metric definitions and values.
- Review every primary workflow for consistency.
- Confirm no chart or advanced analytics work was added.
- Confirm `app.py` remains understandable at its current size.
- Decide whether any UI concern is important enough to fix before final testing.

## Phase 6 completion record

**Completed:** July 30, 2026

The completed Phase 6 application provides:

- Four native Streamlit dashboard metrics for total, active, launched, and
  products updated within the last 30 days.
- An inclusive 30-day boundary: a product updated exactly at the cutoff counts
  as recently updated.
- Clear primary and secondary action labels, including an explicit
  `Delete permanently` confirmation.
- Readable title-cased status labels.
- Guided empty states for the dashboard, product list, and search results.
- Consistent user-safe success, warning, validation, and database-error
  messages.
- Full-width product detail fields and compact list summaries for sensible
  long-text presentation.

The complete automated suite passed 103 tests. Phase 6 coverage includes zero,
total, active, archived, launched, mixed-status, recently updated, exact
30-day-boundary, create, edit, status-change, delete, empty-state, action-label,
and long-text cases. Every automated test used a temporary database.

A separate disposable-database Streamlit walkthrough passed empty dashboard,
create, edit, launched status, archived status, two-step delete, and immediate
metric-refresh checks. Its temporary product and database were removed during
cleanup.

The live Product Manager Central record was not edited or deleted. The database
schema and persistence implementation did not change. No charts, advanced
styling framework, AI integration, external LLM, authentication, analytics,
deployment, or Phase 7 functionality were added.

# Phase 7: Final testing, documentation, and Git safety verification

## 1. Purpose

Verify the entire MVP, finalize beginner-friendly documentation, and confirm
that the existing Git repository safely excludes generated, private, preserved,
and disposable data.

## 2. Files created or changed

- `README.md`
- `PROJECT_SPEC.md`
- `.gitignore`
- `requirements.txt`, only if actual runtime dependencies changed
- `tests/test_validation.py`
- `tests/test_database.py`
- Other MVP files only for defects found during final testing
- Existing Git configuration and ignore behavior, without reinitializing Git

The following must not be committed:

- `data/pmc.db`
- SQLite `-wal` or `-shm` files
- Database backups
- `archive/products.csv`
- `.venv`
- `__pycache__`
- `.pyc` files
- `.DS_Store`
- Test/tool caches
- `pasted-text.txt`
- `.env` and other secret-bearing environment files

## 3. Exact expected result

- All automated tests pass.
- All manual workflows pass.
- README explains:
  - Project purpose.
  - MVP scope.
  - File responsibilities.
  - Environment setup.
  - How to run Streamlit.
  - How to run tests.
  - Database location and backup expectations.
  - Deferred features.
- PROJECT_SPEC matches the implemented fields, statuses, workflows, and metrics.
- Existing Git configuration and ignore rules are verified without
  reinitializing the repository.
- A pre-commit status check proves excluded files are not staged or tracked.
- The proposed Phase 7 commit contains only approved source, tests, and
  documentation changes.
- Existing SQLite and CSV data remain preserved locally.
- No external AI calls or credentials exist.

## 4. Manual tests

Complete acceptance walkthrough:

1. Inspect the existing Product Manager Central record read-only.
2. Point `PMC_DATABASE_FILE` to a new disposable database.
3. Launch the application and confirm the empty dashboard.
4. Create a valid disposable product.
5. Create another product with the same name.
6. Search for both.
7. Open both by ID.
8. Edit one without affecting the other.
9. Attempt an invalid edit and confirm no stored value changes.
10. Cancel deletion and confirm the record remains.
11. Permanently delete only the intended record.
12. Confirm dashboard metrics refresh correctly.
13. Stop and restart Streamlit against the same disposable database.
14. Confirm the remaining record persists.
15. Remove the disposable database and temporary artifacts.
16. Confirm the live database, CSV archive, and permanent backups are unchanged.
17. Confirm ignored data does not appear in the proposed staging set.

## 5. Automated tests

Run the complete model, validation, database, presentation-helper, and
Streamlit workflow test suite.

Final automated coverage must include:

- Required and optional validation.
- Field normalization.
- Status validation.
- Empty database initialization.
- Legacy-schema migration.
- CRUD.
- Duplicate names.
- Search.
- Timestamps.
- Dashboard metrics.
- Missing-record behavior.
- Database constraints and rollback behavior.

The tests must not read from or write to `data/pmc.db`.

## 6. Approval checkpoint

Before declaring the MVP complete or making the Phase 7 commit:

- Review the automated test results.
- Complete the manual acceptance walkthrough.
- Review final README and PROJECT_SPEC.
- Review the Git staging set.
- Confirm the live database, backup, and CSV are excluded.
- Approve the Phase 7 commit contents.

No later refactor, AI integration, service layer, view layer, or advanced feature work begins without a separate plan and approval.

## Phase 7 completion record

**Completed:** July 30, 2026

The Phase 7 preflight confirmed:

- `main` was clean and matched `origin/main` at Phase 6 commit
  `975da63b635bb70f95ec5c65623f1f616c851948`.
- Git was already initialized and was not reinitialized.
- The implemented application, persistence layer, validation rules,
  dependencies, and tests were reviewed in full.
- Documentation drift was limited to outdated phase status, action wording,
  incomplete validation/workflow detail, and obsolete first-commit Git
  instructions.

Final verification completed successfully:

- All 103 automated tests passed using temporary databases.
- The disposable acceptance walkthrough passed empty dashboard, valid create,
  duplicate-name create, search, ID-specific detail, isolated edit, rejected
  invalid edit, canceled deletion, confirmed deletion, metric refresh, actual
  Streamlit stop/restart, and persistence checks.
- The disposable database and server logs were removed during cleanup.
- `git diff --check` passed.
- Runtime dependencies were complete; `requirements.txt` did not change.
- No application, test, database, schema, or migration change was required.

Data-safety verification confirmed:

- The live database passed SQLite integrity checking and retained the complete
  Product Manager Central record at ID 1.
- The live database remained unchanged at SHA-256
  `7577ddf8dc7db112a295ab862102c4e89e2485b21b8a274969dedeffbdd9f049`.
- `archive/products.csv` remained unchanged at SHA-256
  `3c9e8eb9190ead8c8708d8ab0b957ece195d6704cb3682adf23ca55671be21f3`.
- All four permanent backup files retained their preflight checksums.
- Databases and sidecars, backups, the CSV, virtual environments, Python/test/
  tool caches, operating-system files, temporary pasted text, and secret-bearing
  environment files are ignored and are neither tracked nor staged.

No Generative AI, external LLM, RAG, prompt management, generated artifacts,
export, authentication, deployment, analytics, charts, advanced styling, ORM,
service/view layers, schema changes, migrations, or unrelated refactoring were
added. Phase 7 and the Product Manager Central MVP are complete, pending
approval to commit and push these final documentation and Git-safety changes.

# Phase 8: Product Document Builder

## 1. Purpose

Add deterministic, template-guided BRD and PRD authoring for existing products.
Phase 8 does not create or integrate an LLM, call an AI API, require API tokens,
or generate document content.

## 2. Files created or changed

- `app.py`
- `src/models.py`
- `src/document_templates.py`
- `src/validation.py`
- `src/database.py`
- Document validation, persistence, migration, and Streamlit workflow tests
- `PROJECT_SPEC.md`
- `IMPLEMENTATION_PLAN.md`
- `DECISIONS.md`
- `README.md`

No runtime dependency is added.

## 3. Data design and migration

- `documents` stores stable document ID, product ID, type, title, version,
  status, and timestamps.
- `document_sections` stores one row per stable template section key.
- SQLite foreign keys are enabled on application connections.
- Both relationships use `ON DELETE CASCADE`.
- `idx_documents_product_id` supports product document listings.
- Empty databases receive the complete schema directly.
- Existing product-only canonical databases receive the document tables and
  index in one additive transaction.
- Migration verifies that the complete ordered product rowset is unchanged.
- Known legacy and unknown-schema protections remain in place.

## 4. Validation and workflow

- Document type, associated product ID, title, version, and status are required.
- Titles allow 200 characters; versions allow 50; sections allow 10,000 each.
- Version is nonblank free text.
- Draft body sections may be empty.
- Approved documents require every template section and report every incomplete
  section by readable label.
- Creation begins from an existing product and supports BRD or PRD selection.
- Approved product fields are copied once into the new-document form.
- Saved documents are listed by product, previewed in template order, and edited
  by stable document ID.
- Multiple documents may be associated with one product.
- Product deletion confirmation reports the number of documents that will
  cascade.
- Document export and explicit document deletion are outside Phase 8.

## 5. Verification requirements

- Migration, rollback, schema, foreign-key, index, preservation, BRD, PRD,
  association, multiplicity, validation, stable update, version/status,
  timestamp, cascade, prepopulation snapshot, preview, edit, and regression
  tests use disposable databases.
- A verified ignored backup precedes active migration.
- The migration is dry-run against a disposable copy and compares every product
  row and value before active migration.
- The complete automated suite, disposable Streamlit walkthrough, SQLite
  integrity check, `git diff --check`, and Git artifact review must pass.

## Phase 8 completion record

**Implemented:** August 1, 2026

Phase 8 implements the approved normalized schema and deterministic document
workflow. The active migration was preceded by an ignored SQLite backup and a
successful disposable-copy dry run. The migration preserved both existing
product rows and every value, left the database integrity check at `ok`, and
created zero initial documents. Final test counts and Git verification are
recorded in the implementation handoff rather than hard-coded here.

## Phase 8 focused navigation improvement

**Implemented:** August 1, 2026

The primary sidebar now places Create PRD and Create BRD after Create Product
and before View Products. Each page starts with an explicit placeholder and
requires an ID-safe product selection before displaying the fixed document-type
form. Duplicate product names remain unambiguous. An empty database displays
product-first guidance and a Go to Create Product action without rendering an
unusable document form.

The primary routes reuse the existing Phase 8 form, prepopulation, validation,
persistence, preview, editing, and stable document ID behavior. Route-specific
widget and workflow keys prevent PRD, BRD, and product-detail state from
leaking into one another. The product-detail Create Document path remains
available as a secondary convenience. No database, migration, model, template,
validation, dependency, LLM, RAG, export, authentication, or deployment change
was introduced.

# Phase 9: AI Assistant

## Checkpoint 1: Secure connection and approved-source boundaries

**Completed:** August 4, 2026

Checkpoint 1 introduces only the foundations approved for this increment:

- Add the compatible official OpenAI Python SDK runtime dependency.
- Read `OPENAI_API_KEY` only from the environment and expose only non-secret
  configured/inactive status.
- Allow the default Responses API model to be overridden with `OPENAI_MODEL`.
- Isolate `client.responses.create` behind an injectable service so automated
  tests make no network request and consume no tokens.
- Query the existing normalized schema read-only for sections belonging only to
  Approved BRDs and PRDs.
- Return product, document, type, and section metadata needed for future source
  citations.
- Document optional activation, separate ChatGPT/API billing, secure macOS and
  Windows environment setup, deactivation, and key replacement.
- Preserve Phase 8 workflows and the current schema.

Checkpoint 1 does not add embeddings, semantic ranking, a question-answer UI,
answer generation, prompt management, generated-content persistence, human
acceptance controls, or RAG evaluation. AI must never automatically modify an
original BRD or PRD; any later generated content must remain separate until a
human explicitly accepts it.

The complete suite passed 146 tests, including the unchanged Phase 8 workflow
coverage and seven new AI/retrieval tests. `git diff --check`, secret and
artifact review, and database/backup checksum comparisons passed. No schema,
live database, backup, UI, or production-data change was made.

## Checkpoint 2: Embeddings and semantic retrieval

**Completed:** August 5, 2026

Checkpoint 2 adds only the approved retrieval capabilities for this increment:

- Split nonblank Approved BRD/PRD sections into deterministic,
  paragraph-aware chunks with stable content-derived IDs.
- Preserve product ID/name, document ID/title/type/approval status, section
  key/title, chunk index, and unchanged source text with every chunk.
- Extend the injectable official OpenAI client boundary to embeddings, with
  `OPENAI_EMBEDDING_MODEL` configuration and no live calls in tests.
- Rank chunks by cosine similarity, return scores in descending order, and
  support configurable result limits and minimum relevance thresholds.
- Re-read the approved-source boundary after embedding so deleted, missing,
  edited, Draft, unsupported, or no-longer-approved content cannot be returned
  as a trusted result.
- Return explicit states for no Approved BRD/PRD sources and for no relevant
  results.
- Preserve the normalized schema and all original products, BRDs, PRDs, and
  document sections unchanged.

Keyword search and semantic retrieval remain distinct. Existing product search
matches literal words or substrings across product fields. Semantic retrieval
compares embedding vectors so conceptually related approved document chunks can
rank even when they use different wording.

Checkpoint 2 does not add the assistant interface, answer generation, prompt
management, generated-content persistence or acceptance, source-document
mutation, or RAG evaluation. The complete suite passed 155 tests with
deterministic fake or mocked embeddings and no network or API key requirement.
`git diff --check` and final artifact/secret review also passed.

## Checkpoint 3: Assistant interface and grounded draft generation

**Completed:** August 5, 2026

Checkpoint 3 adds the approved generation workflow without adding persistence:

- Accept a Product Manager's request through a Streamlit-independent service.
- Retrieve and revalidate only Approved BRD and PRD chunks; exclude Draft and
  unsupported content.
- Construct a source-numbered prompt from the request and trusted context, then
  call the Responses API through the existing injectable OpenAI service.
- Return clearly labeled generated draft content with structured citations for
  product name/ID, document title/ID/type, and section title/key.
- Return explicit ungrounded empty states and skip generation when no approved
  or relevant context is available.
- Keep generated content temporary and separate. No original document is
  modified, and Checkpoint 3 exposes no save operation; human review and
  explicit acceptance are prerequisites for the later saving workflow.
- Handle missing configuration, invalid requests, provider failures, and
  malformed responses with non-secret, user-safe messages.

The existing schema remains sufficient. Tests use injected fakes/mocks and
explicit temporary database paths, make no live API calls, and never access the
live database.

## Remaining Phase 9 checkpoints

- Checkpoint 4: Generated-content review, acceptance, and saving — Completed
  August 9, 2026
  - Display the original generated output and structured supporting citations.
  - Keep revisions pending until a separate explicit acceptance action.
  - Reject without creating a saved or approved artifact.
  - Store accepted content separately with its product, original AI output,
    accepted revision, and citation/source snapshots.
  - Revalidate cited sources as current Approved BRDs or PRDs at acceptance.
  - Use a unique review key to prevent duplicate saves across repeated submits
    and Streamlit reruns.
  - Verify the workflow with deterministic generation and temporary databases;
    no live OpenAI request or production-database write is required.
- Checkpoint 5: Prompt management and assistant workflow hardening — Completed
  August 9, 2026
  - Define immutable, version-controlled prompt metadata and templates in source.
  - Move the existing grounded-draft prompt into the catalog without changing
    the Approved-only evidence, citation, or source-document safety rules.
  - Require explicit product, assistant-task, approved-prompt, and request input
    before retrieval or generation.
  - Display only the selected prompt's public name, description, and version.
  - Reject missing inputs, unsupported prompt IDs, and task/prompt mismatches.
  - Prevent generation without approved BRD/PRD evidence or available optional
    API configuration, using non-sensitive messages.
  - Harden Streamlit reruns against duplicate generation and preserve the
    existing idempotent explicit-acceptance workflow.
  - Keep prompts out of SQLite; do not add user editing, product-specific
    prompts, experiments, optimization, or evaluation features.
- Checkpoint 6: RAG evaluation and release verification — Completed August 9,
  2026
  - Add a developer-facing, offline evaluator with no Streamlit dashboard,
    LLM-as-a-judge, result persistence, database migration, or schema change.
  - Score retrieval precision and recall from expected and returned stable
    chunk IDs; score citation completeness and source correspondence across
    citations.
  - Score source trust, grounded generation, human control, and source
    separation as binary criteria.
  - Average all eight criteria without weights and report the result from 0 to
    100. Require at least 80 overall and perfect source-trust,
    citation-completeness, human-control, and source-separation scores.
  - Exercise successful, empty, stale-source, rejected, fractional, and
    boundary outcomes with deterministic fake providers and temporary
    databases.
  - Validate Approved BRD/PRD-only retrieval, citation metadata, explicit
    acceptance, separate persistence, rerun idempotency, and safe user-facing
    failures across the complete Phase 9 test suite.
  - Preserve the production database, source documents, backups, archive,
    environment, secrets, and existing untracked screenshot unchanged.

Phase 9 is complete. The Checkpoint 6 deterministic release cases scored 100
for every criterion and passed the approved release gates. The complete suite
passed 205 tests without a live OpenAI call or production-database access.

# Phase 10: Portfolio Release and Distribution

## Goal and approved boundaries

Prepare Product Manager Central as a polished local portfolio application that
Product Managers can download and run on Mac or Windows and recruiters can
review as evidence of practical generative-AI product management. Phase 10 does
not turn PMC into a publicly hosted enterprise service.

The planned first release is v1.0.0 under the MIT License. Distribution will be
a source-based GitHub Release ZIP with cross-platform setup and launch helpers,
not a native signed or notarized installer. The package must start clean or
offer separately invoked fictional sample data; it must never contain the
existing production database or a prebuilt SQLite sample.

Python and operating-system support remain unclaimed until an exact combination
passes clean-environment dependency installation, the complete automated suite,
and an isolated no-key application smoke test. Direct runtime dependencies will
be pinned only after that evidence exists. The current requirements remain
unchanged in Checkpoint 1.

## Checkpoint 1: Release definition, governance, and versioning

**Completed:** August 9, 2026

- Add the MIT License using Celso Gonçalves Guerra as the copyright holder.
- Establish `1.0.0` source metadata and the planned `v1.0.0` Git tag convention
  without creating a tag or publishing a release.
- Add changelog, contribution, and security-reporting policies.
- Define Semantic Versioning, release approval, archive safety, and checksum
  conventions.
- Define evidence-based environment support and direct-dependency policies
  without making speculative dependency changes or support claims.
- Add deterministic governance and metadata consistency tests.
- Ignore the exact protected screenshot filename without modifying the file.
- Preserve the production database, all Phase 9 safeguards, and the existing
  205-test baseline.

Checkpoint 1 verification passed 214 tests, Python compilation, the isolated
no-key application smoke test, `git diff --check`, version consistency, secret
and artifact review, and protected-file comparisons. No dependency, application,
database, package, tag, or publication change was made.

## Checkpoint 2: First-time onboarding, fictional sample data, and accepted-artifact history

**Completed:** August 9, 2026

- Add plain-language Getting Started guidance to the default Dashboard.
- Explain the local workflow, Draft versus Approved status, Approved-only AI
  sources, citations, human review, explicit acceptance, source separation, and
  secure environment-based API-key setup.
- Add one explicitly triggered, deterministic fictional Trailwise product with
  an Approved PRD and a Draft BRD; never load it automatically or ship a
  prebuilt database.
- Use a source-controlled sample marker and recovery state so repeat activation
  does not create uncontrolled duplicates or overwrite user records.
- Explain how to identify and manually delete the fictional product through the
  existing product workflow.
- Show separately stored accepted AI artifacts in normal product detail with
  purpose, content, revision context, dates, product association, and complete
  citations.
- Keep artifact history read-only; do not add edit, delete, regenerate, or
  source-document update actions.
- Add deterministic temporary-database and Streamlit coverage without live
  OpenAI calls.

Checkpoint 2 makes no schema, dependency, production-database, packaging,
version, or release-status change. Verification passed 11 focused tests and the
complete 225-test suite, Python compilation, an isolated no-key startup smoke
test, `git diff --check`, secret and artifact review, and protected-file
comparisons.

## Checkpoint 3: Cross-platform installation, launch, and packaging

**Completed:** August 9, 2026

- Validate a clean macOS 26.5.2 arm64 installation on Python 3.14.6; document
  that Windows and Python 3.11–3.13 have structural rather than native coverage.
- Establish Python 3.11 as the dependency-imposed prerequisite floor and allow
  launchers through Python 3.14 without overstating native validation.
- Pin only the three direct runtime dependencies to clean-tested versions:
  Streamlit 1.61.1, pandas 3.0.5, and OpenAI 2.53.0.
- Add Mac and Windows setup helpers that locate the application directory,
  create or reuse `.venv`, install declared dependencies, and fail with
  actionable prerequisite messages.
- Add Mac and Windows run helpers that validate the environment, optionally
  accept a masked session-only API key, launch `app.py`, and explain shutdown.
- Document install, start, stop, backup, restoration, update, uninstall,
  clean-database, optional-sample, security-prompt, and checksum workflows.
- Build local test ZIPs only from the explicit human-readable
  `release_manifest.txt` allowlist.
- Validate exact archive membership, normalize ZIP metadata, generate SHA-256,
  refuse accidental overwrite, and exclude databases, secrets, sidecars,
  archives, Git metadata, caches, tests, and the protected screenshot.
- Test Mac helpers executably and Windows helpers structurally without claiming
  native Windows validation.

Checkpoint 3 creates build capability only. It does not create an official
release candidate, Git tag, GitHub Release, installer, or publication.
Verification passed 6 launcher tests, 10 package tests, 20 affected workflow and
metadata tests, the complete 241-test suite in both the development and fresh
pinned environments, Python and shell syntax checks, `git diff --check`, secret
and artifact review, deterministic archive comparison, checksum and exact-member
validation, and extracted no-key clean-database startup.

## Checkpoint 4: UAT, beta preparation, and responsible use

**Completed:** August 9, 2026

- Add one consolidated guide with 17 traceable UAT scenarios, each containing
  preconditions, steps, expected results, pass/fail criteria, evidence, and
  status.
- Cover clean startup, product and document workflows, approval validation,
  Approved-only retrieval, ineligible-source exclusion, citations, no-key
  behavior, human review, explicit acceptance, acceptance-time revalidation,
  generated/source separation, explicit samples, local-data operations, and
  cross-platform launcher guidance.
- Define a future four-to-six-Product-Manager beta with participant selection,
  objectives, onboarding, feedback boundaries, severity, exit criteria, and
  stop/rollback conditions without conducting participant outreach or claiming
  beta results.
- Consolidate setup and workflow troubleshooting, known product and validation
  limitations, and responsible-use guidance for AI-generated content.
- Distinguish automated validation, internal UAT, structural Windows evidence,
  native macOS evidence, and future external validation.
- Preserve application code, dependencies, launchers, packaging logic, schema,
  Approved-only retrieval, citations, human control, explicit acceptance,
  source revalidation, source separation, clean startup, and optional samples.
- Include the guide in the explicit future source-release allowlist without
  creating an official release artifact.

Checkpoint 4 verification passed 126 focused internal UAT and regression tests,
the complete 246-test suite, compilation of all 35 tracked Python files, Bash
and Zsh syntax checks, and the existing Windows structural tests. Two isolated
32-member archives matched byte-for-byte and passed manifest, exclusion,
SHA-256, extracted no-key clean-start, and temporary-cleanup checks.
`git diff --check`, secret and prohibited-artifact review, and production
database, protected screenshot, and existing README image comparisons passed.
The external beta was not conducted, native Windows and Python 3.11–3.13 remain
unvalidated, and no application, database, official package, tag, release, or
publication change was made.

## Remaining Phase 10 checkpoints

- Checkpoint 5: Recruiter case study, architecture diagram, sanitized
  screenshots, demo plan, and launch materials — Not started
- Checkpoint 6: Release-candidate verification and GitHub release preparation —
  Not started
