#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

REMOTE_HOST="${REMOTE_HOST:-192.168.6.55}"
REMOTE_USER="${REMOTE_USER:-root}"
REMOTE_SSH_PORT="${REMOTE_SSH_PORT:-22}"
REMOTE_ROOT="${REMOTE_ROOT:-/opt/production-platform}"
REMOTE_UV_BIN="${REMOTE_UV_BIN:-/root/.local/bin/uv}"
API_PORT="${API_PORT:-8090}"
WEB_HTTP_PORT="${WEB_HTTP_PORT:-80}"
WEB_HTTPS_PORT="${WEB_HTTPS_PORT:-443}"
SERVER_NAME="${SERVER_NAME:-_}"
SSL_CERTIFICATE="${SSL_CERTIFICATE:-/etc/ssl/production-platform/production-platform.crt}"
SSL_CERTIFICATE_KEY="${SSL_CERTIFICATE_KEY:-/etc/ssl/production-platform/production-platform.key}"
DURO_API_KEY_PATH="${DURO_API_KEY_PATH:-$REPOSITORY_ROOT/apps/backend/auth-files/duro-api-key.txt}"
REMOTE_DURO_API_KEY_PATH="${REMOTE_DURO_API_KEY_PATH:-/configs/duro-api-key.txt}"

for command_name in ssh rsync mktemp npm; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "Error: $command_name is required"
        exit 1
    fi
done

if [[ ! "$REMOTE_SSH_PORT" =~ ^[0-9]+$ ]]; then
    echo "Error: REMOTE_SSH_PORT must be numeric"
    exit 1
fi
if [[ ! "$REMOTE_ROOT" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
    echo "Error: REMOTE_ROOT must be an absolute path without spaces"
    exit 1
fi
case "$REMOTE_ROOT" in
    /|*/../*|*/..|*//*)
        echo "Error: REMOTE_ROOT must identify a dedicated deployment directory"
        exit 1
        ;;
esac
if [ ! -s "$DURO_API_KEY_PATH" ]; then
    echo "Error: Duro API Key file is missing or empty: $DURO_API_KEY_PATH"
    exit 1
fi
if [[ ! "$REMOTE_DURO_API_KEY_PATH" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
    echo "Error: REMOTE_DURO_API_KEY_PATH must be an absolute path without spaces"
    exit 1
fi
case "$REMOTE_DURO_API_KEY_PATH" in
    /|*/../*|*/..|*//*|*/)
        echo "Error: REMOTE_DURO_API_KEY_PATH must identify a file"
        exit 1
        ;;
esac

REMOTE_TARGET="$REMOTE_USER@$REMOTE_HOST"
CONTROL_DIR="$(mktemp -d "${TMPDIR:-/tmp}/production-deploy.XXXXXX")"
CONTROL_PATH="$CONTROL_DIR/ssh"
SSH_OPTIONS=(
    -p "$REMOTE_SSH_PORT"
    -o ControlMaster=auto
    -o ControlPersist=60
    -o "ControlPath=$CONTROL_PATH"
    -o StrictHostKeyChecking=accept-new
)
RSYNC_SSH="ssh -p $REMOTE_SSH_PORT -o ControlMaster=auto -o ControlPersist=60 -o ControlPath=$CONTROL_PATH -o StrictHostKeyChecking=accept-new"

cleanup() {
    ssh -p "$REMOTE_SSH_PORT" -o "ControlPath=$CONTROL_PATH" -O exit "$REMOTE_TARGET" >/dev/null 2>&1 || true
    rmdir "$CONTROL_DIR" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Connecting to $REMOTE_TARGET..."
ssh "${SSH_OPTIONS[@]}" "$REMOTE_TARGET" \
    "mkdir -p '$REMOTE_ROOT/apps/backend' '$REMOTE_ROOT/apps/web-ui' '$REMOTE_ROOT/deploy'"

echo "Installing Duro API Key..."
remote_duro_key_dir="${REMOTE_DURO_API_KEY_PATH%/*}"
remote_duro_key_temp="${REMOTE_DURO_API_KEY_PATH}.deploying"
ssh "${SSH_OPTIONS[@]}" "$REMOTE_TARGET" \
    "install -d -o root -g root -m 700 '$remote_duro_key_dir'"
rsync -az -e "$RSYNC_SSH" \
    "$DURO_API_KEY_PATH" \
    "$REMOTE_TARGET:$remote_duro_key_temp"
ssh "${SSH_OPTIONS[@]}" "$REMOTE_TARGET" \
    "chown root:root '$remote_duro_key_temp' && chmod 600 '$remote_duro_key_temp' && mv -f '$remote_duro_key_temp' '$REMOTE_DURO_API_KEY_PATH'"

echo "Syncing backend code..."
rsync -az --delete \
    --exclude '.env' \
    --exclude 'data/' \
    --exclude 'db-storage/' \
    --exclude 'auth-files/' \
    --exclude 'ghelper-test/*.yml' \
    --exclude 'ghelper-test/*.yaml' \
    --exclude 'ghelper-test/skill_config.json' \
    --exclude 'tests/reports/' \
    --exclude '**/__pycache__/' \
    --exclude '**/.pytest_cache/' \
    -e "$RSYNC_SSH" \
    "$REPOSITORY_ROOT/apps/backend/" \
    "$REMOTE_TARGET:$REMOTE_ROOT/apps/backend/"

echo "Syncing frontend code and production assets..."
rsync -az --delete \
    --exclude 'node_modules/' \
    --exclude '.env' \
    --exclude '.env.*' \
    -e "$RSYNC_SSH" \
    "$REPOSITORY_ROOT/apps/web-ui/" \
    "$REMOTE_TARGET:$REMOTE_ROOT/apps/web-ui/"

echo "Syncing deployment files..."
rsync -az --delete -e "$RSYNC_SSH" \
    "$REPOSITORY_ROOT/deploy/" \
    "$REMOTE_TARGET:$REMOTE_ROOT/deploy/"
rsync -az -e "$RSYNC_SSH" \
    "$REPOSITORY_ROOT/Makefile" \
    "$REPOSITORY_ROOT/pyproject.toml" \
    "$REPOSITORY_ROOT/uv.lock" \
    "$REMOTE_TARGET:$REMOTE_ROOT/"
rsync -az -e "$RSYNC_SSH" \
    "$REPOSITORY_ROOT/apps/version.json" \
    "$REMOTE_TARGET:$REMOTE_ROOT/apps/version.json"

echo "Restarting the remote backend and reloading Nginx..."
ssh "${SSH_OPTIONS[@]}" "$REMOTE_TARGET" bash -s -- \
    "$REMOTE_ROOT" "$REMOTE_UV_BIN" "$API_PORT" "$WEB_HTTP_PORT" "$WEB_HTTPS_PORT" \
    "$SERVER_NAME" "$SSL_CERTIFICATE" "$SSL_CERTIFICATE_KEY" <<'REMOTE_SCRIPT'
set -euo pipefail

remote_root="$1"
uv_bin="$2"
api_port="$3"
web_http_port="$4"
web_https_port="$5"
server_name="$6"
ssl_certificate="$7"
ssl_certificate_key="$8"

cd "$remote_root"
UV_BIN="$uv_bin" API_PORT="$api_port" bash deploy/backend.sh
API_PORT="$api_port" \
WEB_HTTP_PORT="$web_http_port" \
WEB_HTTPS_PORT="$web_https_port" \
WEB_ENABLE_HTTPS=true \
WEB_SKIP_BUILD=true \
SERVER_NAME="$server_name" \
SSL_CERTIFICATE="$ssl_certificate" \
SSL_CERTIFICATE_KEY="$ssl_certificate_key" \
bash deploy/web.sh

systemctl is-active --quiet production-backend.service
systemctl is-active --quiet nginx.service

for attempt in $(seq 1 30); do
    if curl --fail --silent "http://127.0.0.1:$api_port/" >/dev/null; then
        exit 0
    fi
    sleep 1
done

echo "Backend health check failed after 30 seconds"
systemctl --no-pager status production-backend.service || true
exit 1
REMOTE_SCRIPT

echo "Remote deployment completed: $REMOTE_TARGET:$REMOTE_ROOT"
