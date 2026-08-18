#!/usr/bin/env bash

set -euo pipefail

SERVICE_NAME="production-backend"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_ROOT="$REPOSITORY_ROOT/apps/backend"
API_PORT="${API_PORT:-8090}"
UV_BIN="${UV_BIN:-$(command -v uv)}"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
AUTH_ENV_FILE="${AUTH_ENV_FILE:-/etc/production-platform.env}"
AUTH_COOKIE_SECURE="${AUTH_COOKIE_SECURE:-true}"
AUTH_REFRESH_TOKEN_HOURS="${AUTH_REFRESH_TOKEN_HOURS:-1}"
AUTH_ACCESS_TOKEN_MINUTES="${AUTH_ACCESS_TOKEN_MINUTES:-5}"
VERSION_SOURCE="$REPOSITORY_ROOT/apps/version.json"
VERSION_FILE="$API_ROOT/data/app-version.json"

if [ "$(id -u)" -ne 0 ]; then
    echo "backend.sh must run as root"
    exit 1
fi

mkdir -p "$API_ROOT/data" "$API_ROOT/auth-files" "$API_ROOT/db-storage/auth"

touch "$AUTH_ENV_FILE"
chmod 600 "$AUTH_ENV_FILE"
if ! grep -Eq '^PRODUCTION_PLATFORM_AUTH_JWT_SECRET=.{32,}$' "$AUTH_ENV_FILE"; then
    if ! command -v openssl >/dev/null 2>&1; then
        echo "openssl is required to generate the platform JWT secret"
        exit 1
    fi
    echo "PRODUCTION_PLATFORM_AUTH_JWT_SECRET=$(openssl rand -hex 32)" >> "$AUTH_ENV_FILE"
fi
if ! grep -Eq '^PRODUCTION_PLATFORM_COLLECTION_DATA_ACCESS_TOKEN=.{32,}$' "$AUTH_ENV_FILE"; then
    if ! command -v openssl >/dev/null 2>&1; then
        echo "openssl is required to generate the collection data access token"
        exit 1
    fi
    COLLECTION_DATA_ACCESS_TOKEN="$(openssl rand -hex 32)"
    if grep -q '^PRODUCTION_PLATFORM_COLLECTION_DATA_ACCESS_TOKEN=' "$AUTH_ENV_FILE"; then
        sed -i "s/^PRODUCTION_PLATFORM_COLLECTION_DATA_ACCESS_TOKEN=.*/PRODUCTION_PLATFORM_COLLECTION_DATA_ACCESS_TOKEN=$COLLECTION_DATA_ACCESS_TOKEN/" "$AUTH_ENV_FILE"
    else
        echo "PRODUCTION_PLATFORM_COLLECTION_DATA_ACCESS_TOKEN=$COLLECTION_DATA_ACCESS_TOKEN" >> "$AUTH_ENV_FILE"
    fi
    unset COLLECTION_DATA_ACCESS_TOKEN
fi
if ! [[ "$AUTH_REFRESH_TOKEN_HOURS" =~ ^[1-9][0-9]*$ ]]; then
    echo "AUTH_REFRESH_TOKEN_HOURS must be a positive integer"
    exit 1
fi
if ! [[ "$AUTH_ACCESS_TOKEN_MINUTES" =~ ^[1-9][0-9]*$ ]]; then
    echo "AUTH_ACCESS_TOKEN_MINUTES must be a positive integer"
    exit 1
fi
if grep -q '^PRODUCTION_PLATFORM_AUTH_REFRESH_TOKEN_HOURS=' "$AUTH_ENV_FILE"; then
    sed -i "s/^PRODUCTION_PLATFORM_AUTH_REFRESH_TOKEN_HOURS=.*/PRODUCTION_PLATFORM_AUTH_REFRESH_TOKEN_HOURS=$AUTH_REFRESH_TOKEN_HOURS/" "$AUTH_ENV_FILE"
else
    echo "PRODUCTION_PLATFORM_AUTH_REFRESH_TOKEN_HOURS=$AUTH_REFRESH_TOKEN_HOURS" >> "$AUTH_ENV_FILE"
fi
if grep -q '^PRODUCTION_PLATFORM_AUTH_ACCESS_TOKEN_MINUTES=' "$AUTH_ENV_FILE"; then
    sed -i "s/^PRODUCTION_PLATFORM_AUTH_ACCESS_TOKEN_MINUTES=.*/PRODUCTION_PLATFORM_AUTH_ACCESS_TOKEN_MINUTES=$AUTH_ACCESS_TOKEN_MINUTES/" "$AUTH_ENV_FILE"
else
    echo "PRODUCTION_PLATFORM_AUTH_ACCESS_TOKEN_MINUTES=$AUTH_ACCESS_TOKEN_MINUTES" >> "$AUTH_ENV_FILE"
fi

cd "$REPOSITORY_ROOT"
"$UV_BIN" sync --frozen --package production-backend

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Productions testing API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$REPOSITORY_ROOT
Environment=PRODUCTION_PLATFORM_DATA_DIR=$API_ROOT/data
Environment=PRODUCTION_PLATFORM_REFRESH_PROXY_ON_STARTUP=false
EnvironmentFile=$AUTH_ENV_FILE
Environment=PRODUCTION_PLATFORM_RUN_ENV=server
Environment=PRODUCTION_PLATFORM_AUTH_STORAGE=mongodb
Environment=PRODUCTION_PLATFORM_DEVICE_SCAN_MODE=real
Environment=PRODUCTION_PLATFORM_AUTH_COOKIE_SECURE=$AUTH_COOKIE_SECURE
Environment=PYTHONUNBUFFERED=1
ExecStart=$UV_BIN run --package production-backend uvicorn app:app --host 127.0.0.1 --port $API_PORT
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
systemctl --no-pager status "$SERVICE_NAME"
python3 "$SCRIPT_DIR/update_version.py" --path "$VERSION_FILE" --source "$VERSION_SOURCE" --repository "$REPOSITORY_ROOT"

echo "Backend deployed on port $API_PORT"
echo "Local runtime data preserved under $API_ROOT/data and $API_ROOT/db-storage"
echo "Non-simulating authentication and business documents use MongoDB ProductionsMessage"
echo "Create the first account with:"
echo "  cd $REPOSITORY_ROOT && sudo $UV_BIN run --package production-backend python apps/backend/scripts/create_auth_user.py --username admin --role admin"
