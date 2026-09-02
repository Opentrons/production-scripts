# Google credentials

Put `credentials.json` and `token.json` in this directory for user OAuth, or put
`service-account.json` here for unattended server-side Google API access. These
files are ignored by git. Server deployments read `/configs/service-account.json`
by default; override it with `PRODUCTION_PLATFORM_GOOGLE_SERVICE_ACCOUNT_PATH`.
Share the required Drive folders with the service account as Viewer.

Duro BOM and component reads use the REST API and its `apiToken` header. Put the raw API key in
`duro-api-key.txt` in this directory, or configure it in `apps/backend/.env`:

```dotenv
PRODUCTION_PLATFORM_DURO_API_KEY=...
```

The key file and `.env` file are ignored by git. The key file is read for each Duro request,
so it can be rotated without restarting the backend. Duro authentication is API Key only;
the backend does not start a browser or retain browser cookies. Override its location with
`PRODUCTION_PLATFORM_DURO_API_KEY_PATH`, or override the REST base URL with
`PRODUCTION_PLATFORM_DURO_BASE_URL`. The product catalog falls back to the legacy GraphQL
catalog query when the API key lacks Duro's REST product-search permission.

## Bridgefloods GPT token

The Bridge token module uses these git-ignored files in this directory:

- `bridgefloods.env`: Bridge access/refresh credentials and email settings.
- `bridgefloods_whitelist.csv`: enabled users, key matching, and reminder recipients.
- `bridge-gmail-token.json`: Gmail OAuth state used for reminders and administrator alerts.
- `bridge-main-balance-alert-state.json`: state retained from the standalone automation migration.

Keep every file at mode `600`. `bridgefloods.env` must contain a non-empty
`BRIDGEFLOODS_ACCESS_TOKEN` or `BRIDGEFLOODS_REFRESH_TOKEN`; variable names without values do
not configure the service. The application-level paths are set in `apps/backend/.env`.
