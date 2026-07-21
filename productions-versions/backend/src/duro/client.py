from __future__ import annotations

import base64
import json
import os
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from duro.browser_auth import DuroRemoteChromeError, DuroRemoteChromeTokenProvider
from duro.cookies import DuroCookieError, load_cookie_jar, save_cookie_jar
from duro.models import (
    DuroConnectionStatus,
    DuroProduct,
    DuroProductSearchRequest,
    DuroProductSearchResponse,
    utc_now,
)
from settings import (
    DURO_AUTH_URL,
    DURO_BASE_URL,
    DURO_COOKIES_PATH,
    DURO_REQUEST_TIMEOUT_SECONDS,
    DURO_TOKEN_PATH,
    DURO_TOKEN_REFRESH_MARGIN_SECONDS,
)


class DuroApiError(RuntimeError):
    pass


class DuroAuthenticationError(DuroApiError):
    pass


class DuroClient:
    def __init__(
        self,
        base_url: str = DURO_BASE_URL,
        token_path: Path = DURO_TOKEN_PATH,
        timeout_seconds: int = DURO_REQUEST_TIMEOUT_SECONDS,
        api_key: str | None = None,
        cookies_path: Path = DURO_COOKIES_PATH,
        auth_url: str = DURO_AUTH_URL,
        refresh_margin_seconds: int = DURO_TOKEN_REFRESH_MARGIN_SECONDS,
        browser_token_provider: DuroRemoteChromeTokenProvider | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token_path = Path(token_path)
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key.strip() if api_key else ""
        self.cookies_path = Path(cookies_path)
        self.auth_url = auth_url.rstrip("/")
        self.refresh_margin_seconds = max(0, refresh_margin_seconds)
        self.browser_token_provider = browser_token_provider
        self.session = session or requests.Session()
        self._refresh_lock = threading.Lock()
        self._refreshed_access_token = ""
        self._refreshed_token_expires_at: datetime | None = None

    def search_products(self, payload: DuroProductSearchRequest) -> DuroProductSearchResponse:
        data = self._authenticated_data(
            lambda token: self.session.post(
                f"{self.base_url}/v1/search/products",
                headers={
                    "accept": "application/json",
                    "authorization": f"Bearer {token}",
                    "content-type": "application/json",
                },
                json=payload.model_dump(exclude_none=True),
                timeout=self.timeout_seconds,
            ),
            "Duro 产品搜索",
        )
        if not isinstance(data, dict):
            raise DuroApiError("Duro 产品接口缺少 data 对象")
        results = data.get("results", [])
        if not isinstance(results, list):
            raise DuroApiError("Duro 产品接口 data.results 格式错误")
        products = [DuroProduct.model_validate(item) for item in results]
        return DuroProductSearchResponse(
            success=True,
            count=int(data.get("count", len(products))),
            products=products,
            request=payload,
            fetched_at=utc_now(),
        )

    def get_product(self, product_id: str) -> dict[str, Any]:
        return self._get_entity("products", product_id, "Duro 产品 BOM")

    def get_component(self, component_id: str) -> dict[str, Any]:
        return self._get_entity("components", component_id, "Duro 组件 BOM")

    def connection_status(self) -> DuroConnectionStatus:
        token = self._raw_credential()
        expires_at = self._token_expiry(token) if token else None
        now = datetime.now(timezone.utc)
        remote_chrome_configured = bool(
            self.browser_token_provider
            and getattr(self.browser_token_provider, "configured", True)
        )
        return DuroConnectionStatus(
            configured=bool(token) or remote_chrome_configured,
            token_valid=bool(token) and (expires_at is None or expires_at > now),
            token_expires_at=expires_at,
            base_url=self.base_url,
            remote_chrome_configured=remote_chrome_configured,
        )

    def _access_token(self) -> str:
        explicit_token = os.getenv("PRODUCTIONS_VERSIONS_DURO_TOKEN", "").strip()
        if explicit_token:
            token = self._strip_bearer_prefix(explicit_token)
            expires_at = self._token_expiry(token)
            if expires_at is not None and expires_at <= datetime.now(timezone.utc):
                # The provider refreshes automatically when its cached token is
                # missing or near expiry. Avoid forcing a new browser refresh on
                # every request while the explicit fallback token stays expired.
                browser_token = self._browser_access_token()
                if browser_token:
                    return browser_token
                refreshed = self._refresh_access_token_from_cookies(force=True)
                if refreshed:
                    return refreshed
                raise DuroAuthenticationError(f"Duro 凭据已过期: {expires_at.isoformat()}")
        elif browser_token := self._browser_access_token():
            return browser_token
        elif self._cached_refreshed_token_is_valid():
            return self._refreshed_access_token
        elif self._refreshed_access_token:
            refreshed = self._refresh_access_token_from_cookies(force=True)
            if refreshed:
                return refreshed
            token = self._raw_credential()
        else:
            token = self._raw_credential()
        if not token:
            token = self._refresh_access_token_from_cookies()
        if not token:
            raise DuroAuthenticationError(
                "未配置可用的 Duro 凭据，请设置 DURO_API_KEY、PRODUCTIONS_VERSIONS_DURO_TOKEN、"
                f"写入 {self.token_path}，或导出 auth.duro.app 登录 Cookie 到 {self.cookies_path}"
            )
        expires_at = self._token_expiry(token)
        if expires_at is not None and expires_at <= datetime.now(timezone.utc):
            refreshed = self._refresh_access_token_from_cookies(force=True)
            if not refreshed:
                raise DuroAuthenticationError(f"Duro 凭据已过期: {expires_at.isoformat()}")
            token = refreshed
        return token

    def _raw_credential(self) -> str:
        # An explicitly exported access token is useful for temporary overrides;
        # otherwise prefer the long-lived API key loaded from backend/.env.
        value = os.getenv("PRODUCTIONS_VERSIONS_DURO_TOKEN", "").strip()
        if not value:
            value = os.getenv("DURO_API_KEY", self.api_key).strip()
        if not value and self.token_path.exists():
            value = self.token_path.read_text(encoding="utf-8").strip()
        return self._strip_bearer_prefix(value)

    @staticmethod
    def _strip_bearer_prefix(value: str) -> str:
        normalized = value.strip()
        if normalized.lower().startswith("bearer "):
            normalized = normalized[7:].strip()
        return normalized

    def _raw_token(self) -> str:
        """Backward-compatible alias for callers that used the old helper."""

        return self._raw_credential()

    def _token_expiry(self, token: str) -> datetime | None:
        try:
            payload_segment = token.split(".")[1]
            padding = "=" * (-len(payload_segment) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_segment + padding))
            expires_at = payload.get("exp")
            return datetime.fromtimestamp(int(expires_at), tz=timezone.utc) if expires_at else None
        except (IndexError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def _get_entity(self, resource: str, entity_id: str, operation: str) -> dict[str, Any]:
        encoded_id = quote(entity_id.strip(), safe="")
        if not encoded_id:
            raise DuroApiError(f"{operation}缺少 ID")
        data = self._authenticated_data(
            lambda token: self.session.get(
                f"{self.base_url}/v1/{resource}/{encoded_id}",
                headers={
                    "accept": "application/json",
                    "authorization": f"Bearer {token}",
                },
                params={"include": "children", "lean": "true"},
                timeout=self.timeout_seconds,
            ),
            operation,
        )
        if not isinstance(data, dict):
            raise DuroApiError(f"{operation}接口缺少 data 对象")
        return data

    def _authenticated_data(
        self,
        send: Callable[[str], requests.Response],
        operation: str,
    ) -> Any:
        token = self._access_token()
        try:
            return self._response_data(send(token), operation)
        except DuroAuthenticationError as original_error:
            browser_token = self._browser_access_token(force=True)
            if browser_token and browser_token != token:
                try:
                    return self._response_data(send(browser_token), operation)
                except DuroAuthenticationError:
                    token = browser_token
            try:
                refreshed = self._refresh_access_token_from_cookies(force=True)
            except DuroApiError:
                raise original_error
            if not refreshed or refreshed == token:
                raise
            return self._response_data(send(refreshed), operation)

    def _browser_access_token(self, force: bool = False) -> str:
        if self.browser_token_provider is None:
            return ""
        try:
            return self.browser_token_provider.get_access_token(force=force)
        except DuroRemoteChromeError:
            return ""

    def _refresh_access_token_from_cookies(self, force: bool = False) -> str:
        with self._refresh_lock:
            if not force and self._cached_refreshed_token_is_valid():
                return self._refreshed_access_token
            try:
                cookies = load_cookie_jar(self.cookies_path)
            except DuroCookieError as exc:
                raise DuroAuthenticationError(str(exc)) from exc
            if not cookies:
                return ""

            try:
                response = self.session.get(
                    f"{self.auth_url}/api/v1/refresh_token",
                    headers={
                        "accept": "application/json",
                        "origin": "https://mfg.duro.app",
                        "referer": "https://mfg.duro.app/",
                    },
                    cookies=cookies,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                raise DuroApiError("Duro 登录会话刷新请求失败") from exc
            if response.status_code in {401, 403}:
                return ""
            try:
                response.raise_for_status()
            except requests.RequestException as exc:
                raise DuroApiError(f"Duro 登录会话刷新失败: HTTP {response.status_code}") from exc
            try:
                body = response.json()
            except ValueError as exc:
                raise DuroApiError("Duro 登录会话刷新接口返回了无效 JSON") from exc
            if not isinstance(body, dict):
                raise DuroApiError("Duro 登录会话刷新接口返回格式错误")

            response_cookies = getattr(response, "cookies", None)
            if response_cookies:
                self._merge_rotated_cookies(cookies, response_cookies)
                save_cookie_jar(self.cookies_path, cookies)

            token = str(body.get("access_token") or "").strip()
            if not token:
                return ""
            self._refreshed_access_token = token
            self._refreshed_token_expires_at = self._refresh_response_expiry(body, token)
            return token

    @staticmethod
    def _merge_rotated_cookies(
        current: requests.cookies.RequestsCookieJar,
        updated: requests.cookies.RequestsCookieJar,
    ) -> None:
        for replacement in updated:
            if replacement.name == "refresh_token":
                for existing in list(current):
                    if existing.name == "refresh_token":
                        try:
                            current.clear(existing.domain, existing.path, existing.name)
                        except KeyError:
                            pass
            current.set_cookie(replacement)

    def _cached_refreshed_token_is_valid(self) -> bool:
        if not self._refreshed_access_token:
            return False
        expires_at = self._refreshed_token_expires_at or self._token_expiry(self._refreshed_access_token)
        if expires_at is None:
            return True
        margin = timedelta(seconds=self.refresh_margin_seconds)
        return expires_at > datetime.now(timezone.utc) + margin

    def _refresh_response_expiry(self, body: dict[str, Any], token: str) -> datetime | None:
        value = body.get("expires_at_seconds")
        try:
            seconds = int(value)
        except (TypeError, ValueError):
            return self._token_expiry(token)
        now = datetime.now(timezone.utc)
        if seconds > int(now.timestamp()):
            return datetime.fromtimestamp(seconds, timezone.utc)
        return now + timedelta(seconds=max(0, seconds))

    def _response_data(self, response: requests.Response, operation: str) -> Any:
        if response.status_code in {401, 403}:
            raise DuroAuthenticationError("Duro 凭据已失效或没有产品读取权限")

        # The Duro gateway currently serializes an authentication failure as
        # HTTP 500 with {success: false, errors: [{message: "Unauthorized"}]}.
        # Inspect the JSON body before handling the generic HTTP error so the
        # frontend receives a useful 401 instead of an opaque 502.
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict) and self._is_unauthorized(body):
            raise DuroAuthenticationError("Duro 凭据未被接受或没有产品读取权限")
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DuroApiError(f"{operation}请求失败: HTTP {response.status_code}") from exc

        if body is None:
            try:
                body = response.json()
            except ValueError as exc:
                raise DuroApiError(f"{operation}接口返回了无效 JSON") from exc
        if not isinstance(body, dict) or body.get("success") is not True:
            raise DuroApiError(self._response_error_message(body, operation))
        return body.get("data")

    @staticmethod
    def _is_unauthorized(body: dict[str, Any]) -> bool:
        values: list[str] = []
        for key in ("message", "error", "detail"):
            value = body.get(key)
            if isinstance(value, str):
                values.append(value)
        errors = body.get("errors")
        if isinstance(errors, list):
            for item in errors:
                if isinstance(item, dict) and isinstance(item.get("message"), str):
                    values.append(item["message"])
                elif isinstance(item, str):
                    values.append(item)
        return any("unauthorized" in value.lower() or "unauthenticated" in value.lower() for value in values)

    def _response_error_message(self, body: Any, operation: str = "Duro 产品") -> str:
        if isinstance(body, dict):
            errors = body.get("errors")
            if isinstance(errors, list):
                for item in errors:
                    if isinstance(item, dict) and item.get("message"):
                        return f"{operation}接口失败: {item['message']}"
                    if isinstance(item, str) and item:
                        return f"{operation}接口失败: {item}"
            for key in ("message", "error", "detail"):
                value = body.get(key)
                if value:
                    return f"{operation}接口失败: {value}"
        return f"{operation}接口返回失败状态"
