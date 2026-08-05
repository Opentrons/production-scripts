from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

import pytest

from api.services import diagnostic_logs


class FakeCollection:
    def __init__(self) -> None:
        self.documents: list[dict] = []

    def insert_many(self, documents: list[dict], ordered: bool = True) -> None:
        self.documents.extend(documents)

    def update_many(self, *_args, **_kwargs) -> None:
        return None


class FakeRecordCollection:
    def __init__(self, record: dict) -> None:
        self.record = deepcopy(record)

    def find_one(self, query: dict):
        if query.get("_id") != self.record.get("_id"):
            return None
        return deepcopy(self.record)

    def update_one(self, query: dict, update: dict) -> None:
        if query.get("_id") == self.record.get("_id"):
            self.record.update(deepcopy(update.get("$set", {})))


class FakeCoordinatorExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def submit(self, function, *args):
        self.calls.append((function, args))
        return None


class FakeChannel:
    def recv_exit_status(self) -> int:
        return 0


class FakeStream:
    def __init__(self, content: bytes = b"") -> None:
        self.channel = FakeChannel()
        self.content = content

    def read(self) -> bytes:
        return self.content


class FakeSftp:
    def get(self, _remote_path: str, local_path: str, callback=None) -> None:
        content = b"diagnostic archive"
        Path(local_path).write_bytes(content)
        if callback:
            callback(len(content), len(content))


class FakeClient:
    def exec_command(self, command: str, timeout: int):
        output = b"OT3-FLEX-TEST" if "hostnamectl" in command else b""
        return None, FakeStream(output), FakeStream()


class FakeSshClient:
    ip = "192.168.1.101"

    @contextmanager
    def connect(self):
        yield FakeClient(), FakeSftp()


def test_folder_options_match_script_categories() -> None:
    response = diagnostic_logs.list_folder_options()

    assert [folder["key"] for folder in response["folders"]] == [
        "data",
        "server",
        "logs",
        "system",
        "network",
    ]
    assert all(folder["default_selected"] for folder in response["folders"])
    for option in diagnostic_logs.DIAGNOSTIC_FOLDER_OPTIONS:
        rendered_command = option["command"].format(diag="/tmp/diagnostics")
        assert "{diag}" not in rendered_command


def test_download_device_creates_archive_and_reports_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    updates: list[dict] = []
    monkeypatch.setattr(diagnostic_logs, "OpentronsSshClient", lambda _ip: FakeSshClient())
    monkeypatch.setattr(
        diagnostic_logs,
        "_update_record",
        lambda _task_id, _record_id, **values: updates.append(values),
    )

    record = {
        "_id": "record-1",
        "robot_ip": "192.168.1.101",
        "device_name": "Flex Test",
        "server_directory": str(tmp_path / "downloads"),
        "total_steps": 3,
    }
    diagnostic_logs._download_device("task-1", record, ["data"])

    final_update = updates[-1]
    assert final_update["status"] == "success"
    assert final_update["progress"] == 100
    assert final_update["cleanup_status"] == "success"
    assert final_update["archive_name"].startswith("OT3-FLEX-TEST_")
    assert Path(final_update["archive_path"]).read_bytes() == b"diagnostic archive"


def test_download_failure_still_runs_device_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    updates: list[dict] = []
    cleanup_calls: list[dict] = []
    monkeypatch.setattr(diagnostic_logs, "OpentronsSshClient", lambda _ip: FakeSshClient())
    monkeypatch.setattr(
        diagnostic_logs,
        "_update_record",
        lambda _task_id, _record_id, **values: updates.append(values),
    )

    def fake_logged_remote(_task_id, _record_id, _client, *, label: str, script: str):
        if label == "初始化诊断目录":
            return "OT3-FLEX-TEST", ""
        raise RuntimeError("forced collection failure")

    monkeypatch.setattr(diagnostic_logs, "_run_logged_remote", fake_logged_remote)
    monkeypatch.setattr(
        diagnostic_logs,
        "_cleanup_remote_download_artifacts",
        lambda _task_id, _record_id, _ssh, **paths: cleanup_calls.append(paths),
    )

    diagnostic_logs._download_device(
        "task-1",
        {
            "_id": "record-1",
            "robot_ip": "192.168.1.101",
            "device_name": "Flex Test",
            "server_directory": str(tmp_path / "downloads"),
            "total_steps": 3,
        },
        ["data"],
    )

    assert len(cleanup_calls) == 1
    assert cleanup_calls[0]["remote_diag"].startswith("/data/.flex-diagnostics-")
    assert updates[-1]["status"] == "failed"
    assert "forced collection failure" in updates[-1]["error"]


def test_cleanup_failure_is_persisted_and_scheduled_for_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    updates: list[dict] = []
    scheduled: list[dict] = []
    monkeypatch.setattr(diagnostic_logs, "OpentronsSshClient", lambda _ip: FakeSshClient())
    monkeypatch.setattr(
        diagnostic_logs,
        "_update_record",
        lambda _task_id, _record_id, **values: updates.append(values),
    )
    monkeypatch.setattr(
        diagnostic_logs,
        "_cleanup_remote_download_artifacts",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("robot offline")),
    )

    record = {
        "_id": "record-1",
        "task_id": "task-1",
        "robot_ip": "192.168.1.101",
        "device_name": "Flex Test",
        "server_directory": str(tmp_path / "downloads"),
        "total_steps": 3,
    }
    monkeypatch.setattr(
        diagnostic_logs,
        "_get_download_record",
        lambda _record_id: {
            **record,
            "remote_diag_path": next(
                update["remote_diag_path"] for update in updates if update.get("remote_diag_path")
            ),
            "remote_archive_path": next(
                update["remote_archive_path"] for update in updates if update.get("remote_archive_path")
            ),
            "cleanup_status": "pending",
            "cleanup_attempts": 3,
            "cleanup_only_failure": True,
        },
    )
    monkeypatch.setattr(
        diagnostic_logs,
        "_schedule_pending_cleanup",
        lambda pending_record, **_kwargs: scheduled.append(pending_record) or True,
    )

    diagnostic_logs._download_device("task-1", record, ["data"])

    assert updates[-1]["status"] == "warning"
    assert updates[-1]["current_step"] == "下载完成，设备残留待清理"
    assert updates[-1]["cleanup_status"] == "pending"
    assert updates[-1]["cleanup_only_failure"] is True
    assert updates[-1]["error"] is None
    assert updates[-1]["file_available"] is True
    assert Path(updates[-1]["archive_path"]).is_file()
    assert len(scheduled) == 1


def test_pending_cleanup_restores_success_after_robot_reconnects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remote_diag = "/data/.flex-diagnostics-0123456789abcdef0123456789abcdef"
    collection = FakeRecordCollection(
        {
            "_id": "record-1",
            "task_id": "task-1",
            "robot_ip": "192.168.1.101",
            "remote_diag_path": remote_diag,
            "remote_archive_path": f"{remote_diag}.tar.gz",
            "cleanup_status": "pending",
            "cleanup_attempts": 3,
            "cleanup_only_failure": True,
            "status": "warning",
            "error": None,
        }
    )
    monkeypatch.setattr(diagnostic_logs, "OpentronsSshClient", lambda _ip: FakeSshClient())
    monkeypatch.setattr(diagnostic_logs, "_get_collection", lambda: collection)
    diagnostic_logs._TASKS.clear()

    diagnostic_logs._run_pending_cleanup(collection.record, immediate=True)

    assert collection.record["cleanup_status"] == "success"
    assert collection.record["cleanup_attempts"] == 4
    assert collection.record["status"] == "success"
    assert collection.record["error"] is None


def test_warning_record_is_counted_as_completed() -> None:
    task = {
        "devices": [
            {"status": "success", "progress": 100},
            {"status": "warning", "progress": 100},
            {"status": "failed", "progress": 100},
        ]
    }

    diagnostic_logs._recompute_task_locked(task)

    assert task["completed_devices"] == 3
    assert task["successful_devices"] == 1
    assert task["warning_devices"] == 1
    assert task["failed_devices"] == 1


def test_cleanup_rejects_paths_outside_task_namespace() -> None:
    with pytest.raises(ValueError, match="拒绝清理"):
        diagnostic_logs._build_remote_cleanup_script("/data", "/data.tar.gz")


def test_create_task_persists_one_mongo_record_per_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = FakeCollection()
    executor = FakeCoordinatorExecutor()
    monkeypatch.setattr(diagnostic_logs, "_get_collection", lambda: collection)
    monkeypatch.setattr(diagnostic_logs, "_COORDINATOR_EXECUTOR", executor)
    diagnostic_logs._TASKS.clear()

    task = diagnostic_logs.create_download_task(
        devices=[
            {"ip": "192.168.1.101", "name": "Flex A"},
            {"ip": "192.168.1.102", "name": "Flex B"},
        ],
        folder_keys=["logs", "system"],
        concurrency=8,
    )

    assert task["status"] == "queued"
    assert task["concurrency"] == 2
    assert len(collection.documents) == 2
    assert collection.documents[0]["device_name"] == "Flex A"
    assert collection.documents[0]["server_directory"]
    assert [folder["key"] for folder in collection.documents[0]["selected_folders"]] == ["logs", "system"]
    assert len(executor.calls) == 1
    diagnostic_logs._TASKS.clear()


def test_server_log_can_be_resolved_and_deleted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    download_root = tmp_path / "robot_logs"
    server_directory = download_root / "record-1"
    server_directory.mkdir(parents=True)
    archive_path = server_directory / "diagnostics.tar.gz"
    archive_path.write_bytes(b"archive")
    collection = FakeRecordCollection(
        {
            "_id": "record-1",
            "task_id": "task-1",
            "archive_path": str(archive_path),
            "archive_name": archive_path.name,
            "server_directory": str(server_directory),
            "file_deleted_at": None,
        }
    )
    monkeypatch.setattr(diagnostic_logs.setting, "ROBOT_LOG_DOWNLOAD_DIR", str(download_root))
    monkeypatch.setattr(diagnostic_logs, "_get_collection", lambda: collection)
    diagnostic_logs._TASKS.clear()

    resolved_path, filename = diagnostic_logs.resolve_server_log_download("record-1")
    result = diagnostic_logs.delete_server_log("record-1")

    assert resolved_path == archive_path.resolve()
    assert filename == "diagnostics.tar.gz"
    assert result["success"] is True
    assert archive_path.exists() is False
    assert collection.record["file_available"] is False
    assert collection.record["file_deleted_at"] is not None
