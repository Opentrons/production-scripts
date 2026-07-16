# Google credentials

Put `credentials.json` and `token.json` in this directory for standalone operation. These files are ignored by git.

During local monorepo development, Productions Versions falls back to `productions-opentrons/backend/auth` when local credentials are absent. The directory can also be overridden with `PRODUCTIONS_VERSIONS_GOOGLE_AUTH_DIR`.

Duro access tokens can be supplied with `PRODUCTIONS_VERSIONS_DURO_TOKEN`. For local testing, a raw bearer token may also be stored in `duro_token.txt`; that file is ignored by git. Duro access tokens are short-lived and should not be committed.
