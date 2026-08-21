# Platform authentication

Production Testing, Productions Versions, the Dashboard, Downloads, and the Production Agent use one FastAPI login session.

Persistence follows the platform rule:

- Non-simulating → MongoDB `ProductionsMessage.auth_users` / `auth_sessions`
- Simulating → SQLite under `db-storage/simulating/auth.sqlite3` (or `PRODUCTION_PLATFORM_AUTH_DB_PATH`)

Migrate legacy production `db-storage/auth/auth.sqlite3` into MongoDB with `apps/backend/scripts/migrate_sqlite_to_mongodb.py` before removing the sqlite file.

## First deployment

Deploy the backend first. The deployment script creates `/etc/production-platform.env`, generates a persistent JWT secret when necessary, and restricts Uvicorn to `127.0.0.1`.

```bash
make deploy-backend
sudo "$(command -v uv)" run --package production-backend python apps/backend/scripts/create_auth_user.py \
  --username admin \
  --role admin
```

The command prompts for a password and requires at least 12 characters. Available roles are `admin`, `operator`, `viewer`, and `device_operator`.

`device_operator` is the standard production-floor role. It can use the dashboard and all platform modules except the device control page. The web application blocks `/devices/control` with a permission-controlled dialog. The API independently returns HTTP 403 for `/api/robots/{ip}/control/*` while allowing other authenticated platform endpoints.

```bash
sudo "$(command -v uv)" run --package production-backend python apps/backend/scripts/create_auth_user.py \
  --username device_control \
  --display-name '普通用户' \
  --role device_operator
```

Configure a domain or fixed-IP certificate before deploying Nginx:

```bash
sudo SERVER_NAME=productions.example.com \
  SSL_CERTIFICATE=/etc/letsencrypt/live/productions.example.com/fullchain.pem \
  SSL_CERTIFICATE_KEY=/etc/letsencrypt/live/productions.example.com/privkey.pem \
  bash deploy/web.sh
```

Port 80 only redirects to HTTPS. Do not expose backend port 8090 through the router or host firewall.

For explicitly local HTTP-only testing, set both `WEB_ENABLE_HTTPS=false` for Nginx and `PRODUCTION_PLATFORM_AUTH_COOKIE_SECURE=false` for the backend. Never use that configuration on a public interface.

## Configuration

Authentication environment variables:

```text
PRODUCTION_PLATFORM_AUTH_JWT_SECRET=<at least 32 random characters>
PRODUCTION_PLATFORM_AUTH_ACCESS_TOKEN_MINUTES=5
PRODUCTION_PLATFORM_AUTH_REFRESH_TOKEN_HOURS=24
PRODUCTION_PLATFORM_AUTH_COOKIE_SECURE=true
PRODUCTION_PLATFORM_AUTH_DB_PATH=<optional absolute sqlite path for simulating mode>
PRODUCTION_PLATFORM_AUTH_ALLOWED_ORIGINS=<optional comma-separated origins>
```

JWTs are held in HttpOnly cookies. State-changing cookie-authenticated API requests also require the session CSRF header. Access JWTs expire after 5 minutes by default while the login session remains valid. The login session expires after 24 hours by default, then the web client requires a new login. Refresh tokens are rotated, and logout revokes the server-side session immediately.
