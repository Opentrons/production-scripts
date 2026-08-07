# Backend

The repository's only FastAPI service. It provides uploads, data analysis, robot control, test management, resources, Duro, SOP, and workflows.

The Python source is flat under `src/`: `app.py` is the service entry point, while `api/`, `core/`, and `modules/` are importable top-level packages. `api/router.py` aggregates the domain routers under `api/routers/`. Start Uvicorn with `app:app`.

```bash
make backend-dev
make backend-test
```

Runtime files, including the preserved SQLite databases, live in `apps/backend/data/`.
