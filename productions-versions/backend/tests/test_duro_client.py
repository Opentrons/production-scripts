from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from duro.client import DuroAuthenticationError, DuroClient
from duro.models import DuroProductSearchRequest


def make_token(expires_at: datetime) -> str:
    def encode(value: dict[str, object]) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{encode({'alg': 'none'})}.{encode({'exp': int(expires_at.timestamp())})}.signature"


class FakeResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {
            "success": True,
            "data": {
                "count": 1,
                "results": [
                    {
                        "_id": "product-id",
                        "name": "FLEX GRIPPER",
                        "revision": "C1.2",
                        "status": "PRODUCTION",
                        "lastModified": 1781136833514,
                    }
                ],
            },
        }


class FakeSession:
    def __init__(self, get_response: FakeResponse | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.get_response = get_response or FakeResponse()

    def post(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return FakeResponse()

    def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.get_response


class FakeProductBomResponse(FakeResponse):
    def json(self):
        return {
            "success": True,
            "data": {
                "_id": "product-id",
                "name": "FLEX GRIPPER",
                "children": [
                    {
                        "_id": "relationship-id",
                        "quantity": 2,
                        "component": {"_id": "component-id", "name": "Jaw", "children": []},
                    }
                ],
            },
        }


def test_search_products_sends_bearer_token_and_browser_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    token = make_token(datetime.now(timezone.utc) + timedelta(hours=1))
    monkeypatch.setenv("PRODUCTIONS_VERSIONS_DURO_TOKEN", token)
    session = FakeSession()
    client = DuroClient(token_path=tmp_path / "missing", session=session)  # type: ignore[arg-type]

    response = client.search_products(DuroProductSearchRequest())

    assert response.count == 1
    assert response.products[0].id == "product-id"
    assert response.products[0].name == "FLEX GRIPPER"
    call = session.calls[0]
    assert call["url"] == "https://mfg.duro.app/v1/search/products"
    assert call["headers"]["authorization"] == f"Bearer {token}"  # type: ignore[index]
    assert call["json"] == {
        "page": 1,
        "sort": "lastModified",
        "reverse": True,
        "limit": 0,
        "lean": False,
        "populate": "images",
    }


def test_expired_token_is_rejected_before_network_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        "PRODUCTIONS_VERSIONS_DURO_TOKEN",
        make_token(datetime.now(timezone.utc) - timedelta(minutes=1)),
    )
    session = FakeSession()
    client = DuroClient(token_path=tmp_path / "missing", session=session)  # type: ignore[arg-type]

    with pytest.raises(DuroAuthenticationError, match="已过期"):
        client.search_products(DuroProductSearchRequest())

    assert session.calls == []


def test_get_product_requests_lean_children(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    token = make_token(datetime.now(timezone.utc) + timedelta(hours=1))
    monkeypatch.setenv("PRODUCTIONS_VERSIONS_DURO_TOKEN", token)
    session = FakeSession(FakeProductBomResponse())
    client = DuroClient(token_path=tmp_path / "missing", session=session)  # type: ignore[arg-type]

    product = client.get_product("product-id")

    assert product["children"][0]["component"]["_id"] == "component-id"
    call = session.calls[0]
    assert call["url"] == "https://mfg.duro.app/v1/products/product-id"
    assert call["params"] == {"include": "children", "lean": "true"}
    assert call["headers"]["authorization"] == f"Bearer {token}"  # type: ignore[index]
