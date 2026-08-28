from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

from modules.duro.client import DuroAuthenticationError, DuroClient
from modules.duro.models import DuroProductSearchRequest


def make_api_key(expires_at: datetime) -> str:
    def encode(value: dict[str, object]) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{encode({'alg': 'none'})}.{encode({'exp': int(expires_at.timestamp())})}.signature"


class FakeGraphqlResponse:
    def __init__(self, body: dict[str, object], status_code: int = 200) -> None:
        self.body = body
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self.body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeGraphqlSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> FakeGraphqlResponse:
        self.calls.append({"url": url, **kwargs})
        request_body = kwargs.get("json")
        query = request_body.get("query", "") if isinstance(request_body, dict) else ""
        if "productsByIds" in query:
            return FakeGraphqlResponse(
                {
                    "data": {
                        "productsByIds": [
                            {
                                "id": "product-id",
                                "name": "FLEX GRIPPER",
                                "revisionValue": "C1.2",
                                "cpn": {"displayValue": "999-00001", "variant": "00"},
                                "children": [
                                    {
                                        "quantity": 2,
                                        "component": {
                                            "id": "component-id",
                                            "name": "Jaw",
                                            "revisionValue": "A1.0",
                                            "cpn": {
                                                "displayValue": "123-00001",
                                                "variant": "01",
                                            },
                                            "children": [{"component": {"id": "leaf-id"}}],
                                        },
                                    }
                                ],
                            }
                        ]
                    }
                }
            )
        if "componentsByIds" in query:
            return FakeGraphqlResponse(
                {
                    "data": {
                        "componentsByIds": [
                            {
                                "id": "component-id",
                                "name": "Jaw",
                                "revisionValue": "A1.0",
                                "children": [],
                            }
                        ]
                    }
                }
            )
        return FakeGraphqlResponse(
            {
                "data": {
                    "products": {
                        "connection": {
                            "totalCount": 1,
                            "pageInfo": {"hasNextPage": False, "endCursor": "cursor"},
                            "edges": [
                                {
                                    "node": {
                                        "id": "product-id",
                                        "name": "FLEX GRIPPER",
                                        "revisionValue": "C1.2",
                                        "status": "PRODUCTION",
                                        "lastModified": "2026-06-11T00:00:00.000Z",
                                        "cpn": {
                                            "displayValue": "999-00001",
                                            "variant": "00",
                                        },
                                        "images": [
                                            {
                                                "id": "image-id",
                                                "src": "https://example.test/product.png",
                                                "archived": False,
                                            }
                                        ],
                                    }
                                }
                            ],
                        }
                    }
                }
            }
        )


class FakeRestSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    @staticmethod
    def _product() -> dict[str, object]:
        return {
            "_id": "product-id",
            "name": "FLEX GRIPPER",
            "revision": "C1.2",
            "cpn": "999-00001",
            "cpnVariant": "00",
            "images": [{"_id": "image-id", "src": "https://example.test/product.png"}],
            "children": [
                {
                    "quantity": 2,
                    "component": {
                        "_id": "component-id",
                        "name": "Jaw",
                        "revision": "A1.0",
                        "cpn": "123-00001",
                        "children": [{"component": {"_id": "leaf-id"}}],
                    },
                }
            ],
        }

    def get(self, url: str, **kwargs: object) -> FakeGraphqlResponse:
        self.calls.append({"method": "GET", "url": url, **kwargs})
        if "/products/" in url:
            body = {"success": True, "data": self._product()}
        else:
            body = {
                "success": True,
                "data": {
                    "_id": "component-id",
                    "name": "Jaw",
                    "revision": "A1.0",
                    "cpn": "123-00001",
                    "children": [],
                },
            }
        return FakeGraphqlResponse(body)

    def post(self, url: str, **kwargs: object) -> FakeGraphqlResponse:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return FakeGraphqlResponse(
            {
                "success": True,
                "data": {"count": 1, "results": [self._product()]},
            }
        )


class RestSearchUnauthorizedSession(FakeGraphqlSession):
    def post(self, url: str, **kwargs: object) -> FakeGraphqlResponse:
        if url.endswith("/search/products"):
            self.calls.append({"url": url, **kwargs})
            return FakeGraphqlResponse(
                {
                    "success": False,
                    "errors": [{"message": "You are not authorized to perform this action."}],
                },
                status_code=500,
            )
        return super().post(url, **kwargs)


class CanonicalComponentRestSession(FakeRestSession):
    def get(self, url: str, **kwargs: object) -> FakeGraphqlResponse:
        response = super().get(url, **kwargs)
        if "/components/" in url:
            response.body["data"]["cpn"] = "438-00601"  # type: ignore[index]
        return response


class UnauthorizedSession(FakeGraphqlSession):
    def post(self, url: str, **kwargs: object) -> FakeGraphqlResponse:
        self.calls.append({"url": url, **kwargs})
        return FakeGraphqlResponse(
            {"errors": [{"message": "Unauthorized"}]},
            status_code=500,
        )


def test_api_key_uses_rest_and_maps_product_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    api_key = make_api_key(datetime.now(timezone.utc) + timedelta(days=30))
    session = FakeRestSession()
    client = DuroClient(
        api_key=api_key,
        api_key_path=tmp_path / "missing-api-key",
        session=session,  # type: ignore[arg-type]
    )

    response = client.search_products(DuroProductSearchRequest())

    assert response.count == 1
    assert response.products[0].id == "product-id"
    assert response.products[0].cpn == "999-00001"
    assert response.products[0].cpn_variant == "00"
    assert response.products[0].revision == "C1.2"
    assert response.products[0].images[0]["_id"] == "image-id"
    call = session.calls[0]
    assert call["url"] == "https://mfgapi.duro.app/v1/search/products"
    assert call["headers"]["apiToken"] == api_key  # type: ignore[index]
    assert "authorization" not in call["headers"]  # type: ignore[operator]
    assert call["json"] == DuroProductSearchRequest().model_dump(exclude_none=True)  # type: ignore[index]


def test_product_search_falls_back_to_graphql_when_rest_search_is_forbidden(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    api_key = make_api_key(datetime.now(timezone.utc) + timedelta(days=30))
    session = RestSearchUnauthorizedSession()
    client = DuroClient(
        api_key=api_key,
        api_key_path=tmp_path / "missing-api-key",
        session=session,  # type: ignore[arg-type]
    )

    response = client.search_products(DuroProductSearchRequest())

    assert response.products[0].cpn == "999-00001"
    assert session.calls[0]["url"] == "https://mfgapi.duro.app/v1/search/products"
    assert session.calls[1]["url"] == "https://mfg-core-api.duro.app/graphql"


def test_rest_component_preserves_canonical_cpn(tmp_path: Path) -> None:
    session = CanonicalComponentRestSession()
    client = DuroClient(
        api_key=make_api_key(datetime.now(timezone.utc) + timedelta(days=30)),
        api_key_path=tmp_path / "missing-api-key",
        session=session,  # type: ignore[arg-type]
    )

    component = client.get_component("642336d81ee9c10008052c00")

    assert component["_id"] == "component-id"
    assert component["cpn"] == "438-00601"
    assert session.calls[0]["url"] == (
        "https://mfgapi.duro.app/v1/components/642336d81ee9c10008052c00"
    )
    assert session.calls[0]["params"] == {"include": "children", "lean": "true"}


def test_missing_api_key_is_rejected_before_network_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    session = FakeRestSession()
    client = DuroClient(
        api_key_path=tmp_path / "missing-api-key",
        session=session,  # type: ignore[arg-type]
    )

    with pytest.raises(DuroAuthenticationError, match="未配置 Duro API Key"):
        client.search_products(DuroProductSearchRequest())

    assert session.calls == []


def test_expired_api_key_is_rejected_before_network_request(tmp_path: Path) -> None:
    session = FakeRestSession()
    client = DuroClient(
        api_key=make_api_key(datetime.now(timezone.utc) - timedelta(minutes=1)),
        api_key_path=tmp_path / "missing-api-key",
        session=session,  # type: ignore[arg-type]
    )

    with pytest.raises(DuroAuthenticationError, match="API Key 已过期"):
        client.search_products(DuroProductSearchRequest())

    assert session.calls == []


def test_graphql_unauthorized_is_reported_as_authentication_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        "PRODUCTION_PLATFORM_DURO_API_KEY",
        make_api_key(datetime.now(timezone.utc) + timedelta(days=30)),
    )
    client = DuroClient(
        api_key_path=tmp_path / "missing-api-key",
        session=UnauthorizedSession(),  # type: ignore[arg-type]
    )

    with pytest.raises(DuroAuthenticationError, match="未被接受"):
        client.search_products(DuroProductSearchRequest())


def test_api_key_file_is_used_for_product_and_component_bom(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    api_key = make_api_key(datetime.now(timezone.utc) + timedelta(days=30))
    api_key_path = tmp_path / "duro-api-key.txt"
    api_key_path.write_text(api_key, encoding="utf-8")
    session = FakeRestSession()
    client = DuroClient(
        api_key_path=api_key_path,
        session=session,  # type: ignore[arg-type]
    )

    product = client.get_product("product-id")
    component = client.get_component("component-id")

    assert product["_id"] == "product-id"
    assert product["revision"] == "C1.2"
    child = product["children"][0]["component"]
    assert child["_id"] == "component-id"
    assert child["cpn"] == "123-00001"
    assert child["children"][0]["component"]["_id"] == "leaf-id"
    assert component["_id"] == "component-id"
    assert all(call["headers"]["apiToken"] == api_key for call in session.calls)  # type: ignore[index]


def test_update_api_key_persists_and_reports_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    old_key = make_api_key(datetime.now(timezone.utc) + timedelta(days=1))
    new_expiry = datetime.now(timezone.utc) + timedelta(days=30)
    new_key = make_api_key(new_expiry)
    api_key_path = tmp_path / "credentials" / "duro-api-key.txt"
    monkeypatch.setenv("PRODUCTION_PLATFORM_DURO_API_KEY", old_key)
    client = DuroClient(api_key_path=api_key_path)

    status = client.update_api_key(f"Bearer {new_key}")

    assert status.configured is True
    assert status.api_key_valid is True
    assert status.api_key_expires_at is not None
    assert abs(status.api_key_expires_at.timestamp() - new_expiry.timestamp()) < 1
    assert api_key_path.read_text(encoding="utf-8").strip() == new_key
    assert api_key_path.stat().st_mode & 0o777 == 0o600
    assert client._api_key() == new_key
    assert DuroClient(api_key_path=api_key_path)._api_key() == new_key


def test_update_api_key_rejects_expired_value(tmp_path: Path) -> None:
    api_key_path = tmp_path / "duro-api-key.txt"
    client = DuroClient(api_key_path=api_key_path)

    with pytest.raises(DuroAuthenticationError, match="已过期"):
        client.update_api_key(
            make_api_key(datetime.now(timezone.utc) - timedelta(minutes=1))
        )

    assert not api_key_path.exists()
