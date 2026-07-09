#!/bin/bash

set -euo pipefail

SERVICE_NAME="data-handler"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PROXY_MONITOR_SERVICE_NAME="data-handler-proxy-monitor"
PROXY_MONITOR_TIMER_NAME="${PROXY_MONITOR_SERVICE_NAME}.timer"
PROXY_MONITOR_SERVICE_FILE="/etc/systemd/system/${PROXY_MONITOR_SERVICE_NAME}.service"
PROXY_MONITOR_TIMER_FILE="/etc/systemd/system/${PROXY_MONITOR_TIMER_NAME}"
PROXY_MONITOR_INTERVAL="${PROXY_MONITOR_INTERVAL:-10min}"
GHELPER_MONITOR_THREADS="${GHELPER_MONITOR_THREADS:-25}"
PORT="8090"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR"
UV_BIN=""
DEPS_MARKER=".venv/.data-handler-deps.sha256"
FORCE_UV_SYNC="${FORCE_UV_SYNC:-0}"

echo "=========================================="
echo "Starting backend deployment..."
echo "Backend directory: $BACKEND_DIR"
echo "=========================================="

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: deploy.sh must run as root"
    exit 1
fi

run_if_exists() {
    "$@" >/dev/null 2>&1 || true
}

ensure_runtime_dirs() {
    echo "Creating runtime directories..."
    mkdir -p /data/temp
    mkdir -p /data/testing_data
    mkdir -p /configs
    mkdir -p /var/log
}

stop_old_systemd_service() {
    echo "Stopping old ${SERVICE_NAME} systemd service if present..."
    if systemctl list-unit-files "${SERVICE_NAME}.service" >/dev/null 2>&1 || [ -f "$SERVICE_FILE" ]; then
        run_if_exists systemctl stop "$SERVICE_NAME"
        run_if_exists systemctl disable "$SERVICE_NAME"
    fi

    echo "Removing old ${SERVICE_NAME} systemd unit..."
    rm -f "$SERVICE_FILE"
    rm -f "/lib/systemd/system/${SERVICE_NAME}.service"
    rm -f "/usr/lib/systemd/system/${SERVICE_NAME}.service"
    systemctl daemon-reload
    run_if_exists systemctl reset-failed "$SERVICE_NAME"
}

stop_old_proxy_monitor() {
    echo "Stopping old ${PROXY_MONITOR_SERVICE_NAME} timer if present..."
    run_if_exists systemctl stop "$PROXY_MONITOR_TIMER_NAME"
    run_if_exists systemctl disable "$PROXY_MONITOR_TIMER_NAME"
    run_if_exists systemctl stop "$PROXY_MONITOR_SERVICE_NAME"
    rm -f "$PROXY_MONITOR_SERVICE_FILE"
    rm -f "$PROXY_MONITOR_TIMER_FILE"
    systemctl daemon-reload
    run_if_exists systemctl reset-failed "$PROXY_MONITOR_SERVICE_NAME"
}

kill_port_processes() {
    local pids=""

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

    echo "Killing process(es) on port ${PORT}: $pids"
    kill $pids 2>/dev/null || true
    sleep 2

    local alive=""
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            alive="$alive $pid"
        fi
    done

    if [ -n "$alive" ]; then
        echo "Force killing process(es):$alive"
        kill -9 $alive 2>/dev/null || true
    fi
}

install_nginx_with() {
    local manager="$1"
    case "$manager" in
        apt-get)
            apt-get update
            DEBIAN_FRONTEND=noninteractive apt-get install -y nginx
            ;;
        dnf)
            dnf install -y nginx
            ;;
        yum)
            yum install -y nginx
            ;;
        apk)
            apk add --no-cache nginx
            ;;
        *)
            echo "Unsupported package manager: $manager"
            return 1
            ;;
    esac
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

ensure_proxy_monitor_tools() {
    echo "Checking proxy monitor tools..."
    if command -v curl >/dev/null 2>&1; then
        echo "curl is already installed: $(curl --version | head -n 1)"
    else
        echo "curl is not installed. Installing curl..."
        install_package curl
    fi
}

ensure_nginx() {
    echo "Checking nginx..."
    if command -v nginx >/dev/null 2>&1; then
        echo "nginx is already installed: $(nginx -v 2>&1)"
    else
        echo "nginx is not installed. Installing nginx..."
        if command -v apt-get >/dev/null 2>&1; then
            install_nginx_with apt-get
        elif command -v dnf >/dev/null 2>&1; then
            install_nginx_with dnf
        elif command -v yum >/dev/null 2>&1; then
            install_nginx_with yum
        elif command -v apk >/dev/null 2>&1; then
            install_nginx_with apk
        else
            echo "Error: no supported package manager found for nginx installation"
            exit 1
        fi
    fi

    if systemctl list-unit-files nginx.service 2>/dev/null | grep -q '^nginx\.service'; then
        run_if_exists systemctl enable nginx
        if ! systemctl start nginx 2>/dev/null; then
            echo "Warning: nginx service did not start cleanly. Backend deployment will continue."
        fi
        echo "nginx status: $(systemctl is-active nginx 2>/dev/null || echo unknown)"
    else
        echo "nginx installed, but nginx.service was not found. Skipping systemctl management."
    fi
}

find_uv_bin() {
    local candidates=(
        "$(command -v uv || true)"
        "/usr/local/bin/uv"
        "/usr/bin/uv"
        "/root/.local/bin/uv"
        "/root/.cargo/bin/uv"
        "/home/opentrons/.local/bin/uv"
        "/home/opentrons/.cargo/bin/uv"
    )

    local candidate
    for candidate in "${candidates[@]}"; do
        if [ -n "$candidate" ] && [ -x "$candidate" ]; then
            echo "$candidate"
            return 0
        fi
    done

    return 1
}

install_uv_with_installer() {
    if ! command -v curl >/dev/null 2>&1; then
        echo "curl is not installed. Installing curl..."
        install_package curl
    fi

    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
}

ensure_uv() {
    UV_BIN="$(find_uv_bin || true)"
    if [ -n "$UV_BIN" ]; then
        echo "uv found: $UV_BIN"
        "$UV_BIN" --version || true
        return
    fi

    install_uv_with_installer

    export PATH="/root/.local/bin:/root/.cargo/bin:/usr/local/bin:/usr/bin:$PATH"
    UV_BIN="$(find_uv_bin || true)"
    if [ -z "$UV_BIN" ]; then
        echo "Error: uv installation finished, but uv binary was not found"
        exit 1
    fi

    echo "uv installed: $UV_BIN"
    "$UV_BIN" --version || true
}

dependency_fingerprint() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum pyproject.toml uv.lock | sha256sum | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 pyproject.toml uv.lock | shasum -a 256 | awk '{print $1}'
    else
        echo "Error: sha256sum or shasum is required to fingerprint dependencies"
        exit 1
    fi
}

write_dependency_marker() {
    local fingerprint="$1"
    mkdir -p "$(dirname "$DEPS_MARKER")"
    printf '%s\n' "$fingerprint" > "$DEPS_MARKER"
}

dependencies_are_current() {
    local fingerprint="$1"

    if [ "$FORCE_UV_SYNC" = "1" ]; then
        echo "FORCE_UV_SYNC=1, running uv sync."
        return 1
    fi

    if [ ! -x ".venv/bin/python" ]; then
        echo "No reusable .venv found."
        return 1
    fi

    if [ -f "$DEPS_MARKER" ] && [ "$(cat "$DEPS_MARKER")" = "$fingerprint" ]; then
        echo "Dependencies unchanged; skipping uv sync."
        return 0
    fi

    if [ ! -f "$DEPS_MARKER" ]; then
        echo "Existing .venv found without dependency marker; bootstrapping marker and skipping uv sync."
        echo "Set FORCE_UV_SYNC=1 before deploy.sh to rebuild dependencies."
        write_dependency_marker "$fingerprint"
        return 0
    fi

    echo "Dependency files changed; running uv sync."
    return 1
}

install_backend_dependencies() {
    echo "Installing backend dependencies with uv..."
    ensure_uv

    cd "$BACKEND_DIR"
    local fingerprint
    fingerprint="$(dependency_fingerprint)"
    if dependencies_are_current "$fingerprint"; then
        return
    fi

    "$UV_BIN" sync --frozen
    write_dependency_marker "$fingerprint"
}

refresh_google_proxy_config() {
    echo "Refreshing Google proxy config..."
    if [ ! -f "$BACKEND_DIR/ghelper-test/node_test.py" ]; then
        echo "Warning: ghelper-test/node_test.py not found; skipping proxy refresh."
        return
    fi

    cd "$BACKEND_DIR"
    if "$UV_BIN" run python ghelper-test/node_test.py --max-threads "$GHELPER_MONITOR_THREADS"; then
        echo "Google proxy config refreshed."
    else
        echo "Warning: Google proxy config refresh failed; backend will keep the existing skill_config.json proxy."
    fi
}

write_systemd_service() {
    echo "Writing ${SERVICE_NAME} systemd service..."
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Data Handler FastAPI Service
After=network.target

[Service]
User=root
WorkingDirectory=$BACKEND_DIR
Environment=DATA_HANDLER_RUN_ENV=server
Environment=PYTHONUNBUFFERED=1
Environment=GHELPER_MONITOR_THREADS=$GHELPER_MONITOR_THREADS
Environment=PATH=/root/.local/bin:/root/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStartPre=/bin/bash -lc 'cd $BACKEND_DIR && if [ -f ghelper-test/node_test.py ]; then $UV_BIN run python ghelper-test/node_test.py --max-threads $GHELPER_MONITOR_THREADS || true; fi'
ExecStart=$UV_BIN run python -m uvicorn app:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
}

write_proxy_monitor_units() {
    echo "Writing ${PROXY_MONITOR_SERVICE_NAME} systemd units..."
    cat > "$PROXY_MONITOR_SERVICE_FILE" << EOF
[Unit]
Description=Refresh Data Handler Google proxy config
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
WorkingDirectory=$BACKEND_DIR
Environment=DATA_HANDLER_RUN_ENV=server
Environment=PYTHONUNBUFFERED=1
Environment=GHELPER_MONITOR_THREADS=$GHELPER_MONITOR_THREADS
Environment=PATH=/root/.local/bin:/root/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/bin/bash -lc 'cd $BACKEND_DIR && $UV_BIN run python ghelper-test/node_test.py --max-threads $GHELPER_MONITOR_THREADS'
EOF

    cat > "$PROXY_MONITOR_TIMER_FILE" << EOF
[Unit]
Description=Run Data Handler Google proxy refresh periodically

[Timer]
OnBootSec=30s
OnUnitActiveSec=$PROXY_MONITOR_INTERVAL
AccuracySec=30s
Persistent=true
Unit=${PROXY_MONITOR_SERVICE_NAME}.service

[Install]
WantedBy=timers.target
EOF
}

start_proxy_monitor_timer() {
    echo "Enabling ${PROXY_MONITOR_TIMER_NAME}..."
    systemctl daemon-reload
    systemctl enable "$PROXY_MONITOR_TIMER_NAME"
    systemctl start "$PROXY_MONITOR_TIMER_NAME"
    systemctl status "$PROXY_MONITOR_TIMER_NAME" --no-pager || true
}

start_systemd_service() {
    echo "Reloading systemctl configuration..."
    systemctl daemon-reload

    echo "Enabling and starting ${SERVICE_NAME}..."
    systemctl enable "$SERVICE_NAME"
    systemctl start "$SERVICE_NAME"

    sleep 2
    if ! systemctl is-active --quiet "$SERVICE_NAME"; then
        echo "Error: ${SERVICE_NAME} failed to start"
        systemctl status "$SERVICE_NAME" --no-pager || true
        journalctl -u "$SERVICE_NAME" -n 120 --no-pager || true
        exit 1
    fi

    systemctl status "$SERVICE_NAME" --no-pager
}

ensure_runtime_dirs
stop_old_systemd_service
stop_old_proxy_monitor
kill_port_processes
ensure_proxy_monitor_tools
ensure_nginx
install_backend_dependencies
refresh_google_proxy_config
write_systemd_service
write_proxy_monitor_units
start_proxy_monitor_timer
start_systemd_service

echo ""
echo "=========================================="
echo "Backend deployment completed!"
echo "=========================================="
echo "data-handler service: http://localhost:${PORT}"
echo "proxy monitor timer: ${PROXY_MONITOR_TIMER_NAME} (${PROXY_MONITOR_INTERVAL})"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u ${SERVICE_NAME} -f"
echo "  sudo journalctl -u ${PROXY_MONITOR_SERVICE_NAME} -f"
