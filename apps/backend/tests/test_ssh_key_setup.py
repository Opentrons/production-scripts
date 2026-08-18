from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from modules.robots import ssh_key_setup


def _setup_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "ssh-ot3"
    directory.mkdir()
    script = directory / ssh_key_setup.SETUP_SCRIPT_NAME
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv(ssh_key_setup.SSH_OT3_DIR_ENV, str(directory))
    return script


def test_install_ssh_key_runs_fixed_script_and_recognizes_success(tmp_path, monkeypatch) -> None:
    script = _setup_script(tmp_path, monkeypatch)

    def fake_run(command, **kwargs):
        assert command == ["bash", "setup_ssh_keys.sh", "-flex", "192.168.6.126"]
        assert kwargs["cwd"] == script.parent
        assert kwargs["timeout"] == 45
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='Setting up Flex at 192.168.6.126\n{"message":"Added 1 new keys","key_md5":["abc"]}\nDone\n',
            stderr="",
        )

    monkeypatch.setattr(ssh_key_setup.subprocess, "run", fake_run)

    result = ssh_key_setup.install_ssh_key("192.168.6.126", timeout=45)

    assert result["success"] is True
    assert result["message"] == "Added 1 new keys"
    assert result["exit_code"] == 0


def test_install_ssh_key_treats_http_error_body_as_failure(tmp_path, monkeypatch) -> None:
    _setup_script(tmp_path, monkeypatch)
    monkeypatch.setattr(
        ssh_key_setup.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout='Setting up Flex\n{"errorCode":"no-key","message":"No valid keys found"}\nDone\n',
            stderr="",
        ),
    )

    result = ssh_key_setup.install_ssh_key("192.168.6.127")

    assert result["success"] is False
    assert result["message"] == "No valid keys found"


def test_install_ssh_key_rejects_zero_keys_as_failure(tmp_path, monkeypatch) -> None:
    _setup_script(tmp_path, monkeypatch)
    monkeypatch.setattr(
        ssh_key_setup.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout='{"message":"Added 0 new keys","key_md5":[]}\nDone\n',
            stderr="",
        ),
    )

    result = ssh_key_setup.install_ssh_key("192.168.6.128")

    assert result["success"] is False
    assert result["message"] == "Added 0 new keys"


def test_install_ssh_key_rejects_command_injection_before_subprocess(monkeypatch) -> None:
    called = False

    def fake_run(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(ssh_key_setup.subprocess, "run", fake_run)

    with pytest.raises(ValueError, match="无效设备 IP"):
        ssh_key_setup.install_ssh_key("192.168.6.55; reboot")
    assert called is False


def test_install_ssh_key_decodes_timeout_output(tmp_path, monkeypatch) -> None:
    _setup_script(tmp_path, monkeypatch)

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("sh", 2, output=b"partial stdout", stderr=b"partial stderr")

    monkeypatch.setattr(ssh_key_setup.subprocess, "run", timeout)

    result = ssh_key_setup.install_ssh_key("192.168.6.129", timeout=2)

    assert result["success"] is False
    assert result["stdout"] == "partial stdout"
    assert result["stderr"] == "partial stderr"


def test_install_ssh_keys_batch_preserves_order_and_reports_failures(tmp_path, monkeypatch) -> None:
    script = _setup_script(tmp_path, monkeypatch)

    def fake_install(ip, timeout, *, script_path):
        assert timeout == 30
        assert script_path == script
        return {
            "ip": ip,
            "success": ip.endswith("126"),
            "message": "Added 1 new keys" if ip.endswith("126") else "No valid keys found",
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "output_truncated": False,
            "started_at": "start",
            "finished_at": "finish",
            "duration_ms": 10,
        }

    monkeypatch.setattr(ssh_key_setup, "install_ssh_key", fake_install)

    result = ssh_key_setup.install_ssh_keys_batch(
        ["192.168.6.126", "192.168.6.127", "192.168.6.126"],
        concurrency=4,
    )

    assert [item["ip"] for item in result["results"]] == ["192.168.6.126", "192.168.6.127"]
    assert result["success_count"] == 1
    assert result["failed_count"] == 1
    assert result["concurrency"] == 2


def test_resolve_setup_script_reports_server_locations(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ssh_key_setup.SSH_OT3_DIR_ENV, str(tmp_path / "missing"))
    monkeypatch.setattr(ssh_key_setup.Path, "home", lambda: tmp_path / "home")

    with pytest.raises(RuntimeError, match="/ssh-ot3"):
        ssh_key_setup.resolve_setup_script()
