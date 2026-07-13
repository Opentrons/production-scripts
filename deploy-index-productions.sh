#!/bin/bash

set -euo pipefail

INDEX_PORT="${INDEX_PORT:-80}"
OPENTRONS_PORT="${OPENTRONS_PORT:-8091}"
OPENTRONS_API_PORT="${OPENTRONS_API_PORT:-8090}"
OPENTRONS_PATH="${OPENTRONS_PATH:-/opentrons-productions}"
LEGACY_OPENTRONS_PATH="${LEGACY_OPENTRONS_PATH:-/opetrons-productions}"
SITE_NAME="productions-index"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$SCRIPT_DIR/dist"
OLD_DATA_CENTER_SERVICE_NAME="data-center"

echo "=========================================="
echo "Starting index-productions deployment..."
echo "Web root: $WEB_ROOT"
echo "Index port: $INDEX_PORT"
echo "Opentrons proxy: ${OPENTRONS_PATH}/ -> 127.0.0.1:${OPENTRONS_PORT}"
echo "Opentrons API proxy: /api/ -> 127.0.0.1:${OPENTRONS_API_PORT}"
echo "Legacy proxy path: ${LEGACY_OPENTRONS_PATH}/"
echo "=========================================="

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: deploy.sh must run as root"
    exit 1
fi

run_if_exists() {
    "$@" >/dev/null 2>&1 || true
}

normalize_path() {
    local value="$1"
    value="/${value#/}"
    value="${value%/}"
    if [ "$value" = "/" ]; then
        echo "Error: proxy path cannot be /" >&2
        exit 1
    fi
    printf '%s\n' "$value"
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

ensure_nginx() {
    echo "Checking nginx..."
    if command -v nginx >/dev/null 2>&1; then
        echo "nginx is already installed: $(nginx -v 2>&1)"
        return
    fi

    echo "nginx is not installed. Installing nginx..."
    install_package nginx
}

remove_old_data_center_service() {
    echo "Removing old ${OLD_DATA_CENTER_SERVICE_NAME} service if present..."
    run_if_exists systemctl stop "$OLD_DATA_CENTER_SERVICE_NAME"
    run_if_exists systemctl disable "$OLD_DATA_CENTER_SERVICE_NAME"

    rm -f "/etc/systemd/system/${OLD_DATA_CENTER_SERVICE_NAME}.service"
    rm -f "/lib/systemd/system/${OLD_DATA_CENTER_SERVICE_NAME}.service"
    rm -f "/usr/lib/systemd/system/${OLD_DATA_CENTER_SERVICE_NAME}.service"
    systemctl daemon-reload
    run_if_exists systemctl reset-failed "$OLD_DATA_CENTER_SERVICE_NAME"
}

remove_old_data_center_nginx_block() {
    local nginx_conf="/etc/nginx/nginx.conf"

    if [ ! -f "$nginx_conf" ]; then
        return
    fi

    if ! grep -qE "/opt/web-ui|127\\.0\\.0\\.1:8080|data-center" "$nginx_conf"; then
        echo "No old data-center server block found in $nginx_conf."
        return
    fi

    if ! command -v python3 >/dev/null 2>&1; then
        echo "Warning: python3 not found; skipping old nginx server block cleanup."
        return
    fi

    echo "Removing old data-center server block from $nginx_conf..."
    python3 - <<'PY'
from __future__ import annotations

from datetime import datetime
from pathlib import Path

path = Path("/etc/nginx/nginx.conf")
text = path.read_text()
lines = text.splitlines(keepends=True)
out: list[str] = []
removed = False
i = 0

while i < len(lines):
    stripped = lines[i].strip()
    if stripped == "server {":
        block = [lines[i]]
        j = i + 1
        while j < len(lines):
            block.append(lines[j])
            if lines[j].strip() == "}":
                indent = len(lines[j]) - len(lines[j].lstrip(" \t"))
                if indent <= 4:
                    break
            j += 1

        block_text = "".join(block)
        is_old_data_center = (
            "/opt/web-ui" in block_text
            or "127.0.0.1:8080" in block_text
            or "0.0.0.0:8080" in block_text
        )
        if is_old_data_center:
            removed = True
            i = j + 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            continue

    out.append(lines[i])
    i += 1

new_text = "".join(out)
if removed and new_text != text:
    backup = path.with_suffix(path.suffix + "." + datetime.now().strftime("%Y%m%d%H%M%S") + ".bak")
    backup.write_text(text)
    path.write_text(new_text)
    print(f"Removed old data-center nginx server block. Backup: {backup}")
else:
    print("No old data-center nginx server block removed.")
PY
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

    echo "Checking port ${INDEX_PORT}..."
    if command -v lsof >/dev/null 2>&1; then
        pids="$(lsof -tiTCP:"$INDEX_PORT" -sTCP:LISTEN 2>/dev/null || true)"
    fi
    if [ -z "$pids" ] && command -v fuser >/dev/null 2>&1; then
        pids="$(fuser -n tcp "$INDEX_PORT" 2>/dev/null || true)"
    fi
    if [ -z "$pids" ] && command -v ss >/dev/null 2>&1; then
        pids="$(ss -ltnp "sport = :$INDEX_PORT" 2>/dev/null | sed -nE 's/.*pid=([0-9]+).*/\1/p' | sort -u || true)"
    fi

    if [ -z "$pids" ]; then
        echo "No process is listening on port ${INDEX_PORT}."
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
        echo "Port ${INDEX_PORT} is already handled by nginx; preserving nginx process(es)."
    fi

    if [ -z "$kill_pids" ]; then
        return
    fi

    echo "Killing non-nginx process(es) on port ${INDEX_PORT}:$kill_pids"
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

nginx_site_file() {
    if [ -d /etc/nginx/sites-available ]; then
        echo "/etc/nginx/sites-available/${SITE_NAME}"
    else
        mkdir -p /etc/nginx/conf.d
        echo "/etc/nginx/conf.d/${SITE_NAME}.conf"
    fi
}

disable_default_nginx_site() {
    rm -f /etc/nginx/sites-enabled/default
}

write_nginx_site() {
    local site_file="$1"

    OPENTRONS_PATH="$(normalize_path "$OPENTRONS_PATH")"
    LEGACY_OPENTRONS_PATH="$(normalize_path "$LEGACY_OPENTRONS_PATH")"

    echo "Writing nginx site config: $site_file"
    cat > "$site_file" << EOF
server {
    listen ${INDEX_PORT} default_server;
    server_name _;

    root ${WEB_ROOT};
    index index.html;
    client_max_body_size 200m;

    location = ${LEGACY_OPENTRONS_PATH} {
        return 308 ${OPENTRONS_PATH}/;
    }

    location ^~ ${LEGACY_OPENTRONS_PATH}/ {
        rewrite ^${LEGACY_OPENTRONS_PATH}/(.*)\$ ${OPENTRONS_PATH}/\$1 permanent;
    }

    location = ${OPENTRONS_PATH} {
        return 308 ${OPENTRONS_PATH}/;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:${OPENTRONS_API_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location = /login {
        return 302 /;
    }

    location = /service-worker.js {
        default_type application/javascript;
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate" always;
        return 200 "self.addEventListener('install', function(event) { self.skipWaiting(); }); self.addEventListener('activate', function(event) { event.waitUntil(caches.keys().then(function(keys) { return Promise.all(keys.map(function(key) { return caches.delete(key); })); }).then(function() { return self.registration.unregister(); }).then(function() { return self.clients.matchAll(); }).then(function(clients) { clients.forEach(function(client) { client.navigate(client.url); }); })); });";
    }

    location = /sw.js {
        default_type application/javascript;
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate" always;
        return 200 "self.addEventListener('install', function(event) { self.skipWaiting(); }); self.addEventListener('activate', function(event) { event.waitUntil(caches.keys().then(function(keys) { return Promise.all(keys.map(function(key) { return caches.delete(key); })); }).then(function() { return self.registration.unregister(); }).then(function() { return self.clients.matchAll(); }).then(function(clients) { clients.forEach(function(client) { client.navigate(client.url); }); })); });";
    }

    location ^~ ${OPENTRONS_PATH}/ {
        proxy_pass http://127.0.0.1:${OPENTRONS_PORT}/;
        proxy_http_version 1.1;
        proxy_hide_header Cache-Control;
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate" always;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix ${OPENTRONS_PATH};
        proxy_redirect / ${OPENTRONS_PATH}/;
    }

    location ^~ /assets/ {
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate" always;
        try_files \$uri =404;
    }

    location / {
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate" always;
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
    echo "Port ${INDEX_PORT} status:"
    if command -v ss >/dev/null 2>&1; then
        ss -ltnp "sport = :${INDEX_PORT}" || true
    elif command -v lsof >/dev/null 2>&1; then
        lsof -nP -iTCP:"${INDEX_PORT}" -sTCP:LISTEN || true
    else
        echo "No ss/lsof command available for port status."
    fi
}

ensure_dist
ensure_nginx
remove_old_data_center_service
remove_old_data_center_nginx_block
kill_non_nginx_port_processes
SITE_FILE="$(nginx_site_file)"
disable_default_nginx_site
write_nginx_site "$SITE_FILE"
reload_nginx
show_port_status

echo ""
echo "=========================================="
echo "index-productions deployment completed!"
echo "=========================================="
echo "index-productions service: http://localhost:${INDEX_PORT}"
echo "opentrons-productions proxy: http://localhost:${INDEX_PORT}${OPENTRONS_PATH}/"
