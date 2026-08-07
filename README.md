# Production Scripts

The repository is organized as three applications directly under `apps/`. There is no additional platform or packages layer.

```text
production-scripts/
├── apps/
│   ├── backend/              # FastAPI, data upload, robots, versions, SOP, workflows
│   ├── web-ui/               # Vue dashboard and operations UI
│   └── hardwares/            # executable, devices, drivers, diagnostics, and tools
│       └── src/
│           ├── cli/
│           ├── devices/
│           ├── drivers/
│           ├── gravimetric_testing/
│           ├── leveling_testing/
│           ├── modules_testing/
│           ├── opentonrs_api/
│           ├── resources/
│           └── tools/
├── deploy/
├── csv-samples/
├── Makefile
├── pyproject.toml
└── uv.lock
```

The backend-only Opentrons API client lives under `apps/backend`. Hardware report constants and the CLI HTTP client live under `apps/hardwares`; no standalone shared packages remain.

## Commands

```bash
make sync
make backend-dev
make backend-test
make web-install
make web-dev
make web-build
make hardware
make hardware-test
```

Run `make help` for all targets.

## Persistent data

The following SQLite databases remain in place and must not be removed by cleanup or deployment:

```text
apps/backend/data/duro_cache.sqlite3
apps/backend/data/sop_cache.sqlite3
apps/backend/data/workflows.sqlite3
```
