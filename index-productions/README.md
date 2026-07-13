# Index Productions

Static Vue/Vite launch page for production web tools.

The navigation includes a Downloads workspace for versioned static resources. Resources are grouped by project, and project/version metadata is tracked in MongoDB through the `opentrons-productions` backend.

## Run

```bash
make init
make dev
```

## Build

```bash
make build
```

## Makefile

```text
make init     Install frontend dependencies with npm ci
make dev      Start the Vite dev server
make start    Alias of dev
make build    Build the static frontend
make preview  Build and preview the static frontend
make clean    Remove local frontend artifacts
```

## Links

Module and API URLs can be configured at build time:

```bash
VITE_OPENTRONS_PRODUCTIONS_URL=/opentrons-productions/
VITE_PRODUCTION_AGENT_URL=/production-agent/
VITE_API_BASE_URL=/api
```

Defaults:

- `VITE_OPENTRONS_PRODUCTIONS_URL=/opentrons-productions/`
- `VITE_PRODUCTION_AGENT_URL` is unset, so the Production Agent card stays planned until configured.
- `VITE_API_BASE_URL=/api`

The local Vite server only provides the frontend. To exercise resource management locally, run the `opentrons-productions` backend and configure `VITE_API_BASE_URL` to reach it.

## Deployment

From the repository root:

```bash
make deploy-index-productions DEPLOY_HOST=192.168.0.137
```

The deployment script serves this app on port `80` and configures nginx to proxy `/api/` to the backend on local port `8090`. Uploaded files are stored by the backend in `/data/file_resources`; project and version records use the `file_resource_projects` and `file_resource_versions` MongoDB collections. The nginx upload limit is 200 MB per request.
