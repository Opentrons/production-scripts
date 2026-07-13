# Index Productions

Static Vue/Vite launch page for production web tools.

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

The launch page has no backend. Module URLs can be configured at build time:

```bash
VITE_OPENTRONS_PRODUCTIONS_URL=/opentrons-productions/
VITE_PRODUCTION_AGENT_URL=/production-agent/
```

Defaults:

- `VITE_OPENTRONS_PRODUCTIONS_URL=/opentrons-productions/`
- `VITE_PRODUCTION_AGENT_URL` is unset, so the Production Agent card stays planned until configured.

## Deployment

From the repository root:

```bash
make deploy-index-productions DEPLOY_HOST=192.168.0.137
```

The deployment script serves this app on port `80` and configures nginx to proxy `/opentrons-productions/` to local port `8091`.
