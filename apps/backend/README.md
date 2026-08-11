# Backend

The repository's only FastAPI service. It provides uploads, data analysis, robot control, test management, resources, Duro, SOP, and workflows.

The Python source is flat under `src/`: `app.py` is the service entry point, while `api/`, `core/`, and `modules/` are importable top-level packages. `api/router.py` aggregates the domain routers under `api/routers/`. Start Uvicorn with `app:app`.

```bash
make backend-dev
make backend-test
```

Runtime files live in `apps/backend/data/`.

SQLite databases live under `apps/backend/db-storage/`:

- `db-storage/business/` — production/business sqlite (workflows, duro/sop cache, and simulating-off platform docs)
- `db-storage/simulating/` — isolated sqlite used when Dashboard **Simulating** is enabled

When simulating is on, Mongo-backed features (robot scan gateways/cache, SSH custom commands, upload finish settings) use `db-storage/simulating/platform.sqlite3` instead of MongoDB.

Platform login accounts and sessions use `db-storage/auth/auth.sqlite3`, independently of simulating mode. See [Platform authentication](docs/platform-authentication.md) for first-user and HTTPS deployment instructions.
