#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PORT="${DURO_REMOTE_CHROME_PORT:-9222}"
ADDRESS="${DURO_REMOTE_CHROME_ADDRESS:-127.0.0.1}"
PROFILE_DIR="${DURO_REMOTE_CHROME_PROFILE_DIR:-${BACKEND_DIR}/auth-files/duro-chrome-profile}"
START_URL="${DURO_REMOTE_CHROME_START_URL:-https://mfg.duro.app/dashboard}"

if [[ -n "${DURO_CHROME_BIN:-}" ]]; then
  CHROME_BIN="${DURO_CHROME_BIN}"
elif [[ "$(uname -s)" == "Darwin" ]]; then
  CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
else
  CHROME_BIN="$(command -v google-chrome || command -v chromium || command -v chromium-browser || true)"
fi

if [[ -z "${CHROME_BIN}" || ! -x "${CHROME_BIN}" ]]; then
  echo "Chrome executable not found; set DURO_CHROME_BIN" >&2
  exit 1
fi

mkdir -p "${PROFILE_DIR}"

exec "${CHROME_BIN}" \
  --remote-debugging-address="${ADDRESS}" \
  --remote-debugging-port="${PORT}" \
  '--remote-allow-origins=*' \
  --user-data-dir="${PROFILE_DIR}" \
  --no-first-run \
  --no-default-browser-check \
  "${START_URL}"
