#!/bin/bash

set -euo pipefail

PORT="8091"
SITE_NAME="data-handler-web-ui"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$SCRIPT_DIR/dist"
OLD_SERVICE_NAME="data-app"

echo "=========================================="
echo "Starting web_ui deployment..."
echo "Web root: $WEB_ROOT"
echo "=========================================="

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: deploy.sh must run as root"
    exit 1
fi

run_if_exists() {
    "$@" >/dev/null 2>&1 || true
}

install_package() {
    local package_name="$1"
    if command -v apt-get >/dev/null 2>&1; then
        apt-get update
        DEBIAN_FRONTEND=noninteractive apt-get install -y "$package_name"
    elif command -v dnf >/dev/null 2>&1; then
        dnf install -y "$package_name"
    elif command -v yum >/dev/null 2>&1; then
        yum install -y "$package_name"
    elif command -v apk >/dev/null 2>&1; then
        apk add --no-cache "$package_name"
    else
        echo "Error: no supported package manager found to install ${package_name}"
        return 1
    fi
}

ensure_dist() {
    if [ ! -f "$WEB_ROOT/index.html" ]; then
        echo "Error: dist index.html not found at $WEB_ROOT/index.html"
        exit 1
    fi
}

stop_old_data_app_service() {
    echo "Stopping old ${OLD_SERVICE_NAME} service if present..."
    if systemctl list-unit-files "${OLD_SERVICE_NAME}.service" 2>/dev/null | grep -q "^${OLD_SERVICE_NAME}\\.service" \
        || [ -f "/etc/systemd/system/${OLD_SERVICE_NAME}.service" ]; then
        run_if_exists systemctl stop "$OLD_SERVICE_NAME"
        run_if_exists systemctl disable "$OLD_SERVICE_NAME"
    fi

    rm -f "/etc/systemd/system/${OLD_SERVICE_NAME}.service"
    rm -f "/lib/systemd/system/${OLD_SERVICE_NAME}.service"
    rm -f "/usr/lib/systemd/system/${OLD_SERVICE_NAME}.service"
    systemctl daemon-reload
    run_if_exists systemctl reset-failed "$OLD_SERVICE_NAME"
}

ensure_nginx() {
    echo "Checking nginx..."
    if command -v nginx >/dev/null 2>&1; then
        echo "nginx is already installed: $(nginx -v 2>&1)"
        return
    fi

    echo "nginx is not installed. Installing nginx..."
    install_package nginx
}

is_nginx_pid() {
    local pid="$1"
    local command_name=""
    command_name="$(ps -p "$pid" -o comm= 2>/dev/null | tr -d '[:space:]' || true)"
    [ "$command_name" = "nginx" ]
}

kill_non_nginx_port_processes() {
    local pids=""
    local pid=""
    local kill_pids=""
    local nginx_pids=""

    echo "Checking port ${PORT}..."
    if command -v lsof >/dev/null 2>&1; then
        pids="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
    fi
    if [ -z "$pids" ] && command -v fuser >/dev/null 2>&1; then
        pids="$(fuser -n tcp "$PORT" 2>/dev/null || true)"
    fi
    if [ -z "$pids" ] && command -v ss >/dev/null 2>&1; then
        pids="$(ss -ltnp "sport = :$PORT" 2>/dev/null | sed -nE 's/.*pid=([0-9]+).*/\1/p' | sort -u || true)"
    fi

    if [ -z "$pids" ]; then
        echo "No process is listening on port ${PORT}."
        return
    fi

    for pid in $pids; do
        if is_nginx_pid "$pid"; then
            nginx_pids="$nginx_pids $pid"
        else
            kill_pids="$kill_pids $pid"
        fi
    done

    if [ -n "$nginx_pids" ]; then
        echo "Port ${PORT} is already handled by nginx; preserving nginx process(es)."
    fi

    if [ -z "$kill_pids" ]; then
        return
    fi

    echo "Killing non-nginx process(es) on port ${PORT}:$kill_pids"
    kill $kill_pids 2>/dev/null || true
    sleep 2

    local alive=""
    for pid in $kill_pids; do
        if kill -0 "$pid" 2>/dev/null; then
            alive="$alive $pid"
        fi
    done

    if [ -n "$alive" ]; then
        echo "Force killing process(es):$alive"
        kill -9 $alive 2>/dev/null || true
    fi
}

find_existing_nginx_site() {
    local search_dirs=()
    [ -d /etc/nginx/sites-available ] && search_dirs+=("/etc/nginx/sites-available")
    [ -d /etc/nginx/conf.d ] && search_dirs+=("/etc/nginx/conf.d")

    if [ "${#search_dirs[@]}" -eq 0 ]; then
        return 1
    fi

    grep -RIlE "listen[[:space:]]+[^;]*${PORT}[^0-9;]*;" "${search_dirs[@]}" 2>/dev/null | head -n 1
}

nginx_site_file() {
    local existing=""
    existing="$(find_existing_nginx_site || true)"
    if [ -n "$existing" ]; then
        echo "$existing"
        return
    fi

    if [ -d /etc/nginx/sites-available ]; then
        echo "/etc/nginx/sites-available/${SITE_NAME}"
    else
        mkdir -p /etc/nginx/conf.d
        echo "/etc/nginx/conf.d/${SITE_NAME}.conf"
    fi
}

write_nginx_site() {
    local site_file="$1"

    echo "Writing nginx site config: $site_file"
    cat > "$site_file" << EOF
server {
    listen ${PORT};
    server_name _;

    root ${WEB_ROOT};
    index index.html;
    client_max_body_size 200m;

    location /api/ {
        proxy_pass http://127.0.0.1:8090;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

    if [ -d /etc/nginx/sites-enabled ] && [[ "$site_file" == /etc/nginx/sites-available/* ]]; then
        ln -sfn "$site_file" "/etc/nginx/sites-enabled/$(basename "$site_file")"
    fi
}

reload_nginx() {
    nginx -t
    if systemctl list-unit-files nginx.service 2>/dev/null | grep -q '^nginx\.service'; then
        run_if_exists systemctl enable nginx
        systemctl reload nginx || systemctl restart nginx
        echo "nginx status: $(systemctl is-active nginx 2>/dev/null || echo unknown)"
    else
        nginx -s reload || nginx
    fi
}

show_port_status() {
    echo "Port ${PORT} status:"
    if command -v ss >/dev/null 2>&1; then
        ss -ltnp "sport = :${PORT}" || true
    elif command -v lsof >/dev/null 2>&1; then
        lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN || true
    else
        echo "No ss/lsof command available for port status."
    fi
}

ensure_dist
stop_old_data_app_service
ensure_nginx
kill_non_nginx_port_processes
SITE_FILE="$(nginx_site_file)"
write_nginx_site "$SITE_FILE"
reload_nginx
show_port_status

echo ""
echo "=========================================="
echo "web_ui deployment completed!"
echo "=========================================="
echo "web_ui service: http://localhost:${PORT}"
