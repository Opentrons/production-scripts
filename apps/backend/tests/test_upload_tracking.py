from __future__ import annotations

import asyncio
from io import BytesIO
from types import SimpleNamespace

from bson import ObjectId
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
import pytest
import requests

from api.routers import uploads as uploads_router
from modules.uploads import upload as upload_service
from modules.uploads import upload_records
from scripts import data_center_client


class MemoryUploadRecordCollection:
    def __init__(self) -> None:
        self.documents: dict[str, dict] = {}

    def insert_one(self, document: dict):
        record_id = ObjectId()
        self.documents[str(record_id)] = {**document, "_id": record_id}
        return SimpleNamespace(inserted_id=record_id)

    def update_one(self, query: dict, update: dict):
        record = self.documents.get(str(query.get("_id")))
        if record is None or any(record.get(key) != value for key, value in query.items() if key != "_id"):
            return SimpleNamespace(matched_count=0, modified_count=0)
        record.update(update.get("$set") or {})
        return SimpleNamespace(matched_count=1, modified_count=1)


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
