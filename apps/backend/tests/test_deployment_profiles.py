from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("target,profile", [("backend-dev", "dev"), ("backend-prod", "server")])
def test_make_start_commands_pin_runtime_profile(target, profile) -> None:
    result = subprocess.run(
        ["make", "-n", target], cwd=REPOSITORY_ROOT,
        env={**os.environ, "PRODUCTION_PLATFORM_RUN_ENV": "development"},
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.startswith(f"PRODUCTION_PLATFORM_RUN_ENV={profile} uv run ")


def test_remote_deployment_alias_runs_same_production_deployment() -> None:
    commands = []
    for target in ("deploy_remote", "deploy-remote"):
        result = subprocess.run(
            ["make", "-n", target], cwd=REPOSITORY_ROOT,
            capture_output=True, text=True, check=True,
        )
        commands.append(result.stdout)
    assert commands[0] == commands[1]
    assert "npm run build" in commands[0]
    assert "bash deploy/remote.sh" in commands[0]


def test_generated_production_service_overrides_stale_development_environment(tmp_path) -> None:
    source = (REPOSITORY_ROOT / "deploy/backend.sh").read_text()
    unit_template = source.split('cat > "$SERVICE_FILE" <<EOF\n', 1)[1].split("\nEOF", 1)[0]
    fake_uv = tmp_path / "uv"
    fake_uv.write_text(
        f"#!{sys.executable}\n"
        "import json, os\n"
        "print(json.dumps({key: os.environ[key] for key in "
        "['PRODUCTION_PLATFORM_RUN_ENV', 'PRODUCTION_PLATFORM_AUTH_STORAGE', "
        "'PRODUCTION_PLATFORM_DEVICE_SCAN_MODE']}))\n"
    )
    fake_uv.chmod(0o755)
    environment = {
        **os.environ,
        "UV_BIN": str(fake_uv), "REPOSITORY_ROOT": str(tmp_path),
        "API_ROOT": str(tmp_path), "API_PORT": "18090",
        "AUTH_ENV_FILE": str(tmp_path / "production.env"),
        "PRODUCTION_PLATFORM_RUN_ENV": "dev",
        "PRODUCTION_PLATFORM_AUTH_STORAGE": "sqlite",
        "PRODUCTION_PLATFORM_DEVICE_SCAN_MODE": "simulated",
    }
    rendered = subprocess.run(
        ["bash", "-c", f"cat <<EOF\n{unit_template}\nEOF\n"],
        env=environment, capture_output=True, text=True, check=True,
    ).stdout
    command = next(line.removeprefix("ExecStart=") for line in rendered.splitlines() if line.startswith("ExecStart="))
    result = subprocess.run(shlex.split(command), env=environment, capture_output=True, text=True, check=True)

    assert json.loads(result.stdout) == {
        "PRODUCTION_PLATFORM_RUN_ENV": "server",
        "PRODUCTION_PLATFORM_AUTH_STORAGE": "mongodb",
        "PRODUCTION_PLATFORM_DEVICE_SCAN_MODE": "real",
    }


def test_remote_sync_excludes_local_backend_environment_files() -> None:
    source = (REPOSITORY_ROOT / "deploy/remote.sh").read_text()
    backend_sync = source.split('echo "Syncing backend code', 1)[1].split('echo "Syncing frontend', 1)[0]
    assert "--exclude '.env'" in backend_sync
    assert "--exclude '.env.*'" in backend_sync
