from __future__ import annotations

import subprocess

import paramiko
import pytest

from modules.robots import code_flash


@pytest.mark.parametrize("hashed", [False, True])
def test_clear_known_host_removes_only_selected_robot(tmp_path, monkeypatch, hashed):
    monkeypatch.setattr(code_flash.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(code_flash, "_append_log", lambda *_args: None)
    key = paramiko.RSAKey.generate(1024)
    host = "192.168.6.87"
    target = paramiko.HostKeys.hash_host(host) if hashed else host
    other = f"192.168.6.88 {key.get_name()} {key.get_base64()}\n"
    path = tmp_path / ".ssh" / "known_hosts"
    path.parent.mkdir()
    path.write_text(f"{target} {key.get_name()} {key.get_base64()}\n" + other)

    code_flash._clear_robot_known_host("test", host)

    assert path.read_text() == other
    assert path.with_suffix(".old").is_file()
    # Repeated cleanup also succeeds when no matching entry remains.
    code_flash._clear_robot_known_host("test", host)
    assert path.read_text() == other


def test_clear_known_host_skips_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(code_flash.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(code_flash, "_append_log", lambda *_args: None)
    monkeypatch.setattr(code_flash.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("unexpected command"))
    code_flash._clear_robot_known_host("test", "192.168.6.87")
    assert not (tmp_path / ".ssh").exists()


@pytest.mark.parametrize("failure", ["exit", "timeout"])
def test_clear_known_host_reports_command_failure(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(code_flash.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(code_flash, "_append_log", lambda *_args: None)
    path = tmp_path / ".ssh" / "known_hosts"
    path.parent.mkdir()
    path.touch()

    def fake_run(arguments, **kwargs):
        assert arguments == ["ssh-keygen", "-f", str(path), "-R", "192.168.6.87"]
        if failure == "timeout":
            raise subprocess.TimeoutExpired(arguments, 10)
        return subprocess.CompletedProcess(arguments, 1, "", "Permission denied")

    monkeypatch.setattr(code_flash.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="旧 SSH 主机密钥失败"):
        code_flash._clear_robot_known_host("test", "192.168.6.87")
