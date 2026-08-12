#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def current_commit(repository: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "--short=12", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def update_version_file(
    path: Path,
    repository: Path,
    source: Path,
    version: str | None = None,
) -> dict[str, Any]:
    source_payload: dict[str, Any] = {}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            source_payload = payload
    except (OSError, json.JSONDecodeError):
        source_payload = {}

    selected_version = str(version or source_payload.get("version") or "1.0.0").strip()
    if not selected_version:
        raise ValueError("App version cannot be empty")

    commit = current_commit(repository)
    if commit == "unknown":
        commit = str(source_payload.get("commit") or "unknown").strip() or "unknown"
    payload = {
        "version": selected_version,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": commit,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary_path = Path(handle.name)
    temporary_path.replace(path)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update the deployed application version metadata")
    parser.add_argument("--path", required=True, type=Path, help="Runtime deployment metadata path")
    parser.add_argument("--source", required=True, type=Path, help="Path to apps/version.json")
    parser.add_argument("--repository", required=True, type=Path, help="Git repository root")
    parser.add_argument("--version", help="Optional new semantic version")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = update_version_file(
        args.path.resolve(),
        args.repository.resolve(),
        args.source.resolve(),
        args.version,
    )
    print(f"App version updated: {payload['version']} at {payload['updated_at']} ({payload['commit']})")


if __name__ == "__main__":
    main()
