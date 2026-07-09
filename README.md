# Production Scripts

Opentrons SZ production scripts monorepo. This repository collects production test CLI tools, data-center services, module diagnostics, shared device drivers, and small manufacturing utilities.

## Projects

| Project | README | Purpose |
| --- | --- | --- |
| Test CLI | [test_cli/README.md](test_cli/README.md) | Cross-platform production test CLI, including leveling tests and executable packaging. |
| Opentrons Productions | [opentrons-productions/README.md](opentrons-productions/README.md) | FastAPI + Vue production data center for upload, analysis, robot control, and production tracking. |
| Upload Handler | [opentrons-productions/backend/src/upload_handler/README.md](opentrons-productions/backend/src/upload_handler/README.md) | Internal upload pipeline notes for Google Drive/Sheets and upload configuration. |
| Thermocycle Diagnostic | [modules_testing/thermocycle_diagnostic/README.md](modules_testing/thermocycle_diagnostic/README.md) | Thermocycler diagnostic script and report flow. |
| High Voltage Test | [tools/high_voltage_test/README.md](tools/high_voltage_test/README.md) | Manual high-voltage tester control through the GPT serial driver. |
| Pipette Function Formatting | [tools/pipette_function_formating/README.md](tools/pipette_function_formating/README.md) | Converts copied function table data into bracketed function text files. |

## Top-Level Layout

```text
production-scripts/
├── devices/                 # Shared device drivers
├── drivers/                 # Shared serial/transport drivers
├── launchers/               # Test CLI launcher scripts
├── modules_testing/         # Module diagnostics and module-specific tools
├── opentrons-productions/   # Production data-center app
├── shared_data/             # Shared specs, assets, and test data resources
├── test_cli/                # Main production test CLI package
├── tests/                   # Repository-level tests
└── tools/                   # Small manufacturing and data utilities
```

## Dependency Model

- Root Python tooling uses `pyproject.toml` and `uv.lock`.
- `opentrons-productions/backend` has its own `pyproject.toml` and `uv.lock`.
- Frontend dependencies live in `opentrons-productions/web_ui/package.json` and `package-lock.json`.
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
  make opentrons-install       Install opentrons-productions backend dependencies
  make opentrons-backend       Start opentrons-productions backend with reload
  make opentrons-backend-prod  Start opentrons-productions backend without reload
  make opentrons-health        Check opentrons-productions backend health
  make opentrons-web-ui-build  Build opentrons-productions web UI
  make opentrons-update        Update opentrons-productions remote code
  make high-voltage            Run high-voltage manual test workflow

Variables:
  HOST=0.0.0.0 PORT=8090
  COMPONENT=all|backend|web DEPLOY_HOST=IP
  PUSH_ARGS='...' WEB_PUSH_ARGS='...'

Subproject help:
  make -C test_cli help
  make -C opentrons-productions help
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

## Opentrons Productions Makefile Help

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

Run Opentrons Productions backend:

```bash
make opentrons-install
make opentrons-backend
```

Build Opentrons Productions frontend:

```bash
make opentrons-web-ui-build
```

## Repository Rules

- Keep generated data out of git: `.venv`, `node_modules`, `dist`, `build`, `__pycache__`, `.pytest_cache`, logs, local reports, and credentials.
- Put new project-level documentation in that project's `README.md`, then link it from this root README.
- Use `uv` for Python dependency changes unless a subproject explicitly documents another tool.
- Avoid nested git repositories inside this monorepo.
