#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

cd "$PROJECT_ROOT" || exit 1

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed or not available on PATH."
  echo "Install uv first, then run this launcher again."
  read -r -p "Press Enter to close..."
  exit 1
fi

uv run --package productions-hardwares productions-hardwares
STATUS=$?

echo
if [ "$STATUS" -ne 0 ]; then
  echo "productions-hardwares exited with code $STATUS"
fi
read -r -p "Press Enter to close..."
exit "$STATUS"
