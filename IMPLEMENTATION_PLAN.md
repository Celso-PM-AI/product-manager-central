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

**Updated:** July 29, 2026

- Phases 0 through 5 are complete.
- Phase 6 has not started.
- Generative AI integration has not started.

The dashboard originally listed under the planned Phase 6 scope was delivered
during Phase 4. That earlier delivery does not mark Phase 6 as started.

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
- Separate Confirm Delete and Cancel actions.
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

# Phase 7: Final testing, documentation, and Git setup

## 1. Purpose

Verify the entire MVP, finalize beginner-friendly documentation, and establish safe version control only after generated and private data are excluded.

## 2. Files created or changed

- `README.md`
- `PROJECT_SPEC.md`
- `.gitignore`
- `requirements.txt`, only if actual runtime dependencies changed
- `tests/test_validation.py`
- `tests/test_database.py`
- Other MVP files only for defects found during final testing
- Git repository metadata after final approval of `.gitignore`

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
- Git is initialized only after ignore rules are verified.
- A pre-commit status check proves excluded files are not staged or tracked.
- The first commit contains source, tests, and documentation only.
- Existing SQLite and CSV data remain preserved locally.
- No external AI calls or credentials exist.

## 4. Manual tests

Complete acceptance walkthrough:

1. Launch the application.
2. Confirm the existing Product Manager Central record.
3. Review dashboard metrics.
4. Create a valid disposable product.
5. Create another product with the same name.
6. Search for both.
7. Open both by ID.
8. Edit one without affecting the other.
9. Attempt an invalid edit.
10. Cancel deletion.
11. Confirm permanent deletion.
12. Restart Streamlit.
13. Confirm remaining data persists.
14. Confirm dashboard metrics remain correct.
15. Confirm the CSV archive and database backup still exist.
16. Confirm ignored data does not appear in the Git staging set.

## 5. Automated tests

Run the complete validation and database test suite.

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

Before declaring the MVP complete or making the first Git commit:

- Review the automated test results.
- Complete the manual acceptance walkthrough.
- Review final README and PROJECT_SPEC.
- Review the Git staging set.
- Confirm the live database, backup, and CSV are excluded.
- Approve the first commit contents.

No later refactor, AI integration, service layer, view layer, or advanced feature work begins without a separate plan and approval.
