from __future__ import annotations

from copy import deepcopy

import pytest

from api.services import ssh_commands


class FakeCursor(list):
    def sort(self, *_args, **_kwargs):
        return self


class FakeDeleteResult:
    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count


class FakeCollection:
    def __init__(self):
        self.documents: dict[str, dict] = {}

    def find(self, *_args, **_kwargs):
        return FakeCursor(deepcopy(list(self.documents.values())))

    def insert_one(self, document):
        self.documents[document["_id"]] = deepcopy(document)

    def find_one_and_update(self, query, update, **_kwargs):
        document = self.documents.get(query["_id"])
        if document is None:
            return None
        document.update(deepcopy(update["$set"]))
        return deepcopy(document)

    def delete_one(self, query):
        deleted = int(self.documents.pop(query["_id"], None) is not None)
        return FakeDeleteResult(deleted)


def test_builtin_commands_include_date(monkeypatch):
    monkeypatch.setattr(ssh_commands, "_get_collection", lambda: FakeCollection())

    result = ssh_commands.list_commands()

    assert result["database_available"] is True
    assert any(item["command"] == "date" for item in result["builtin_commands"])
    assert all(
        item["tag"] == ("risk" if item["id"] == "builtin-sync-server-time" else "general")
        for item in result["builtin_commands"]
    )
    assert any(
        item["id"] == "builtin-sync-server-time"
        and "timedatectl set-timezone Asia/Shanghai" in item["command"]
        and "$DATE_EPOCH" in item["command"]
        and item["command"].endswith("&& date")
        for item in result["builtin_commands"]
    )


def test_custom_command_crud(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(ssh_commands, "_get_collection", lambda: collection)

    created = ssh_commands.create_command(
        name="查看日期",
        command="date",
        description="设备时间",
        tag="general",
    )
    assert created["source"] == "custom"
    assert ssh_commands.list_commands()["custom_commands"][0]["name"] == "查看日期"

    updated = ssh_commands.update_command(
        created["id"],
        name="查看 UTC 日期",
        command="date -u",
        description="UTC 时间",
        tag="risk",
    )
    assert updated["command"] == "date -u"
    assert updated["tag"] == "risk"

    assert ssh_commands.delete_command(created["id"])["success"] is True
    assert ssh_commands.list_commands()["custom_commands"] == []
    with pytest.raises(KeyError):
        ssh_commands.delete_command(created["id"])


def test_custom_command_preserves_long_multi_command(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(ssh_commands, "_get_collection", lambda: collection)
    command = (
        "mount -o remount,rw /; timedatectl set-ntp false; "
        "timedatectl set-time \"$(date '+%Y-%m-%d %H:%M:%S')\"\n"
        + "echo verified; " * 400
    )

    created = ssh_commands.create_command(
        name="长命令",
        command=command,
        description="多段命令",
    )

    assert created["command"] == command.strip()
    assert len(created["command"]) > 4000
    assert created["tag"] == "general"


def test_custom_command_rejects_invalid_tag(monkeypatch):
    monkeypatch.setattr(ssh_commands, "_get_collection", lambda: FakeCollection())

    with pytest.raises(ValueError, match="general 或 risk"):
        ssh_commands.create_command(name="危险命令", command="reboot", tag="danger")


def test_execute_command_returns_stdout_stderr_and_exit_code(monkeypatch):
    class FakeSshClient:
        def __init__(self, ip):
            assert ip == "192.168.6.126"

        def exec_command(self, command, *, timeout):
            assert command == (
                "DATE='2026-08-05 13:20:30'; DATE_EPOCH=1785907230; "
                "DATE_TIMEZONE=UTC+0000; export DATE DATE_EPOCH DATE_TIMEZONE; date"
            )
            assert timeout == 45
            return 0, "Wed Aug 5\n", ""

    monkeypatch.setattr(ssh_commands, "OpentronsSshClient", FakeSshClient)
    monkeypatch.setattr(
        ssh_commands,
        "_build_server_environment",
        lambda: {
            "DATE": "2026-08-05 13:20:30",
            "DATE_EPOCH": "1785907230",
            "DATE_TIMEZONE": "UTC+0000",
        },
    )

    result = ssh_commands.execute_command(
        ip="192.168.6.126",
        command="date",
        timeout=45,
    )

    assert result["success"] is True
    assert result["exit_code"] == 0
    assert result["stdout"] == "Wed Aug 5\n"
    assert result["stderr"] == ""
    assert result["environment"]["DATE"] == "2026-08-05 13:20:30"
    assert result["duration_ms"] >= 0


def test_execute_command_rejects_invalid_ip():
    with pytest.raises(ValueError, match="无效设备 IP"):
        ssh_commands.execute_command(ip="not-an-ip", command="date")


def test_execute_commands_batch_preserves_device_order_and_failures(monkeypatch):
    environment = {
        "DATE": "2026-08-05 14:00:00",
        "DATE_EPOCH": "1785909600",
        "DATE_TIMEZONE": "CST+0800",
    }
    monkeypatch.setattr(ssh_commands, "_build_server_environment", lambda: dict(environment))

    def fake_execute_command(*, ip, command, timeout, server_environment):
        assert command == 'printf "%s" "$DATE"'
        assert timeout == 60
        assert server_environment == environment
        if ip == "192.168.6.127":
            raise RuntimeError("connection refused")
        return {
            "ip": ip,
            "command": command,
            "environment": server_environment,
            "success": True,
            "exit_code": 0,
            "stdout": server_environment["DATE"],
            "stderr": "",
            "output_truncated": False,
            "started_at": "start",
            "finished_at": "finish",
            "duration_ms": 10,
        }

    monkeypatch.setattr(ssh_commands, "execute_command", fake_execute_command)

    result = ssh_commands.execute_commands_batch(
        ips=["192.168.6.126", "192.168.6.127", "192.168.6.126"],
        command='printf "%s" "$DATE"',
        timeout=60,
        concurrency=4,
    )

    assert [item["ip"] for item in result["results"]] == ["192.168.6.126", "192.168.6.127"]
    assert result["results"][0]["success"] is True
    assert result["results"][1]["success"] is False
    assert result["results"][1]["error"] == "connection refused"
    assert result["results"][1]["environment"] == environment
    assert result["success_count"] == 1
    assert result["failed_count"] == 1
    assert result["concurrency"] == 2
