# Product Manager Central

Product Manager Central (PMC) is a beginner-friendly Python and Streamlit project for organizing product information. Its long-term vision includes AI-assisted product documentation, but the first MVP focuses on reliable product management with SQLite.

## Current status

Phase 0 protected the existing SQLite data. Phase 1 repairs the filesystem structure and documents the approved MVP without changing application behavior.

The running application is still the original prototype: it creates products using four fields, stores them in SQLite, and lists saved products. The expanded model, centralized validation, CRUD operations, search, and dashboard workflows are planned for later approved phases.

## Technology

- Python
- Streamlit
- SQLite
- Pandas

SQLite is the application's only active data source. No external AI model is connected in the MVP.

## Project structure

- `app.py`: Current Streamlit application and, later, the MVP navigation and interface.
- `src/database.py`: Current SQLite initialization and persistence functions; CRUD and search are deferred to Phase 3.
- `src/models.py`: Reserved for the Product data structure and approved statuses in Phase 2.
- `src/validation.py`: Reserved for centralized validation and normalization in Phase 2.
- `tests/test_validation.py`: Reserved for Phase 2 validation tests.
- `tests/test_database.py`: Reserved for Phase 3 database tests.
- `data/pmc.db`: Local live SQLite database; intentionally excluded from Git.
- `archive/products.csv`: Preserved legacy CSV; not imported or used by the application.
- `IMPLEMENTATION_PLAN.md`: Approved phase-by-phase development plan.
- `PROJECT_SPEC.md`: Approved MVP product and technical scope.
- `DECISIONS.md`: Architecture and product decision record.

## Run the current application

From the project root, activate the local Python environment and run:

```text
streamlit run app.py
```

The current dependencies are listed in `requirements.txt`.

## Data safety

- Do not use automated tests against `data/pmc.db`.
- Back up the live database before any schema change.
- Keep database files and backups out of Git.
- Preserve `archive/products.csv`; it is historical data, not an active data source.
- Do not test deletion using the preserved Product Manager Central record.

## Development approach

Development proceeds one approved phase at a time. Each phase has manual or automated checks and an approval checkpoint before the next phase begins.

The following are deliberately deferred: external AI integration, AI generators, service and view layers, an ORM, advanced analytics, authentication, and cloud deployment.
