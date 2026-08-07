# Google credentials

Put `credentials.json` and `token.json` in this directory. These files are ignored by git. Override the location with `PRODUCTIONS_VERSIONS_GOOGLE_AUTH_DIR` when credentials are mounted externally.

Duro server access should preferably use the API key in `apps/api/.env`:

```dotenv
DURO_API_KEY=...
```

The `.env` file is ignored by git. An explicitly exported `PRODUCTIONS_VERSIONS_DURO_TOKEN` temporarily takes precedence (useful for debugging); if neither is configured, the backend falls back to the raw bearer token in `duro_token.txt`. Short-lived access tokens are rejected after their JWT expiry. Rotating `DURO_API_KEY` requires restarting the backend process so the new environment is loaded.

As a fallback, the backend can read `cookies.txt` exported from `auth.duro.app`. Browser-extension JSON exports, Netscape cookies.txt exports, and a raw `Cookie` request header such as `refresh_token=...; other_cookie=...` are supported. The export must include the HttpOnly authentication/session cookies; analytics-only cookies such as FullStory or Datadog cannot refresh a Duro access token. When Duro rejects the configured credential, the backend calls `https://auth.duro.app/api/v1/refresh_token`, caches the returned access token, and retries the original request once. If Duro rotates the refresh cookie, the replacement is written atomically back to `cookies.txt` with mode `0600`.

`cookies.txt` is ignored by git and must be handled like a password. It can be relocated with `PRODUCTIONS_VERSIONS_DURO_COOKIES_PATH`.

## Remote Chrome authentication

For browser-bound Duro sessions, start a dedicated Chrome with CDP and log in once:

```bash
make remote-chrome
```

The default CDP endpoint is `http://127.0.0.1:9222` and its persistent profile is stored under the git-ignored `apps/api/auth/duro-chrome-profile`. Configure the API with:

```dotenv
PRODUCTIONS_VERSIONS_DURO_REMOTE_CHROME_URL=http://127.0.0.1:9222
```

The backend connects with Playwright over CDP, executes Duro's refresh request inside the logged-in page, caches the returned access token, and refreshes it before expiry. The backend does not close the remote Chrome process. Keep the CDP port bound to localhost or a protected private network because CDP grants full control of the browser profile.
