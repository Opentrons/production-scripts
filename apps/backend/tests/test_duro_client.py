from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from modules.duro.client import DuroAuthenticationError, DuroClient
from modules.duro.models import DuroProductSearchRequest


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


class FakeGraphqlResponse(FakeResponse):
    def __init__(self, body: dict[str, object], status_code: int = 200) -> None:
        self.body = body
        self.status_code = status_code

    def json(self):
        return self.body


class FakeGraphqlSession(FakeSession):
    def post(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        query = kwargs.get("json", {}).get("query", "")
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


class FakeUnauthorizedResponse(FakeResponse):
    status_code = 500

    def raise_for_status(self) -> None:
        import requests

        raise requests.HTTPError("500 Server Error")

    def json(self):
        return {"success": False, "errors": [{"message": "Unauthorized"}]}


class UnauthorizedSession(FakeSession):
    def __init__(self) -> None:
        super().__init__()

    def post(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return FakeUnauthorizedResponse()


class TokenFallbackSession(FakeSession):
    def __init__(self, rejected_token: str) -> None:
        super().__init__()
        self.rejected_token = rejected_token

    def post(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        authorization = kwargs.get("headers", {}).get("authorization")
        if authorization == f"Bearer {self.rejected_token}":
            return FakeUnauthorizedResponse()
        return FakeResponse()


class FakeBrowserTokenProvider:
    def __init__(self, token: str) -> None:
        self.token = token
        self.calls: list[bool] = []

    def get_access_token(self, force: bool = False) -> str:
        self.calls.append(force)
        return self.token


def test_search_products_sends_bearer_token_and_browser_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    token = make_token(datetime.now(timezone.utc) + timedelta(hours=1))
    monkeypatch.setenv("PRODUCTION_PLATFORM_DURO_TOKEN", token)
    session = FakeSession()
    client = DuroClient(
        api_key_path=tmp_path / "missing-api-key",
        token_path=tmp_path / "missing",
        cookies_path=tmp_path / "missing-cookies",
        session=session,  # type: ignore[arg-type]
    )

    response = client.search_products(DuroProductSearchRequest())

    assert response.count == 1
    assert response.products[0].id == "product-id"
    assert response.products[0].name == "FLEX GRIPPER"
    call = session.calls[0]
    assert call["url"] == "https://mfgapi.duro.app/v1/search/products"
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
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    monkeypatch.setenv(
        "PRODUCTION_PLATFORM_DURO_TOKEN",
        make_token(datetime.now(timezone.utc) - timedelta(minutes=1)),
    )
    session = FakeSession()
    client = DuroClient(
        api_key_path=tmp_path / "missing-api-key",
        token_path=tmp_path / "missing",
        cookies_path=tmp_path / "missing-cookies",
        session=session,  # type: ignore[arg-type]
    )

    with pytest.raises(DuroAuthenticationError, match="已过期"):
        client.search_products(DuroProductSearchRequest())

    assert session.calls == []


def test_expired_explicit_token_falls_back_to_remote_chrome(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    monkeypatch.setenv(
        "PRODUCTION_PLATFORM_DURO_TOKEN",
        make_token(datetime.now(timezone.utc) - timedelta(minutes=1)),
    )
    browser_token = make_token(datetime.now(timezone.utc) + timedelta(hours=1))
    provider = FakeBrowserTokenProvider(browser_token)
    session = FakeSession()
    client = DuroClient(
        api_key_path=tmp_path / "missing-api-key",
        token_path=tmp_path / "missing",
        cookies_path=tmp_path / "missing-cookies",
        browser_token_provider=provider,  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
    )

    response = client.search_products(DuroProductSearchRequest())

    assert response.count == 1
    assert provider.calls == [False]
    assert session.calls[0]["headers"]["authorization"] == f"Bearer {browser_token}"  # type: ignore[index]


def test_rejected_explicit_token_retries_with_remote_chrome(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    explicit_token = make_token(datetime.now(timezone.utc) + timedelta(hours=1))
    browser_token = make_token(datetime.now(timezone.utc) + timedelta(hours=2))
    monkeypatch.setenv("PRODUCTION_PLATFORM_DURO_TOKEN", explicit_token)
    provider = FakeBrowserTokenProvider(browser_token)
    session = TokenFallbackSession(explicit_token)
    client = DuroClient(
        api_key_path=tmp_path / "missing-api-key",
        token_path=tmp_path / "missing",
        cookies_path=tmp_path / "missing-cookies",
        browser_token_provider=provider,  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
    )

    response = client.search_products(DuroProductSearchRequest())

    assert response.count == 1
    assert provider.calls == [True]
    assert len(session.calls) == 2
    assert session.calls[0]["headers"]["authorization"] == f"Bearer {explicit_token}"  # type: ignore[index]
    assert session.calls[1]["headers"]["authorization"] == f"Bearer {browser_token}"  # type: ignore[index]


def test_get_product_requests_lean_children(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    token = make_token(datetime.now(timezone.utc) + timedelta(hours=1))
    monkeypatch.setenv("PRODUCTION_PLATFORM_DURO_TOKEN", token)
    session = FakeSession(FakeProductBomResponse())
    client = DuroClient(
        api_key_path=tmp_path / "missing-api-key",
        token_path=tmp_path / "missing",
        cookies_path=tmp_path / "missing-cookies",
        session=session,  # type: ignore[arg-type]
    )

    product = client.get_product("product-id")

    assert product["children"][0]["component"]["_id"] == "component-id"
    call = session.calls[0]
    assert call["url"] == "https://mfgapi.duro.app/v1/products/product-id"
    assert call["params"] == {"include": "children", "lean": "true"}
    assert call["headers"]["authorization"] == f"Bearer {token}"  # type: ignore[index]


def test_api_key_uses_graphql_api_token_and_maps_product_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_TOKEN", raising=False)
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    api_key = make_token(datetime.now(timezone.utc) + timedelta(days=30))
    session = FakeGraphqlSession()
    client = DuroClient(
        api_key=api_key,
        api_key_path=tmp_path / "missing-api-key",
        token_path=tmp_path / "missing",
        cookies_path=tmp_path / "missing-cookies",
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
    assert call["url"] == "https://mfg-core-api.duro.app/graphql"
    assert call["headers"]["apiToken"] == api_key  # type: ignore[index]
    assert "authorization" not in call["headers"]  # type: ignore[operator]
    assert call["json"]["variables"] == {"first": 100, "after": None}  # type: ignore[index]


def test_api_key_takes_precedence_over_legacy_access_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    api_key = make_token(datetime.now(timezone.utc) + timedelta(days=30))
    access_token = make_token(datetime.now(timezone.utc) + timedelta(hours=1))
    monkeypatch.setenv("PRODUCTION_PLATFORM_DURO_TOKEN", access_token)
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    session = FakeGraphqlSession()
    client = DuroClient(
        api_key=api_key,
        api_key_path=tmp_path / "missing-api-key",
        token_path=tmp_path / "missing",
        cookies_path=tmp_path / "missing-cookies",
        session=session,  # type: ignore[arg-type]
    )

    client.search_products(DuroProductSearchRequest())

    assert session.calls[0]["headers"]["apiToken"] == api_key  # type: ignore[index]


def test_graphql_500_unauthorized_is_reported_as_authentication_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        "PRODUCTION_PLATFORM_DURO_API_KEY",
        make_token(datetime.now(timezone.utc) + timedelta(days=30)),
    )
    session = UnauthorizedSession()
    client = DuroClient(
        api_key_path=tmp_path / "missing-api-key",
        token_path=tmp_path / "missing",
        cookies_path=tmp_path / "missing-cookies",
        session=session,  # type: ignore[arg-type]
    )

    with pytest.raises(DuroAuthenticationError, match="未被接受"):
        client.search_products(DuroProductSearchRequest())


def test_api_key_file_is_used_for_graphql_product_bom(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_TOKEN", raising=False)
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    api_key = make_token(datetime.now(timezone.utc) + timedelta(days=30))
    api_key_path = tmp_path / "duro-api-key.txt"
    api_key_path.write_text(api_key, encoding="utf-8")
    session = FakeGraphqlSession()
    client = DuroClient(
        api_key_path=api_key_path,
        token_path=tmp_path / "missing",
        cookies_path=tmp_path / "missing-cookies",
        session=session,  # type: ignore[arg-type]
    )

    product = client.get_product("product-id")

    assert product["_id"] == "product-id"
    assert product["revision"] == "C1.2"
    child = product["children"][0]["component"]
    assert child["_id"] == "component-id"
    assert child["cpn"] == "123-00001"
    assert child["children"][0]["component"]["_id"] == "leaf-id"
    assert session.calls[0]["headers"]["apiToken"] == api_key  # type: ignore[index]


def test_api_key_is_preferred_over_remote_chrome(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_TOKEN", raising=False)
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    api_key = make_token(datetime.now(timezone.utc) + timedelta(days=30))
    browser_token = make_token(datetime.now(timezone.utc) + timedelta(hours=1))
    provider = FakeBrowserTokenProvider(browser_token)
    session = FakeGraphqlSession()
    client = DuroClient(
        api_key=api_key,
        api_key_path=tmp_path / "missing-api-key",
        token_path=tmp_path / "missing",
        cookies_path=tmp_path / "missing-cookies",
        browser_token_provider=provider,  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
    )

    response = client.search_products(DuroProductSearchRequest())

    assert response.count == 1
    assert provider.calls == []
    assert session.calls[0]["headers"]["apiToken"] == api_key  # type: ignore[index]


def test_update_api_key_persists_and_overrides_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    old_key = make_token(datetime.now(timezone.utc) + timedelta(days=1))
    new_expiry = datetime.now(timezone.utc) + timedelta(days=30)
    new_key = make_token(new_expiry)
    api_key_path = tmp_path / "credentials" / "duro-api-key.txt"
    monkeypatch.setenv("PRODUCTION_PLATFORM_DURO_API_KEY", old_key)
    client = DuroClient(api_key_path=api_key_path)

    status = client.update_api_key(f"Bearer {new_key}")

    assert status.token_valid is True
    assert status.token_expires_at is not None
    assert abs(status.token_expires_at.timestamp() - new_expiry.timestamp()) < 1
    assert api_key_path.read_text(encoding="utf-8").strip() == new_key
    assert api_key_path.stat().st_mode & 0o777 == 0o600
    assert client._api_token() == new_key
    assert DuroClient(api_key_path=api_key_path)._api_token() == new_key


def test_update_api_key_rejects_expired_value(tmp_path: Path) -> None:
    api_key_path = tmp_path / "duro-api-key.txt"
    client = DuroClient(api_key_path=api_key_path)

    with pytest.raises(DuroAuthenticationError, match="已过期"):
        client.update_api_key(
            make_token(datetime.now(timezone.utc) - timedelta(minutes=1))
        )

    assert not api_key_path.exists()
