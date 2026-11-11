# Platform authentication

Production Testing, Productions Versions, the Dashboard, Downloads, and the Production Agent use one FastAPI login session.

Authentication persistence is controlled independently of business simulation by
`PRODUCTION_PLATFORM_AUTH_STORAGE`:

- `mongodb` (production default): `ProductionsMessage.auth_users` / `auth_sessions`.
- `sqlite` (local development default): `PRODUCTION_PLATFORM_AUTH_DB_PATH` or `db-storage/auth/auth.sqlite3`.

Accounts, password changes, and roles use the existing store directly. No JSON
copy is maintained. Passwords are stored as Argon2 hashes, never plaintext.

Migrate legacy production `db-storage/auth/auth.sqlite3` into MongoDB with `apps/backend/scripts/migrate_sqlite_to_mongodb.py` before removing the sqlite file.

## First deployment

Deploy the backend first. The deployment script creates `/etc/production-platform.env`, generates a persistent JWT secret when necessary, and restricts Uvicorn to `127.0.0.1`.

```bash
make deploy-backend
sudo "$(command -v uv)" run --package production-backend python apps/backend/scripts/create_auth_user.py \
  --username admin \
  --role admin
```

The command prompts for a password and requires at least 12 characters. Available roles are `admin`, `engineer`, `operator`, and `guest`; legacy `viewer` and `device_operator` roles remain supported.

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
PRODUCTION_PLATFORM_AUTH_REFRESH_TOKEN_HOURS=360
PRODUCTION_PLATFORM_AUTH_COOKIE_SECURE=true
PRODUCTION_PLATFORM_AUTH_DB_PATH=<optional absolute sqlite path for simulating mode>
PRODUCTION_PLATFORM_AUTH_ALLOWED_ORIGINS=<optional comma-separated origins>
```

JWTs are held in HttpOnly cookies. State-changing cookie-authenticated API requests also require the session CSRF header. Access JWTs expire after 5 minutes by default while the login session remains valid. The login session expires after 360 hours (15 days) by default, then the web client requires a new login. Refresh tokens are rotated, and logout revokes the server-side session immediately.

## Account management and initial administrators

Administrators open **Settings → Account management** to list accounts, add an
email account, or change a role. The API independently checks administrator
access and CSRF protection. Emails are unique without regard to capitalization.
Google Workspace addresses such as `@opentrons.com` are supported; this is
email/password authentication, not Google OAuth.

On authentication initialization, the following missing accounts are created
as administrators:

- `Jerome.li@opentrons.com`
- `Frank.zhang@opentrons.com`
- `zane.wang@opentrons.com`
- `andy.hu@opentrons.com`
- `kevin.jiang@opentrons.com`

The initial password is the part before `@`, preserving the entered case
(for example, `Jerome.li`). Existing accounts, passwords, and role assignments
are preserved on restart. Newly added accounts follow the same initial-password
rule. Users can change this password with the login page's **Reset password**
action. New passwords require at least 12 characters.

Changing a role or password invalidates all existing access and refresh tokens
for that account. The last enabled administrator cannot be demoted. The four
roles are available for future per-module authorization; this change restricts
account management to administrators and preserves existing device-operator
restrictions. It does not yet make guests read-only across all modules.

## Password recovery email

Configure these environment variables on the backend, then restart it:

```text
PRODUCTION_PLATFORM_SMTP_HOST=smtp.example.com
PRODUCTION_PLATFORM_SMTP_PORT=587
PRODUCTION_PLATFORM_SMTP_FROM=software.sz@opentrons.com
PRODUCTION_PLATFORM_SMTP_USERNAME=software.sz@opentrons.com
PRODUCTION_PLATFORM_SMTP_PASSWORD=<SMTP credential or app password>
```

Port 587 uses STARTTLS; port 465 uses implicit TLS. Both verify the server
certificate. Account emails always use `software.sz@opentrons.com`. A different
`PRODUCTION_PLATFORM_SMTP_FROM` value is rejected before sending. Configure SMTP
credentials for this mailbox, or a relay explicitly authorized to send as it.
Do not reuse another personal mailbox's Gmail token. Changing the From header
does not grant send-as permission. This feature does
not need access to a user's Google password or Google OAuth token.

Codes expire after 10 minutes, can be used once, and allow at most five
verification attempts. Requests are limited per email and source IP, with a
60-second resend cooldown. MongoDB stores recovery digests and limits in
`auth_password_resets` and `auth_reset_rates` with TTL indexes; SQLite stores
them in corresponding tables. Codes are HMAC-hashed using the configured JWT
secret and are never returned through the API. A missing mail configuration
returns HTTP 503 without changing any password. Mail delivery failures invalidate
the affected code. Normal responses do not disclose whether an email exists.

API endpoints (under `/api/auth`):

- `GET /accounts`, `POST /accounts`, `PATCH /accounts/{id}`: administrators only.
- `POST /password-reset/request`: `{ "email": "user@example.com" }`.
- `POST /password-reset/confirm`: `{ "email": "user@example.com", "code": "123456", "password": "a-new-long-password" }`.

Run the regression tests with `uv run --package production-backend pytest
apps/backend/tests/test_auth.py apps/backend/tests/test_accounts.py
apps/backend/tests/test_storage_modes.py`. MongoDB store tests use `mongomock`;
live SMTP delivery and production MongoDB are not exercised by these tests.
