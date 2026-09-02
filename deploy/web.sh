#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_ROOT="$REPOSITORY_ROOT/apps/web-ui"
API_PORT="${API_PORT:-8090}"
WEB_HTTP_PORT="${WEB_HTTP_PORT:-80}"
WEB_HTTPS_PORT="${WEB_HTTPS_PORT:-443}"
DATA_CENTER_HTTP_PORT="${DATA_CENTER_HTTP_PORT:-}"
DATA_CENTER_ALLOWED_CIDRS="${DATA_CENTER_ALLOWED_CIDRS:-}"
WEB_ENABLE_HTTPS="${WEB_ENABLE_HTTPS:-true}"
WEB_SKIP_BUILD="${WEB_SKIP_BUILD:-false}"
SERVER_NAME="${SERVER_NAME:-_}"
SSL_CERTIFICATE="${SSL_CERTIFICATE:-}"
SSL_CERTIFICATE_KEY="${SSL_CERTIFICATE_KEY:-}"
SITE_NAME="production-web-ui"
DATA_CENTER_SITE_NAME="production-data-center-client"
VERSION_SOURCE="$REPOSITORY_ROOT/apps/version.json"
VERSION_FILE="$REPOSITORY_ROOT/apps/backend/data/app-version.json"

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
if [ "$WEB_SKIP_BUILD" = "true" ]; then
    if [ ! -f "$WEB_ROOT/dist/index.html" ]; then
        echo "WEB_SKIP_BUILD=true requires a prebuilt dist/index.html"
        exit 1
    fi
    echo "Using prebuilt web assets from $WEB_ROOT/dist"
else
    npm ci
    npm run build
fi

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

write_data_center_client_locations() {
    local require_auth="$1"
    local endpoint
    for endpoint in /api/health /api/pull-folder /api/upload-data /api/upload-data/manual; do
        cat <<EOF
    location = $endpoint {
EOF
        if [ "$require_auth" = "true" ]; then
            cat <<'EOF'
        auth_request /_auth;
EOF
        fi
        cat <<EOF
        proxy_pass http://127.0.0.1:$API_PORT;
EOF
        write_proxy_headers
        cat <<'EOF'
    }

EOF
    done
}

data_center_allow_directives=""
if [ -n "$DATA_CENTER_HTTP_PORT" ]; then
    if [[ ! "$DATA_CENTER_HTTP_PORT" =~ ^[0-9]+$ ]] || (( DATA_CENTER_HTTP_PORT < 1 || DATA_CENTER_HTTP_PORT > 65535 )); then
        echo "DATA_CENTER_HTTP_PORT must be a valid TCP port"
        exit 1
    fi
    if [ "$DATA_CENTER_HTTP_PORT" = "$API_PORT" ]; then
        echo "DATA_CENTER_HTTP_PORT must differ from API_PORT"
        exit 1
    fi
    if [ -z "$DATA_CENTER_ALLOWED_CIDRS" ]; then
        echo "DATA_CENTER_ALLOWED_CIDRS is required when DATA_CENTER_HTTP_PORT is set"
        exit 1
    fi
    IFS=',' read -r -a data_center_cidrs <<< "$DATA_CENTER_ALLOWED_CIDRS"
    for cidr in "${data_center_cidrs[@]}"; do
        if [[ ! "$cidr" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}/([0-9]|[12][0-9]|3[0-2])$ ]]; then
            echo "Invalid DATA_CENTER_ALLOWED_CIDRS entry: $cidr"
            exit 1
        fi
        data_center_allow_directives+="    allow $cidr;\n"
    done
fi

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
    absolute_redirect off;
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

EOF
        write_data_center_client_locations true
        cat <<EOF
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

    location /agent-media/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        try_files \$uri =404;
    }

    location ~ ^/(favicon\.png|agent-favicon\.svg|testing-favicon\.svg|versions-favicon\.svg|icons\.svg)$ {
        try_files \$uri =404;
    }

    location / {
        # Serve the SPA before authentication so its refresh-token flow can
        # renew an expired short-lived access cookie. FastAPI still protects
        # every non-public API route.
        # Do not use \$uri/ — a public/ folder matching a Vue route (e.g. /agent)
        # would otherwise 403 as a directory index instead of serving the SPA.
        try_files \$uri /index.html;
    }
}
EOF
    } > "$SITE_FILE"
else
    {
        cat <<EOF
limit_req_zone \$binary_remote_addr zone=production_auth_login:10m rate=5r/m;

server {
    listen $WEB_HTTP_PORT;
    server_name $SERVER_NAME;
    absolute_redirect off;
    root $WEB_ROOT/dist;
    index index.html;
    client_max_body_size 200m;

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

EOF
        write_data_center_client_locations true
        cat <<EOF
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

    location /agent-media/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        try_files \$uri =404;
    }

    location ~ ^/(favicon\.png|agent-favicon\.svg|testing-favicon\.svg|versions-favicon\.svg|icons\.svg)$ {
        try_files \$uri =404;
    }

    location / {
        # Authentication and access-cookie renewal are handled by the SPA and
        # FastAPI. Nginx must not redirect before refresh-token recovery runs.
        # Do not use \$uri/ — avoids 403 when a static folder collides with a SPA route.
        try_files \$uri /index.html;
    }
}
EOF
    } > "$SITE_FILE"
fi

if [ -n "$ENABLED_FILE" ]; then
    ln -sfn "$SITE_FILE" "$ENABLED_FILE"
fi

if [ -n "$DATA_CENTER_HTTP_PORT" ]; then
    if [ -d /etc/nginx/sites-available ]; then
        DATA_CENTER_SITE_FILE="/etc/nginx/sites-available/$DATA_CENTER_SITE_NAME"
        DATA_CENTER_ENABLED_FILE="/etc/nginx/sites-enabled/$DATA_CENTER_SITE_NAME"
    else
        DATA_CENTER_SITE_FILE="/etc/nginx/conf.d/$DATA_CENTER_SITE_NAME.conf"
        DATA_CENTER_ENABLED_FILE=""
    fi

    {
        cat <<EOF
server {
    listen $DATA_CENTER_HTTP_PORT;
    server_name _;
    client_max_body_size 200m;
    server_tokens off;

    allow 127.0.0.1;
    allow ::1;
EOF
        printf '%b' "$data_center_allow_directives"
        cat <<'EOF'
    deny all;

EOF
        write_data_center_client_locations false
        cat <<'EOF'
    location / {
        return 404;
    }
}
EOF
    } > "$DATA_CENTER_SITE_FILE"

    if [ -n "$DATA_CENTER_ENABLED_FILE" ]; then
        ln -sfn "$DATA_CENTER_SITE_FILE" "$DATA_CENTER_ENABLED_FILE"
    fi
fi

nginx -t
systemctl reload nginx
python3 "$SCRIPT_DIR/update_version.py" --path "$VERSION_FILE" --source "$VERSION_SOURCE" --repository "$REPOSITORY_ROOT"
if [ "$WEB_ENABLE_HTTPS" = "true" ]; then
    echo "Web deployed at https://$SERVER_NAME:$WEB_HTTPS_PORT"
else
    echo "WARNING: Web deployed without HTTPS at http://$SERVER_NAME:$WEB_HTTP_PORT"
fi
