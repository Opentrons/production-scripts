# Production Scripts

Opentrons SZ production scripts monorepo. This repository collects production test CLI tools, data-center services, module diagnostics, shared device drivers, and small manufacturing utilities.

## Projects

| Project | README | Purpose |
| --- | --- | --- |
| Productions Index | [productions-index/README.md](productions-index/README.md) | Static Vue launch page for production web tools. |
| Test CLI | [test_cli/README.md](test_cli/README.md) | Cross-platform production test CLI, including leveling tests and executable packaging. |
| Productions Opentrons | [productions-opentrons/README.md](productions-opentrons/README.md) | FastAPI + Vue production data center for upload, analysis, robot control, and production tracking. |
| Upload Handler | [productions-opentrons/backend/src/upload_handler/README.md](productions-opentrons/backend/src/upload_handler/README.md) | Internal upload pipeline notes for Google Drive/Sheets and upload configuration. |
| Thermocycle Diagnostic | [modules_testing/thermocycle_diagnostic/README.md](modules_testing/thermocycle_diagnostic/README.md) | Thermocycler diagnostic script and report flow. |
| High Voltage Test | [tools/high_voltage_test/README.md](tools/high_voltage_test/README.md) | Manual high-voltage tester control through the GPT serial driver. |
| Pipette Function Formatting | [tools/pipette_function_formating/README.md](tools/pipette_function_formating/README.md) | Converts copied function table data into bracketed function text files. |

## Top-Level Layout

```text
production-scripts/
├── devices/                 # Shared device drivers
├── drivers/                 # Shared serial/transport drivers
├── productions-index/       # Static Vue launch page for production web tools
├── launchers/               # Test CLI launcher scripts
├── modules_testing/         # Module diagnostics and module-specific tools
├── productions-opentrons/   # Production data-center app
├── shared_data/             # Shared specs, assets, and test data resources
├── test_cli/                # Main production test CLI package
├── tests/                   # Repository-level tests
└── tools/                   # Small manufacturing and data utilities
```

## Dependency Model

- Root Python tooling uses `pyproject.toml` and `uv.lock`.
- `productions-opentrons/backend` has its own `pyproject.toml` and `uv.lock`.
- Frontend dependencies live in `productions-opentrons/web_ui/package.json` and `package-lock.json`.
- `Pipfile` / `pipenv` should not be used for new work.
- Local environments, caches, build output, credentials, and generated reports are ignored by `.gitignore`.

## Root Makefile Help

From the repository root:

```text
Available targets:
  make help                    Show this help message
  make test-cli                Start interactive test-cli
  make leveling                Start leveling CLI
  make simulate                Run all leveling tests in simulation mode
  make test-cli-build          Build test-cli executable
  make build-exe               Alias of test-cli-build
  make update-compensation     Update leveling_config.json from Templete.xlsx
  make productions-opentrons-install       Install productions-opentrons backend dependencies
  make productions-opentrons-backend       Start productions-opentrons backend with reload
  make productions-opentrons-backend-prod  Start productions-opentrons backend without reload
  make productions-opentrons-health        Check productions-opentrons backend health
  make productions-opentrons-web-ui-build  Build productions-opentrons web UI
  make productions-opentrons-update        Update productions-opentrons remote code
  make deploy-productions-opentrons Deploy productions-opentrons for indexed routing
  make productions-index-init  Install productions index dependencies
  make productions-index-dev   Start the productions index page
  make productions-index-build Build the productions index page
  make deploy-productions-index Deploy productions index and nginx proxy
  make deploy-productions      Deploy productions-opentrons and productions index
  make high-voltage            Run high-voltage manual test workflow

Variables:
  HOST=0.0.0.0 PORT=8090 PRODUCTIONS_INDEX_PORT=5173 PRODUCTIONS_INDEX_DEPLOY_PORT=80
  COMPONENT=all|backend|web DEPLOY_HOST=IP
  PUSH_ARGS='...' WEB_PUSH_ARGS='...' PRODUCTIONS_INDEX_PUSH_ARGS='...'
  PRODUCTIONS_OPENTRONS_WEB_BASE_PATH=/productions-opentrons/
  PRODUCTIONS_OPENTRONS_PROXY_PATH=/productions-opentrons PRODUCTIONS_OPENTRONS_WEB_PORT=8091

Subproject help:
  make -C productions-index help
  make -C test_cli help
  make -C productions-opentrons help
  make -C tools/high_voltage_test help
```

## Test CLI Makefile Help

```text
make                 Start interactive test-cli
make leveling        Start leveling CLI
make simulate        Run all leveling tests in simulation mode
make build           Build current-platform executable into ../dist
make build-clean     Clean then build executable
make update-compensation  Update leveling_config.json from test_cli/leveling_test/Templete.xlsx
make clean           Remove build artifacts
```

## Productions Opentrons Makefile Help

```text
Available targets:
  make install       Install backend dependencies with uv
  make stop-backend  Stop backend service on PORT (default 8090)
  make backend       Start backend service with reload
  make backend-prod  Start backend service without reload
  make health        Check backend health endpoint
  make update        Update remote code (default: backend + web_ui)
  make push          Alias of update
  make push-backend  Upload backend code (stops service first, fixes robot_key)
  make update-backend Alias of push-backend
  make web-ui-build  Build web_ui dist
  make push-web-ui   Build and upload web_ui dist
  make update-web-ui Alias of push-web-ui

Update parameters:
  COMPONENT=all|backend|web   Which part to update (default: all)
  DEPLOY_HOST=IP              Apply --host to both push scripts
  PUSH_ARGS='...'             Extra args for backend push-scripts.py
  WEB_PUSH_ARGS='...'         Extra args for web_ui push-scripts.py
  WEB_UI_BASE_PATH=/          Vite base path for web_ui build

Examples:
  make update
  make update COMPONENT=backend
  make update COMPONENT=web
  make update DEPLOY_HOST=192.168.0.137
  make update PUSH_ARGS='--no-deploy' WEB_PUSH_ARGS='--no-deploy'
```

## High Voltage Test Makefile Help

```text
Available targets:
  make setup  Install root project dependencies with uv
  make pip    List packages in the uv environment
  make run    Run the high-voltage manual test workflow
  make gpt    Run the GPT device driver module
  make show   Show resolved project root and Python command
```

## Common Workflows

Install and run Test CLI:

```bash
uv sync
uv run test-cli leveling
```

Run Test CLI in simulation:

```bash
make simulate
```

Update leveling compensation from the fixed template:

```bash
make update-compensation
```

Run Productions Opentrons backend:

```bash
make productions-opentrons-install
make productions-opentrons-backend
```

Build Productions Opentrons frontend:

```bash
make productions-opentrons-web-ui-build
```

Run the Productions index page:

```bash
make productions-index-init
make productions-index-dev
```

Deploy Productions Index and Productions Opentrons:

```bash
make deploy-productions DEPLOY_HOST=192.168.0.137
```

This deploys `productions-opentrons` with `WEB_UI_BASE_PATH=/productions-opentrons/`, deploys `productions-index` on port `80`, and configures nginx so `/productions-opentrons/` proxies to local port `8091`. The previous `/opentrons-productions/` route and legacy typo `/opetrons-productions/` both redirect to `/productions-opentrons/`.

## Repository Rules

- Keep generated data out of git: `.venv`, `node_modules`, `dist`, `build`, `__pycache__`, `.pytest_cache`, logs, local reports, and credentials.
- Put new project-level documentation in that project's `README.md`, then link it from this root README.
- Use `uv` for Python dependency changes unless a subproject explicitly documents another tool.
- Avoid nested git repositories inside this monorepo.
