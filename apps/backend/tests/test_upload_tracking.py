from __future__ import annotations

import asyncio
from io import BytesIO
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from bson import ObjectId
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
import pytest
import requests

from api.routers import uploads as uploads_router
from modules.uploads import upload as upload_service
from modules.uploads import upload_records
from modules.uploads.handler.models import UploadResult
from modules.uploads.handler.uploaders.workflows import SpreadsheetUploadPlan, SpreadsheetUploadWorkflow
from scripts import data_center_client


class MemoryUploadRecordCollection:
    def __init__(self) -> None:
        self.documents: dict[str, dict] = {}

    def insert_one(self, document: dict):
        record_id = ObjectId()
        self.documents[str(record_id)] = {**document, "_id": record_id}
        return SimpleNamespace(inserted_id=record_id)

    def create_index(self, *args, **kwargs):
        return None

    def find_one(self, query: dict):
        record = self.documents.get(str(query.get("_id"))) if "_id" in query else None
        if record is not None:
            return record
        for candidate in self.documents.values():
            if all(candidate.get(key) == value for key, value in query.items()):
                return candidate
        return None

    def find(self, query: dict | None = None):
        query = query or {}
        return MemoryCursor([
            candidate
            for candidate in self.documents.values()
            if all(candidate.get(key) == value for key, value in query.items())
        ])

    def update_one(self, query: dict, update: dict):
        record = self.documents.get(str(query.get("_id")))
        if record is None or any(record.get(key) != value for key, value in query.items() if key != "_id"):
            return SimpleNamespace(matched_count=0, modified_count=0)
        record.update(update.get("$set") or {})
        return SimpleNamespace(matched_count=1, modified_count=1)

    def update_many(self, query: dict, update: dict):
        modified = 0
        for record in self.documents.values():
            if all(record.get(key) == value for key, value in query.items()):
                record.update(update.get("$set") or {})
                modified += 1
        return SimpleNamespace(matched_count=modified, modified_count=modified)


class MemoryCursor(list):
    def sort(self, *args, **kwargs):
        return self

    def limit(self, count):
        return MemoryCursor(self[:count])


def test_precreated_record_can_capture_transport_failure(monkeypatch) -> None:
    collection = MemoryUploadRecordCollection()
    monkeypatch.setattr(upload_records, "get_upload_record_collection", lambda: collection)

    record_id = upload_records.create_upload_record(
        None,
        csv_name="assembly.csv",
        source="client",
    )
    upload_records.mark_upload_record_failed(
        record_id,
        failure_stage="request_transport",
        failure_code="client_request_failed",
        error="Upload request timed out",
        error_detail="ReadTimeout after 120 seconds",
    )

    record = collection.documents[record_id]
    assert record["csv_file"]["name"] == "assembly.csv"
    assert record["status"] == "failed"
    assert record["failure_stage"] == "request_transport"
    assert record["failure_code"] == "client_request_failed"
    assert record["error"] == "Upload request timed out"
    assert record["error_detail"] == "ReadTimeout after 120 seconds"


def test_idempotency_key_returns_existing_record(monkeypatch) -> None:
    collection = MemoryUploadRecordCollection()
    monkeypatch.setattr(upload_records, "get_upload_record_collection", lambda: collection)

    first = upload_records.create_upload_record(None, csv_name="same.csv", idempotency_key="request-1")
    second = upload_records.create_upload_record(None, csv_name="same.csv", idempotency_key="request-1")

    assert second == first
    assert len(collection.documents) == 1


def test_queue_claim_and_retry_backoff(monkeypatch, tmp_path: Path) -> None:
    collection = MemoryUploadRecordCollection()
    monkeypatch.setattr(upload_records, "get_upload_record_collection", lambda: collection)
    monkeypatch.setattr(upload_records.setting, "use_sqlite_persistence", lambda: True)
    monkeypatch.setattr(upload_records.setting, "UPLOAD_RETRY_BASE_SECONDS", 1)
    monkeypatch.setattr(upload_records.setting, "UPLOAD_RETRY_MAX_SECONDS", 1)

    csv_path = tmp_path / "same.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")
    record_id = upload_records.create_upload_record(None, csv_name=csv_path.name)
    assert upload_records.enqueue_upload_record(
        record_id,
        csv_path=str(csv_path),
        zip_path=None,
        meta={},
    )
    claimed = upload_records.claim_due_upload_record("worker-1")
    assert claimed["status"] == "running"
    assert claimed["attempt_count"] == 1
    assert upload_records.schedule_upload_retry(
        record_id,
        failure_stage="google_drive",
        failure_code="google_upload_failed",
        error="temporary 503",
    )
    retried = upload_records.get_upload_record(record_id)
    assert retried["status"] == "retrying"
    assert retried["retryable"] is True
    assert retried["retry_history"][0]["failure_code"] == "google_upload_failed"
    collection.documents[record_id]["next_retry_at"] = datetime.now() - timedelta(seconds=1)
    second_attempt = upload_records.claim_due_upload_record("worker-2")
    assert second_attempt["attempt_count"] == 2
    assert not upload_records.schedule_upload_retry(
        record_id,
        failure_stage="google_drive",
        failure_code="late_attempt_failure",
        error="late result from attempt 1",
        expected_attempt=1,
    )
    assert upload_records.get_upload_record(record_id)["status"] == "running"
    assert not upload_records.finish_upload_record(
        record_id,
        upload_success=True,
        database_success=True,
        slack_success=None,
        expected_attempt=1,
    )
    assert upload_records.get_upload_record(record_id)["status"] == "running"


def test_notification_failure_does_not_change_upload_status(monkeypatch) -> None:
    collection = MemoryUploadRecordCollection()
    monkeypatch.setattr(upload_records, "get_upload_record_collection", lambda: collection)
    record_id = upload_records.create_upload_record(None, csv_name="done.csv")
    upload_records.finish_upload_record(
        record_id,
        upload_success=True,
        database_success=True,
        slack_success=None,
        result={"finished": True},
    )
    upload_records.queue_upload_notification(
        record_id,
        result={"finished": True},
        csv_path="done.csv",
        zip_path=None,
        error_message=None,
        upload_success=True,
        database_success=True,
    )
    record = upload_records.get_upload_record(record_id)
    assert record["status"] == "success"
    assert record["notification_status"] == "queued"


def test_expired_upload_at_attempt_limit_fails_and_queues_notification(monkeypatch, tmp_path: Path) -> None:
    collection = MemoryUploadRecordCollection()
    monkeypatch.setattr(upload_records, "get_upload_record_collection", lambda: collection)
    monkeypatch.setattr(upload_records.setting, "use_sqlite_persistence", lambda: True)
    csv_path = tmp_path / "expired.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")
    record_id = upload_records.create_upload_record(None, csv_name=csv_path.name)
    assert upload_records.enqueue_upload_record(
        record_id,
        csv_path=str(csv_path),
        zip_path=None,
        meta={},
    )
    claimed = upload_records.claim_due_upload_record("worker-1")
    collection.documents[record_id]["max_attempts"] = 1
    collection.documents[record_id]["lease_expires_at"] = datetime.now() - timedelta(seconds=1)

    assert upload_records.recover_expired_upload_leases() == 0
    record = upload_records.get_upload_record(record_id)
    assert claimed["attempt_count"] == 1
    assert record["status"] == "failed"
    assert record["failure_code"] == "upload_lease_expired"
    assert record["notification_status"] == "queued"


def test_expired_notification_worker_cannot_overwrite_recovered_attempt(monkeypatch) -> None:
    collection = MemoryUploadRecordCollection()
    monkeypatch.setattr(upload_records, "get_upload_record_collection", lambda: collection)
    monkeypatch.setattr(upload_records.setting, "use_sqlite_persistence", lambda: True)
    record_id = upload_records.create_upload_record(None, csv_name="done.csv")
    upload_records.queue_upload_notification(
        record_id,
        result={"finished": True},
        csv_path="done.csv",
        zip_path=None,
        error_message=None,
        upload_success=True,
        database_success=True,
    )
    claimed = upload_records.claim_due_upload_notification("worker-1")
    assert claimed["notification_attempt_count"] == 1
    collection.documents[record_id]["notification_lease_expires_at"] = datetime.now() - timedelta(seconds=1)

    assert upload_records.recover_expired_upload_notifications() == 1
    assert not upload_records.finish_upload_notification(
        record_id,
        success=True,
        expected_attempt=1,
    )
    assert upload_records.get_upload_record(record_id)["notification_status"] == "retrying"


def test_spreadsheet_workflow_reuses_persisted_checkpoint() -> None:
    checkpoint = {
        "spreadsheet_id": "sheet-1",
        "spreadsheet_link": "https://docs.google.com/spreadsheets/d/sheet-1",
        "spreadsheet_written": True,
        "spreadsheet_archived": True,
        "raw_data_result": {"url": "https://drive.test/raw", "name": "raw-folder"},
        "database_status": {
            "saved": True,
            "workflow_complete": False,
            "missing_tests": ["current_speed"],
            "unit_tracker_uploaded": False,
        },
    }

    class CheckpointUploader:
        gdrive = SimpleNamespace(last_error=None)

        def get_upload_checkpoint(self):
            return checkpoint

        def report_progress(self, *args, **kwargs):
            return None

        def copy_new_spreadsheet(self, *args):
            pytest.fail("checkpoint should skip spreadsheet creation")

        def upload_csv_to_spreadsheet(self, *args):
            pytest.fail("checkpoint should skip spreadsheet write")

        def copy_summary_ranges(self, *args, **kwargs):
            return []

        def move_spreadsheet_to_month(self, *args, **kwargs):
            pytest.fail("checkpoint should skip spreadsheet move")

        def upload_raw_data(self, *args, **kwargs):
            pytest.fail("checkpoint should skip raw data upload")

        def log_upload_links(self, *args):
            return None

    result = UploadResult.base(sn="P1", model="P1000S", production_type="Opentrons")
    plan = SpreadsheetUploadPlan(
        yaml_cfg={"ifupdate": True, "ifcopydata": [], "ifpaste": []},
        result=result,
        file_desc={"file_path": "result.csv"},
        template_id="template",
        new_filename="new sheet",
        timestamp="20260821",
        spreadsheet_strategy="always_new",
        csv_sheet_name="Data",
        csv_range=["A"],
        tracker_sheet_name="Tracker",
        result_cell="A1",
        total_result_cell=None,
        record_writer=lambda payload: pytest.fail("checkpoint should skip database write"),
    )
    workflow = SpreadsheetUploadWorkflow(CheckpointUploader())
    workflow._set_upload_result = lambda current_plan, **kwargs: current_plan.result.set_test_result(
        upload_flag_field="assembly_qc",
        **kwargs,
    )

    workflow_result = workflow.run(plan)

    assert workflow_result["csv_link"] == checkpoint["spreadsheet_link"]
    assert workflow_result["raw_data"] == "https://drive.test/raw"
    assert workflow_result["database_saved"] is True
    assert workflow_result["missing_tests"] == ["current_speed"]


def test_client_failure_callback_does_not_overwrite_completed_record(monkeypatch) -> None:
    collection = MemoryUploadRecordCollection()
    monkeypatch.setattr(upload_records, "get_upload_record_collection", lambda: collection)
    record_id = upload_records.create_upload_record(None, csv_name="complete.csv")
    upload_records.finish_upload_record(
        record_id,
        upload_success=True,
        database_success=True,
        slack_success=True,
        result={"finished": True},
    )

    upload_records.mark_upload_record_failed(
        record_id,
        failure_stage="request_transport",
        failure_code="client_request_failed",
        error="Late client timeout",
    )

    record = collection.documents[record_id]
    assert record["status"] == "success"
    assert record["error"] is None


def test_upload_record_start_and_failure_routes(monkeypatch) -> None:
    captured = {}
    record_id = str(ObjectId())
    monkeypatch.setattr(upload_records, "create_upload_record", lambda *args, **kwargs: record_id)

    def capture_failure(received_record_id, **fields):
        captured.update({"record_id": received_record_id, **fields})

    monkeypatch.setattr(upload_records, "mark_upload_record_failed", capture_failure)
    app = FastAPI()
    app.include_router(uploads_router.data_center_client_router, prefix="/api")
    client = TestClient(app)

    started = client.post(
        "/api/upload-records/start",
        json={"csv_file_name": "result.csv", "source": "client"},
    )
    assert started.status_code == 200
    assert started.json()["record_id"] == record_id

    failed = client.post(
        f"/api/upload-records/{record_id}/fail",
        json={
            "failure_stage": "request_transport",
            "failure_code": "client_request_failed",
            "message": "Connection reset",
            "detail": "RemoteDisconnected",
        },
    )
    assert failed.status_code == 200
    assert captured == {
        "record_id": record_id,
        "failure_stage": "request_transport",
        "failure_code": "client_request_failed",
        "error": "Connection reset",
        "error_detail": "RemoteDisconnected",
    }


def test_failure_stage_prefers_structured_result_and_current_step() -> None:
    assert upload_service.infer_upload_failure_stage(
        {"database_saved": False, "error": "connection refused"},
        None,
        "database",
    ) == ("database", "database_write_failed")
    assert upload_service.infer_upload_failure_stage(
        {"error": "创建或复用 Google Spreadsheet 失败"},
        None,
        "prepare_spreadsheet",
    ) == ("prepare_spreadsheet", "prepare_spreadsheet_failed")
    assert upload_service.infer_upload_failure_stage(
        {"error": "CSV 数据写入失败"},
        None,
        "write_spreadsheet",
    ) == ("write_spreadsheet", "write_spreadsheet_failed")


def test_manual_upload_invalid_meta_is_recorded_as_validation_failure(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(upload_records, "update_upload_record", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        upload_service,
        "finish_failed_upload",
        lambda record_id, **fields: captured.update({"record_id": record_id, **fields}),
    )
    upload_file = UploadFile(filename="result.csv", file=BytesIO(b"header\n"))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            upload_service.upload_manual_data(
                upload_file,
                meta="[]",
                upload_record_id="record-1",
            )
        )

    assert exc_info.value.status_code == 400
    assert captured["failure_stage"] == "request_validation"
    assert captured["failure_code"] == "invalid_manual_metadata"


def test_manual_upload_streams_and_checks_expected_integrity(monkeypatch, tmp_path: Path) -> None:
    captured = {}
    monkeypatch.setattr(upload_records, "update_upload_record", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        upload_service,
        "finish_failed_upload",
        lambda record_id, **fields: captured.update({"record_id": record_id, **fields}),
    )
    monkeypatch.setattr(
        upload_records,
        "get_upload_record",
        lambda record_id: {
            "status": "running",
            "csv_file": {"expected_size": 99, "expected_sha256": "0" * 64},
        },
    )
    upload_file = UploadFile(filename="result.csv", file=BytesIO(b"header\n"))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            upload_service.upload_manual_data(
                upload_file,
                upload_record_id="record-2",
            )
        )

    assert exc_info.value.status_code == 422
    assert captured["failure_stage"] == "file_integrity"
    assert captured["failure_code"] == "csv_integrity_check_failed"


def test_data_center_client_extracts_server_error_and_stage() -> None:
    response = requests.Response()
    response.status_code = 422
    response._content = (
        b'{"detail":{"message":"CSV parse failed","error":"missing serial number"}}'
    )
    error = requests.HTTPError("422 Client Error", response=response)

    assert data_center_client.request_error_detail(error) == (
        "CSV parse failed: missing serial number"
    )
    assert data_center_client.request_failure_classification(error) == (
        "request_validation",
        "http_422",
    )


def test_data_center_client_confirms_queued_job_after_timeout(monkeypatch) -> None:
    response = requests.Response()
    response.status_code = 504
    error = requests.HTTPError("gateway timeout", response=response)
    monkeypatch.setattr(
        data_center_client,
        "get_upload_record_status",
        lambda record_id: {
            "record_id": record_id,
            "status": "queued",
            "job_enqueued": True,
        },
    )
    monkeypatch.setattr(
        data_center_client,
        "mark_upload_record_failed",
        lambda *args, **kwargs: pytest.fail("queued work must not be marked failed"),
    )

    result = data_center_client.resolve_uncertain_upload_request("record-3", error)

    assert result["success"] is True
    assert result["pending"] is True


def test_data_center_client_aborts_when_record_cannot_be_created(monkeypatch) -> None:
    monkeypatch.setattr(data_center_client, "BASE_URL", "http://data-center.test")
    monkeypatch.setattr(data_center_client, "start_upload_record", lambda *args, **kwargs: None)
    post_called = False

    def unexpected_post(*args, **kwargs):
        nonlocal post_called
        post_called = True

    monkeypatch.setattr(data_center_client.requests, "post", unexpected_post)

    result = data_center_client.upload_data("result.csv", "source.zip")

    assert result == {"error": "Unable to create upload record", "success": False}
    assert post_called is False
