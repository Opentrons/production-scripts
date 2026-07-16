from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from duro.models import (
    DuroConnectionStatus,
    DuroProduct,
    DuroProductSearchRequest,
    DuroProductSearchResponse,
    utc_now,
)
from settings import DURO_BASE_URL, DURO_REQUEST_TIMEOUT_SECONDS, DURO_TOKEN_PATH


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
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token_path = Path(token_path)
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    def search_products(self, payload: DuroProductSearchRequest) -> DuroProductSearchResponse:
        token = self._access_token()
        response = self.session.post(
            f"{self.base_url}/v1/search/products",
            headers={
                "accept": "application/json",
                "authorization": f"Bearer {token}",
                "content-type": "application/json",
            },
            json=payload.model_dump(exclude_none=True),
            timeout=self.timeout_seconds,
        )
        data = self._response_data(response, "Duro 产品搜索")
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
        token = self._raw_token()
        expires_at = self._token_expiry(token) if token else None
        now = datetime.now(timezone.utc)
        return DuroConnectionStatus(
            configured=bool(token),
            token_valid=bool(token) and (expires_at is None or expires_at > now),
            token_expires_at=expires_at,
            base_url=self.base_url,
        )

    def _access_token(self) -> str:
        token = self._raw_token()
        if not token:
            raise DuroAuthenticationError(
                "未配置 Duro token，请设置 PRODUCTIONS_VERSIONS_DURO_TOKEN "
                f"或写入 {self.token_path}"
            )
        expires_at = self._token_expiry(token)
        if expires_at is not None and expires_at <= datetime.now(timezone.utc):
            raise DuroAuthenticationError(f"Duro token 已过期: {expires_at.isoformat()}")
        return token

    def _raw_token(self) -> str:
        value = os.getenv("PRODUCTIONS_VERSIONS_DURO_TOKEN", "").strip()
        if not value and self.token_path.exists():
            value = self.token_path.read_text(encoding="utf-8").strip()
        if value.lower().startswith("bearer "):
            value = value[7:].strip()
        return value

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
        token = self._access_token()
        encoded_id = quote(entity_id.strip(), safe="")
        if not encoded_id:
            raise DuroApiError(f"{operation}缺少 ID")
        response = self.session.get(
            f"{self.base_url}/v1/{resource}/{encoded_id}",
            headers={
                "accept": "application/json",
                "authorization": f"Bearer {token}",
            },
            params={"include": "children", "lean": "true"},
            timeout=self.timeout_seconds,
        )
        data = self._response_data(response, operation)
        if not isinstance(data, dict):
            raise DuroApiError(f"{operation}接口缺少 data 对象")
        return data

    def _response_data(self, response: requests.Response, operation: str) -> Any:
        if response.status_code in {401, 403}:
            raise DuroAuthenticationError("Duro token 已失效或没有产品读取权限")
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DuroApiError(f"{operation}请求失败: HTTP {response.status_code}") from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise DuroApiError(f"{operation}接口返回了无效 JSON") from exc
        if not isinstance(body, dict) or body.get("success") is not True:
            raise DuroApiError(self._response_error_message(body, operation))
        return body.get("data")

    def _response_error_message(self, body: Any, operation: str = "Duro 产品") -> str:
        if isinstance(body, dict):
            for key in ("message", "error", "detail"):
                value = body.get(key)
                if value:
                    return f"{operation}接口失败: {value}"
        return f"{operation}接口返回失败状态"
