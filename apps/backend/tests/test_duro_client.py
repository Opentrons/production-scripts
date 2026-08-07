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


class FakeRefreshResponse(FakeResponse):
    def __init__(self, token: str) -> None:
        self.token = token

    def json(self):
        return {
            "access_token": self.token,
            "expires_at_seconds": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }


class CookieRetrySession(FakeSession):
    def __init__(self, api_key: str, refreshed_token: str) -> None:
        super().__init__()
        self.api_key = api_key
        self.refreshed_token = refreshed_token

    def post(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        authorization = kwargs.get("headers", {}).get("authorization")
        if authorization == f"Bearer {self.api_key}":
            return FakeUnauthorizedResponse()
        return FakeResponse()

    def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return FakeRefreshResponse(self.refreshed_token)


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


def test_api_key_is_used_when_no_temporary_access_token_is_exported(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_TOKEN", raising=False)
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    api_key = make_token(datetime.now(timezone.utc) + timedelta(days=30))
    session = FakeSession()
    client = DuroClient(
        api_key=api_key,
        token_path=tmp_path / "missing",
        cookies_path=tmp_path / "missing-cookies",
        session=session,  # type: ignore[arg-type]
    )

    client.search_products(DuroProductSearchRequest())

    assert session.calls[0]["headers"]["authorization"] == f"Bearer {api_key}"  # type: ignore[index]


def test_explicit_access_token_overrides_api_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    api_key = make_token(datetime.now(timezone.utc) + timedelta(days=30))
    access_token = make_token(datetime.now(timezone.utc) + timedelta(hours=1))
    monkeypatch.setenv("PRODUCTION_PLATFORM_DURO_TOKEN", access_token)
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    session = FakeSession()
    client = DuroClient(
        api_key=api_key,
        token_path=tmp_path / "missing",
        cookies_path=tmp_path / "missing-cookies",
        session=session,  # type: ignore[arg-type]
    )

    client.search_products(DuroProductSearchRequest())

    assert session.calls[0]["headers"]["authorization"] == f"Bearer {access_token}"  # type: ignore[index]


def test_gateway_500_unauthorized_is_reported_as_authentication_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        "PRODUCTION_PLATFORM_DURO_TOKEN",
        make_token(datetime.now(timezone.utc) + timedelta(hours=1)),
    )
    session = UnauthorizedSession()
    client = DuroClient(
        token_path=tmp_path / "missing",
        cookies_path=tmp_path / "missing-cookies",
        session=session,  # type: ignore[arg-type]
    )

    with pytest.raises(DuroAuthenticationError, match="未被接受"):
        client.search_products(DuroProductSearchRequest())


def test_rejected_api_key_retries_with_access_token_refreshed_from_cookies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_TOKEN", raising=False)
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    api_key = make_token(datetime.now(timezone.utc) + timedelta(days=30))
    refreshed_token = make_token(datetime.now(timezone.utc) + timedelta(hours=1))
    cookies_path = tmp_path / "cookies.txt"
    cookies_path.write_text(
        json.dumps(
            [
                {
                    "name": "auth_session",
                    "value": "session-value",
                    "domain": "auth.duro.app",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                }
            ]
        ),
        encoding="utf-8",
    )
    session = CookieRetrySession(api_key, refreshed_token)
    client = DuroClient(
        api_key=api_key,
        token_path=tmp_path / "missing",
        cookies_path=cookies_path,
        session=session,  # type: ignore[arg-type]
    )

    response = client.search_products(DuroProductSearchRequest())
    second_response = client.search_products(DuroProductSearchRequest())

    assert response.count == 1
    assert second_response.count == 1
    assert [call["url"] for call in session.calls] == [
        "https://mfgapi.duro.app/v1/search/products",
        "https://auth.duro.app/api/v1/refresh_token",
        "https://mfgapi.duro.app/v1/search/products",
        "https://mfgapi.duro.app/v1/search/products",
    ]
    assert session.calls[2]["headers"]["authorization"] == f"Bearer {refreshed_token}"  # type: ignore[index]
    assert session.calls[3]["headers"]["authorization"] == f"Bearer {refreshed_token}"  # type: ignore[index]


def test_remote_chrome_access_token_is_preferred_over_api_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_TOKEN", raising=False)
    monkeypatch.delenv("PRODUCTION_PLATFORM_DURO_API_KEY", raising=False)
    api_key = make_token(datetime.now(timezone.utc) + timedelta(days=30))
    browser_token = make_token(datetime.now(timezone.utc) + timedelta(hours=1))
    provider = FakeBrowserTokenProvider(browser_token)
    session = FakeSession()
    client = DuroClient(
        api_key=api_key,
        token_path=tmp_path / "missing",
        cookies_path=tmp_path / "missing-cookies",
        browser_token_provider=provider,  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
    )

    response = client.search_products(DuroProductSearchRequest())

    assert response.count == 1
    assert provider.calls == [False]
    assert session.calls[0]["headers"]["authorization"] == f"Bearer {browser_token}"  # type: ignore[index]
