from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from modules.system.app_version import load_app_version


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
UPDATE_SCRIPT_PATH = REPOSITORY_ROOT / "deploy" / "update_version.py"


def load_update_module():
    spec = importlib.util.spec_from_file_location("deploy_update_version", UPDATE_SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_app_version_reads_metadata_and_handles_invalid_file(tmp_path: Path) -> None:
    version_path = tmp_path / "version.json"
    deployment_path = tmp_path / "app-version.json"
    version_path.write_text(
        json.dumps({"version": "2.3.4"}),
        encoding="utf-8",
    )
    deployment_path.write_text(
        json.dumps({"updated_at": "2026-08-12T01:30:00+00:00", "commit": "abc123def456"}),
        encoding="utf-8",
    )

    assert load_app_version(version_path, deployment_path) == {
        "version": "2.3.4",
        "updated_at": "2026-08-12T01:30:00+00:00",
        "commit": "abc123def456",
    }

    deployment_path.unlink()
    version_path.write_text(
        json.dumps({"version": "2.3.4", "updated_at": "release-time", "commit": "release-commit"}),
        encoding="utf-8",
    )
    assert load_app_version(version_path, deployment_path)["updated_at"] == "release-time"

    version_path.write_text("not-json", encoding="utf-8")
    assert load_app_version(version_path, deployment_path) == {
        "version": "N/A",
        "updated_at": None,
        "commit": None,
    }


def test_deployment_update_preserves_version_and_refreshes_metadata(tmp_path: Path, monkeypatch) -> None:
    module = load_update_module()
    source_path = tmp_path / "apps" / "version.json"
    deployment_path = tmp_path / "data" / "app-version.json"
    source_path.parent.mkdir()
    source_path.write_text(
        json.dumps({"version": "3.2.1", "updated_at": "release-time"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "current_commit", lambda _repository: "newcommit123")

    payload = module.update_version_file(deployment_path, tmp_path, source_path)

    assert payload["version"] == "3.2.1"
    assert payload["updated_at"]
    assert payload["commit"] == "newcommit123"
    assert json.loads(deployment_path.read_text(encoding="utf-8")) == payload
    assert json.loads(source_path.read_text(encoding="utf-8")) == {
        "version": "3.2.1",
        "updated_at": "release-time",
    }
