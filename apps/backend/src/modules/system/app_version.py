from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import core.config as setting


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("version metadata must be a JSON object")
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return payload


def load_app_version(
    version_path: Path | None = None,
    deployment_path: Path | None = None,
) -> dict[str, Any]:
    version = _read_json(version_path or setting.APP_VERSION_PATH)
    deployment = _read_json(deployment_path or setting.APP_DEPLOYMENT_VERSION_PATH)

    return {
        "version": str(version.get("version") or "N/A").strip() or "N/A",
        "updated_at": (
            str(deployment.get("updated_at") or version.get("updated_at")).strip()
            if deployment.get("updated_at") or version.get("updated_at")
            else None
        ),
        "commit": (
            str(deployment.get("commit") or version.get("commit")).strip()
            if deployment.get("commit") or version.get("commit")
            else None
        ),
    }
