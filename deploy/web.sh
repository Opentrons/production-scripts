#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_ROOT="$REPOSITORY_ROOT/apps/web-ui"
API_PORT="${API_PORT:-8090}"
WEB_HTTP_PORT="${WEB_HTTP_PORT:-80}"
WEB_HTTPS_PORT="${WEB_HTTPS_PORT:-443}"
WEB_ENABLE_HTTPS="${WEB_ENABLE_HTTPS:-true}"
SERVER_NAME="${SERVER_NAME:-_}"
SSL_CERTIFICATE="${SSL_CERTIFICATE:-}"
SSL_CERTIFICATE_KEY="${SSL_CERTIFICATE_KEY:-}"
SITE_NAME="production-web-ui"

if [ "$(id -u)" -ne 0 ]; then
    echo "web.sh must run as root"
    exit 1
fi

if [ "$WEB_ENABLE_HTTPS" = "true" ]; then
    if [ -z "$SSL_CERTIFICATE" ] || [ -z "$SSL_CERTIFICATE_KEY" ]; then
        echo "SSL_CERTIFICATE and SSL_CERTIFICATE_KEY are required when WEB_ENABLE_HTTPS=true"
        exit 1
    fi
    if [ ! -f "$SSL_CERTIFICATE" ] || [ ! -f "$SSL_CERTIFICATE_KEY" ]; then
        echo "Configured TLS certificate or private key does not exist"
        exit 1
    fi
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

write_proxy_headers() {
    cat <<EOF
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_buffering off;
EOF
}

if [ "$WEB_ENABLE_HTTPS" = "true" ]; then
    {
        cat <<EOF
limit_req_zone \$binary_remote_addr zone=production_auth_login:10m rate=5r/m;

server {
    listen $WEB_HTTP_PORT;
    server_name $SERVER_NAME;
    return 301 https://\$host\$request_uri;
}

server {
    listen $WEB_HTTPS_PORT ssl;
    server_name $SERVER_NAME;
    root $WEB_ROOT/dist;
    index index.html;
    client_max_body_size 200m;
    server_tokens off;

    ssl_certificate $SSL_CERTIFICATE;
    ssl_certificate_key $SSL_CERTIFICATE_KEY;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:ProductionTLS:10m;
    ssl_session_timeout 1d;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "same-origin" always;

    location = /_auth {
        internal;
        proxy_pass http://127.0.0.1:$API_PORT/api/auth/verify;
        proxy_pass_request_body off;
        proxy_set_header Content-Length "";
EOF
        write_proxy_headers
        cat <<EOF
    }

    location = /api/auth/login {
        limit_req zone=production_auth_login burst=5 nodelay;
        proxy_pass http://127.0.0.1:$API_PORT;
EOF
        write_proxy_headers
        cat <<EOF
    }

    location /api/ {
        proxy_pass http://127.0.0.1:$API_PORT;
EOF
        write_proxy_headers
        cat <<EOF
    }

    location = /login {
        try_files /index.html =404;
    }

    location = /index.html {
        add_header Cache-Control "no-store";
    }

    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        try_files \$uri =404;
    }

    location ~ ^/(favicon\.png|versions-favicon\.svg|icons\.svg)$ {
        try_files \$uri =404;
    }

    location @login_redirect {
        return 302 /login?redirect=\$uri;
    }

    location / {
        auth_request /_auth;
        error_page 401 = @login_redirect;
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
    } > "$SITE_FILE"
else
    cat > "$SITE_FILE" <<EOF
server {
    listen $WEB_HTTP_PORT;
    server_name $SERVER_NAME;
    root $WEB_ROOT/dist;
    index index.html;
    client_max_body_size 200m;

    location /api/ {
        proxy_pass http://127.0.0.1:$API_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_buffering off;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
fi

if [ -n "$ENABLED_FILE" ]; then
    ln -sfn "$SITE_FILE" "$ENABLED_FILE"
fi

nginx -t
systemctl reload nginx
if [ "$WEB_ENABLE_HTTPS" = "true" ]; then
    echo "Web deployed at https://$SERVER_NAME:$WEB_HTTPS_PORT"
else
    echo "WARNING: Web deployed without HTTPS at http://$SERVER_NAME:$WEB_HTTP_PORT"
fi
