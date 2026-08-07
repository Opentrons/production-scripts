#!/usr/bin/env bash

set -euo pipefail

SERVICE_NAME="production-backend"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_ROOT="$REPOSITORY_ROOT/apps/backend"
API_PORT="${API_PORT:-8090}"
UV_BIN="${UV_BIN:-$(command -v uv)}"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [ "$(id -u)" -ne 0 ]; then
    echo "backend.sh must run as root"
    exit 1
fi

mkdir -p "$API_ROOT/data" "$API_ROOT/auth"
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
Environment=PRODUCTION_PLATFORM_RUN_ENV=server
Environment=PRODUCTION_PLATFORM_DATA_DIR=$API_ROOT/data
Environment=PYTHONUNBUFFERED=1
ExecStart=$UV_BIN run --package production-backend uvicorn app:app --host 0.0.0.0 --port $API_PORT
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
systemctl --no-pager status "$SERVICE_NAME"

echo "Backend deployed on port $API_PORT"
echo "SQLite data preserved in $API_ROOT/data"
