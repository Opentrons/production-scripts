from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

import pytest

from modules.robots import diagnostic_logs


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


class FakeListCursor(list):
    def sort(self, key: str, direction: int):
        reverse = direction < 0
        return FakeListCursor(sorted(self, key=lambda item: item.get(key) or "", reverse=reverse))

    def skip(self, count: int):
        return FakeListCursor(self[count:])

    def limit(self, count: int):
        return FakeListCursor(self[:count])


class FakeListCollection:
    def __init__(self, documents: list[dict]) -> None:
        self.documents = deepcopy(documents)

    def _matched(self, query: dict) -> list[dict]:
        return [
            deepcopy(document)
            for document in self.documents
            if all(document.get(key) == value for key, value in query.items())
        ]

    def count_documents(self, query: dict) -> int:
        return len(self._matched(query))

    def find(self, query: dict):
        return FakeListCursor(self._matched(query))


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


def test_list_download_records_filters_by_robot_ip_before_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = FakeListCollection(
        [
            {
                "_id": "record-a-new",
                "robot_ip": "192.168.1.101",
                "started_at": "2026-08-12T02:00:00+00:00",
                "archive_path": None,
            },
            {
                "_id": "record-b",
                "robot_ip": "192.168.1.102",
                "started_at": "2026-08-12T03:00:00+00:00",
                "archive_path": None,
            },
            {
                "_id": "record-a-old",
                "robot_ip": "192.168.1.101",
                "started_at": "2026-08-12T01:00:00+00:00",
                "archive_path": None,
            },
        ]
    )
    monkeypatch.setattr(diagnostic_logs, "_get_collection", lambda: collection)

    first_page = diagnostic_logs.list_download_records(
        page=1,
        page_size=1,
        robot_ip=" 192.168.1.101 ",
    )
    second_page = diagnostic_logs.list_download_records(
        page=2,
        page_size=1,
        robot_ip="192.168.1.101",
    )

    assert first_page["total"] == 2
    assert [record["_id"] for record in first_page["records"]] == ["record-a-new"]
    assert [record["_id"] for record in second_page["records"]] == ["record-a-old"]


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


def test_fail_interrupted_downloads_marks_running_record_and_command_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now_running = {
        "_id": "record-running",
        "task_id": "task-1",
        "robot_ip": "192.168.1.101",
        "status": "running",
        "progress": 14,
        "current_step": "收集服务数据",
        "remote_diag_path": "/data/.flex-diagnostics-abc",
        "remote_archive_path": "/data/.flex-diagnostics-abc.tar.gz",
        "cleanup_status": "not_started",
        "command_logs": [
            {
                "id": "cmd-1",
                "label": "初始化诊断目录",
                "command": "mkdir",
                "status": "success",
                "started_at": "2026-08-05T07:35:15+00:00",
                "finished_at": "2026-08-05T07:35:16+00:00",
                "output": "",
                "error": None,
            },
            {
                "id": "cmd-2",
                "label": "收集服务数据",
                "command": "cp -r",
                "status": "running",
                "started_at": "2026-08-05T07:39:41+00:00",
                "finished_at": None,
                "output": "",
                "error": None,
            },
        ],
    }
    queued = {
        "_id": "record-queued",
        "task_id": "task-2",
        "robot_ip": "192.168.1.102",
        "status": "queued",
        "progress": 0,
        "current_step": "等待下载",
        "remote_diag_path": None,
        "remote_archive_path": None,
        "cleanup_status": "not_started",
        "command_logs": [],
    }

    class InterruptCollection:
        def __init__(self) -> None:
            self.documents = {
                now_running["_id"]: deepcopy(now_running),
                queued["_id"]: deepcopy(queued),
            }
            self.scheduled: list[dict] = []

        def find(self, query: dict):
            statuses = set((query.get("status") or {}).get("$in") or [])
            return [
                deepcopy(document)
                for document in self.documents.values()
                if document.get("status") in statuses
            ]

        def update_one(self, query: dict, update: dict) -> None:
            document = self.documents.get(query.get("_id"))
            if document is not None:
                document.update(deepcopy(update.get("$set", {})))

    collection = InterruptCollection()
    monkeypatch.setattr(diagnostic_logs, "_get_collection", lambda: collection)
    monkeypatch.setattr(
        diagnostic_logs,
        "_schedule_pending_cleanup",
        lambda record, **_kwargs: collection.scheduled.append(deepcopy(record)) or True,
    )

    marked = diagnostic_logs.fail_interrupted_diagnostic_log_downloads()

    assert marked == 2
    running = collection.documents["record-running"]
    assert running["status"] == "failed"
    assert running["error"] == diagnostic_logs.INTERRUPTED_BY_RESTART_MESSAGE
    assert running["cleanup_status"] == "pending"
    assert running["current_step"] == "下载失败，设备残留待清理"
    assert running["command_logs"][1]["status"] == "failed"
    assert running["command_logs"][1]["error"] == diagnostic_logs.INTERRUPTED_BY_RESTART_MESSAGE
    assert len(collection.scheduled) == 1
    assert collection.scheduled[0]["_id"] == "record-running"

    waiting = collection.documents["record-queued"]
    assert waiting["status"] == "failed"
    assert waiting["error"] == diagnostic_logs.INTERRUPTED_BY_RESTART_MESSAGE
    assert waiting["command_logs"][-1]["label"] == "任务中断"
    assert waiting["command_logs"][-1]["error"] == diagnostic_logs.INTERRUPTED_BY_RESTART_MESSAGE
    assert waiting["cleanup_status"] == "not_started"


def test_legacy_absolute_archive_path_remaps_to_current_download_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    download_root = tmp_path / "robot_logs"
    relative = Path("2026-08-06/GRAV1_192.168.6.123_ac890e01/diag.tar.gz")
    archive_path = download_root / relative
    archive_path.parent.mkdir(parents=True)
    archive_path.write_bytes(b"archive")

    record = {
        "_id": "record-legacy",
        "archive_path": f"/data/temp/robot_logs/{relative.as_posix()}",
        "archive_name": "diag.tar.gz",
        "server_directory": f"/data/temp/robot_logs/{relative.parent.as_posix()}",
        "file_deleted_at": None,
    }
    monkeypatch.setattr(diagnostic_logs.setting, "ROBOT_LOG_DOWNLOAD_DIR", str(download_root))

    resolved = diagnostic_logs._resolve_record_archive_path(record)
    serialized = diagnostic_logs._serialize_record(record)

    assert resolved == archive_path.resolve()
    assert serialized["file_available"] is True
    assert serialized["file_unavailable_reason"] is None
