# Backend

The repository's only FastAPI service. It provides uploads, data analysis, robot control, test management, resources, Duro, SOP, and workflows.

The Python source is flat under `src/`: `app.py` is the service entry point, while `api/`, `core/`, and `modules/` are importable top-level packages. `api/router.py` aggregates the domain routers under `api/routers/`. Start Uvicorn with `app:app`.

```bash
make backend-dev
make backend-test
```

Runtime files live in `apps/backend/data/`.

Persistence rule:

- Non-simulating → MongoDB (`ProductionsMessage`) for auth, workflows, version records, health, and other business documents
- Simulating → SQLite under `db-storage/simulating/`

`db-storage/business/` may still hold regenerable caches (`duro_cache.sqlite3`, `sop_cache.sqlite3`). Legacy production sqlite files can be migrated with `apps/backend/scripts/migrate_sqlite_to_mongodb.py` then removed.

See [Platform authentication](docs/platform-authentication.md) for first-user and HTTPS deployment instructions.
