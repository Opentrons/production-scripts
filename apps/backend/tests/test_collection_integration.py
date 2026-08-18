from __future__ import annotations

from datetime import datetime

import pytest
from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.router import router as api_router
from api.routers import integrations
from core import config
from modules.data_analysis import data as data_service


ACCESS_TOKEN = "integration-test-token-" * 2
AUTHORIZATION = {"Authorization": f"Bearer {ACCESS_TOKEN}"}


class FakeAggregateCollection:
    def __init__(self, responses: list[list[dict]]) -> None:
        self.responses = responses
        self.pipelines: list[list[dict]] = []

    def aggregate(self, pipeline: list[dict]):
        self.pipelines.append(pipeline)
        return iter(self.responses.pop(0))


class FakeDatabase:
    def __init__(self, collection: FakeAggregateCollection) -> None:
        self.collection = collection

    def list_collection_names(self) -> list[str]:
        return ["pipette_alpha", "pipette_beta", "unrelated"]

    def __getitem__(self, name: str) -> FakeAggregateCollection:
        assert name == "pipette_alpha"
        return self.collection


def _integration_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(config, "COLLECTION_DATA_ACCESS_TOKEN", ACCESS_TOKEN)
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    return TestClient(app)


def test_integration_route_requires_its_own_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = {
        "data": [],
        "count": 0,
        "limit": 200,
        "has_more": False,
        "next_cursor": None,
        "collection": "__all__",
        "snapshot_time": "2026-08-18T00:00:00Z",
    }
    monkeypatch.setattr(data_service, "get_collection_data_cursor", lambda **kwargs: expected)
    client = _integration_client(monkeypatch)

    assert client.get("/api/integrations/collection-data").status_code == 401
    client.cookies.set("production_access_token", "valid-platform-session")
    assert client.get("/api/integrations/collection-data").status_code == 401
    client.cookies.clear()
    assert client.get(
        "/api/integrations/collection-data",
        headers={"Authorization": "Bearer wrong-token"},
    ).status_code == 401

    response = client.get("/api/integrations/collection-data", headers=AUTHORIZATION)
    assert response.status_code == 200
    assert response.json() == expected


def test_integration_route_reports_unconfigured_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "COLLECTION_DATA_ACCESS_TOKEN", "")
    app = FastAPI()
    app.include_router(integrations.router, prefix="/api")
    response = TestClient(app).get(
        "/api/integrations/collection-data",
        headers=AUTHORIZATION,
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "integration.configuration_error"


def test_cursor_query_returns_only_public_fields_and_builds_next_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_id = ObjectId("64f000000000000000000003")
    second_id = ObjectId("64f000000000000000000002")
    third_id = ObjectId("64f000000000000000000001")
    collection = FakeAggregateCollection(
        responses=[
            [
                {
                    "_id": first_id,
                    "collection": "pipette_alpha",
                    "update_time": datetime(2026, 8, 18, 12, 0, 0),
                    "sn": "SN-003",
                    "model": "P1000M",
                    "type": "Opentrons",
                    "total_result": "PASS",
                    "csv_link": "must-not-be-exposed",
                },
                {
                    "_id": second_id,
                    "collection": "pipette_beta",
                    "update_time": datetime(2026, 8, 18, 11, 0, 0),
                    "serial_number": "SN-002",
                    "model": "P1000M",
                    "type": "Opentrons",
                    "total_qc_result": "FAIL",
                },
                {
                    "_id": third_id,
                    "collection": "pipette_beta",
                    "update_time": datetime(2026, 8, 18, 10, 0, 0),
                    "barcode": "SN-001",
                },
            ],
            [
                {
                    "_id": third_id,
                    "collection": "pipette_beta",
                    "update_time": datetime(2026, 8, 18, 10, 0, 0),
                    "barcode": "SN-001",
                    "model": "P50S",
                    "type": "Millipore",
                    "total_result": "PASS",
                }
            ],
        ]
    )
    monkeypatch.setattr(data_service, "get_data_database", lambda: FakeDatabase(collection))

    first_page = data_service.get_collection_data_cursor(limit=2, model="P1000M")

    assert first_page["count"] == 2
    assert first_page["has_more"] is True
    assert first_page["next_cursor"]
    assert first_page["data"][1]["sn"] == "SN-002"
    assert first_page["data"][1]["total_result"] == "FAIL"
    assert set(first_page["data"][0]) == {
        "collection",
        "update_time",
        "sn",
        "model",
        "type",
        "total_result",
    }
    assert collection.pipelines[0][-3] == {
        "$sort": {"update_time": -1, "collection": 1, "_id": -1}
    }
    assert collection.pipelines[0][-2] == {"$limit": 3}
    assert {"model": "P1000M"} in collection.pipelines[0][0]["$match"]["$and"]

    second_page = data_service.get_collection_data_cursor(
        limit=2,
        model="P1000M",
        cursor=first_page["next_cursor"],
    )

    assert second_page["count"] == 1
    assert second_page["has_more"] is False
    assert second_page["next_cursor"] is None
    assert second_page["snapshot_time"] == first_page["snapshot_time"]
    assert "$or" in collection.pipelines[1][-4]["$match"]

    with pytest.raises(data_service.InvalidCollectionCursor):
        data_service.get_collection_data_cursor(
            limit=2,
            model="P50S",
            cursor=first_page["next_cursor"],
        )


def test_invalid_cursor_returns_bad_request(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _integration_client(monkeypatch)
    response = client.get(
        "/api/integrations/collection-data?cursor=not-a-valid-cursor",
        headers=AUTHORIZATION,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "integration.invalid_cursor"


def test_model_query_parameter_is_forwarded_to_the_integration_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict = {}

    def fake_get_collection_data_cursor(**kwargs):
        calls.update(kwargs)
        return {
            "data": [],
            "count": 0,
            "limit": kwargs["limit"],
            "has_more": False,
            "next_cursor": None,
            "collection": kwargs["collection_name"],
            "snapshot_time": "2026-08-18T00:00:00Z",
        }

    monkeypatch.setattr(data_service, "get_collection_data_cursor", fake_get_collection_data_cursor)
    client = _integration_client(monkeypatch)
    response = client.get(
        "/api/integrations/collection-data",
        params={"model": "P1000M", "limit": 500},
        headers=AUTHORIZATION,
    )

    assert response.status_code == 200
    assert calls["model"] == "P1000M"
    assert calls["limit"] == 500
