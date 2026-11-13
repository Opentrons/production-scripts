from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.routers.supplies as supplies_router
from modules.supplies.models import SupplementaryMaterialCreate
from modules.supplies.repository import SupplementaryMaterialRepository
from modules.supplies.service import SupplementaryMaterialService


@pytest.fixture
def supplies_client(tmp_path, monkeypatch):
    repository = SupplementaryMaterialRepository(tmp_path / "supplies.sqlite3")
    source = SimpleNamespace(
        source_url="https://example.com/source",
        read=lambda: [SupplementaryMaterialCreate(material_number="446-00119")],
    )
    service = SupplementaryMaterialService(repository, source)
    monkeypatch.setattr(supplies_router, "supplementary_material_service", service)
    app = FastAPI()
    app.include_router(supplies_router.router)
    with TestClient(app) as client:
        yield client, service, source


def test_manual_sync_updates_list_and_last_success(supplies_client):
    client, _, _ = supplies_client
    response = client.post("/supplies/sync")
    assert response.status_code == 200
    assert response.json()["created_count"] == 1
    result = client.get("/supplies").json()
    assert result["items"][0]["material_number"] == "446-00119"
    assert result["sync_status"]["source_url"] == "https://example.com/source"
    assert result["sync_status"]["interval_seconds"] == 3600
    assert result["sync_status"]["last_synced_at"] == response.json()["synced_at"]


def test_manual_sync_returns_502_without_erasing_saved_data(supplies_client):
    client, _, source = supplies_client
    assert client.post("/supplies/sync").status_code == 200
    def failed_read():
        raise RuntimeError("Download failed")
    source.read = failed_read
    response = client.post("/supplies/sync")
    assert response.status_code == 502
    result = client.get("/supplies").json()
    assert result["total"] == 1
    assert result["sync_status"]["last_error"] == "Download failed"


def test_manual_sync_returns_409_when_auto_sync_is_running(supplies_client):
    client, service, _ = supplies_client
    with service._sync_lock:
        assert client.get("/supplies").json()["sync_status"]["syncing"]
        assert client.post("/supplies/sync").status_code == 409
