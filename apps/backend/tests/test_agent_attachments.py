from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient

from core import config
from modules.agent import attachment_store
from modules.agent.routes import router as agent_router
from modules.auth.dependencies import require_authenticated_user
from modules.auth.store import AuthUser


def save_upload(content: bytes, *, filename: str = "results.csv", owner_id: str = "user-1") -> dict:
    upload = UploadFile(file=BytesIO(content), filename=filename)
    return asyncio.run(attachment_store.save_attachment(upload, owner_id))


def test_attachment_is_stored_and_csv_inspection_scans_complete_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "AGENT_ATTACHMENT_DIR", tmp_path)
    content = (
        "barcode,result,value\n"
        "P100,pass,1\n"
        "P101,fail,\n"
        "P101,fail,\n"
    ).encode()
    saved = save_upload(content)

    assert saved["size"] == len(content)
    assert (tmp_path / f"{saved['id']}.data").read_bytes() == content

    token = attachment_store.set_attachment_scope("user-1", {saved["id"]})
    try:
        result = attachment_store.inspect_attachment(saved["id"])
    finally:
        attachment_store.reset_attachment_scope(token)

    assert result["complete_file_scanned"] is True
    assert result["csv"]["row_count"] == 3
    assert result["csv"]["duplicate_rows"] == 1
    assert result["csv"]["columns"][2]["blank_count"] == 2


def test_attachment_reading_is_paginated_without_silent_truncation(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "AGENT_ATTACHMENT_DIR", tmp_path)
    content = ("0123456789" * 300).encode()
    saved = save_upload(content, filename="run.log")

    token = attachment_store.set_attachment_scope("user-1", {saved["id"]})
    try:
        first = attachment_store.read_attachment(saved["id"], max_chars=1_000)
        second = attachment_store.read_attachment(saved["id"], offset=first["next_offset"], max_chars=2_000)
    finally:
        attachment_store.reset_attachment_scope(token)

    assert first["has_more"] is True
    assert first["next_offset"] == 1_000
    assert first["content"] + second["content"] == content.decode()
    assert second["has_more"] is False
    assert second["next_offset"] is None


def test_attachment_scope_blocks_other_users_and_unreferenced_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "AGENT_ATTACHMENT_DIR", tmp_path)
    saved = save_upload(b"private", filename="private.txt")

    for owner_id, allowed_ids in (("user-2", {saved["id"]}), ("user-1", set())):
        token = attachment_store.set_attachment_scope(owner_id, allowed_ids)
        try:
            with pytest.raises(attachment_store.AttachmentNotFoundError):
                attachment_store.read_attachment(saved["id"])
        finally:
            attachment_store.reset_attachment_scope(token)


def test_attachment_rejects_files_over_five_megabytes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "AGENT_ATTACHMENT_DIR", tmp_path)
    upload = UploadFile(
        file=BytesIO(b"x" * (attachment_store.MAX_ATTACHMENT_BYTES + 1)),
        filename="large.csv",
    )

    with pytest.raises(attachment_store.AttachmentTooLargeError, match="5 MB"):
        asyncio.run(attachment_store.save_attachment(upload, "user-1"))

    assert list(tmp_path.iterdir()) == []


def test_attachment_accepts_exactly_five_megabytes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "AGENT_ATTACHMENT_DIR", tmp_path)
    content = b"x" * attachment_store.MAX_ATTACHMENT_BYTES

    saved = save_upload(content, filename="limit.txt")

    assert saved["size"] == attachment_store.MAX_ATTACHMENT_BYTES
    assert (tmp_path / f"{saved['id']}.data").stat().st_size == attachment_store.MAX_ATTACHMENT_BYTES


def test_attachment_routes_upload_and_delete_for_authenticated_user(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "AGENT_ATTACHMENT_DIR", tmp_path)
    user = AuthUser(
        id="user-1",
        username="operator",
        display_name="Operator",
        role="operator",
        password_hash="unused",
        disabled=False,
        token_version=1,
    )
    app = FastAPI()
    app.include_router(agent_router)
    app.dependency_overrides[require_authenticated_user] = lambda: user
    client = TestClient(app)

    response = client.post(
        "/agent/attachments",
        files={"file": ("results.csv", b"barcode,result\nP100,pass\n", "text/csv")},
    )

    assert response.status_code == 201
    attachment = response.json()
    assert attachment["name"] == "results.csv"
    assert (tmp_path / f"{attachment['id']}.data").is_file()
    assert client.delete(f"/agent/attachments/{attachment['id']}").status_code == 204
    assert list(tmp_path.iterdir()) == []
