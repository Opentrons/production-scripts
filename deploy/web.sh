#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_ROOT="$REPOSITORY_ROOT/apps/web-ui"
WEB_PORT="${WEB_PORT:-80}"
API_PORT="${API_PORT:-8090}"
SITE_NAME="production-web-ui"

if [ "$(id -u)" -ne 0 ]; then
    echo "web.sh must run as root"
    exit 1
fi

cd "$WEB_ROOT"
npm ci
npm run build

if [ -d /etc/nginx/sites-available ]; then
    SITE_FILE="/etc/nginx/sites-available/$SITE_NAME"
    ENABLED_FILE="/etc/nginx/sites-enabled/$SITE_NAME"
else
    mkdir -p /etc/nginx/conf.d
    SITE_FILE="/etc/nginx/conf.d/$SITE_NAME.conf"
    ENABLED_FILE=""
fi

cat > "$SITE_FILE" <<EOF
server {
    listen $WEB_PORT;
    server_name _;
    root $WEB_ROOT/dist;
    index index.html;
    client_max_body_size 200m;

    location /api/ {
        proxy_pass http://127.0.0.1:$API_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

if [ -n "$ENABLED_FILE" ]; then
    ln -sfn "$SITE_FILE" "$ENABLED_FILE"
fi

nginx -t
systemctl reload nginx
echo "Web deployed on port $WEB_PORT"
