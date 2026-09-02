from __future__ import annotations

from threading import RLock
from typing import Any

import httpx


class BridgefloodsError(RuntimeError):
    pass


def unwrap_response(payload: Any) -> Any:
    if isinstance(payload, dict) and "code" in payload:
        if payload.get("code") == 0:
            return payload.get("data")
        raise BridgefloodsError("Bridgefloods API rejected the request")
    return payload


def extract_paginated_items(payload: Any) -> tuple[list[dict[str, Any]], int | None]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], None
    if not isinstance(payload, dict):
        return [], None
    raw_items = payload.get("items") or payload.get("data") or payload.get("records") or []
    if not isinstance(raw_items, list):
        raw_items = []
    raw_pages = payload.get("pages") or payload.get("total_pages")
    try:
        pages = int(raw_pages) if raw_pages is not None else None
    except (TypeError, ValueError):
        pages = None
    return [item for item in raw_items if isinstance(item, dict)], pages


class BridgefloodsClient:
    def __init__(
        self,
        *,
        base_url: str,
        access_token: str = "",
        refresh_token: str = "",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.timeout_seconds = timeout_seconds
        self._lock = RLock()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Accept-Language": "zh",
            "Content-Type": "application/json",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        allow_refresh: bool = True,
    ) -> Any:
        normalized_path = path if path.startswith("/") else f"/{path}"
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{normalized_path}",
                headers=self._headers(),
                json=payload,
                params={key: value for key, value in (params or {}).items() if value is not None},
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise BridgefloodsError("Bridgefloods API request timed out") from exc
        except httpx.HTTPError as exc:
            raise BridgefloodsError("Bridgefloods API is unreachable") from exc

        if response.status_code == 401 and allow_refresh and self.refresh_token and normalized_path != "/auth/refresh":
            with self._lock:
                self._refresh_access_token()
            return self._request(
                method,
                normalized_path,
                payload=payload,
                params=params,
                allow_refresh=False,
            )
        if response.status_code >= 400:
            raise BridgefloodsError(f"Bridgefloods API returned HTTP {response.status_code}")
        if not response.content:
            return None
        try:
            return unwrap_response(response.json())
        except ValueError as exc:
            raise BridgefloodsError("Bridgefloods API returned invalid JSON") from exc

    def _refresh_access_token(self) -> None:
        payload = self._request(
            "POST",
            "/auth/refresh",
            payload={"refresh_token": self.refresh_token},
            allow_refresh=False,
        )
        if not isinstance(payload, dict) or not payload.get("access_token"):
            raise BridgefloodsError("Bridgefloods authentication refresh failed")
        self.access_token = str(payload["access_token"])
        if payload.get("refresh_token"):
            self.refresh_token = str(payload["refresh_token"])

    def list_keys(self, page_size: int = 100) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            payload = self._request(
                "GET",
                "/keys",
                params={"page": page, "page_size": page_size},
            )
            page_items, total_pages = extract_paginated_items(payload)
            items.extend(page_items)
            if total_pages is not None:
                if page >= total_pages:
                    break
            elif len(page_items) < page_size:
                break
            page += 1
        return items

    def get_profile(self) -> dict[str, Any]:
        payload = self._request("GET", "/user/profile")
        if not isinstance(payload, dict):
            raise BridgefloodsError("Bridgefloods profile response is invalid")
        return payload

    def get_usage_stats(
        self,
        *,
        start_date: str,
        end_date: str,
        key_id: str,
    ) -> dict[str, Any]:
        payload = self._request(
            "GET",
            "/usage/stats",
            params={
                "start_date": start_date,
                "end_date": end_date,
                "api_key_id": key_id,
            },
        )
        if not isinstance(payload, dict):
            raise BridgefloodsError("Bridgefloods usage response is invalid")
        return payload

    def update_key_quota(
        self,
        key_id: str,
        quota: float,
        *,
        status: str | None = None,
    ) -> Any:
        payload: dict[str, Any] = {"quota": round(quota, 4)}
        if status:
            payload["status"] = status
        return self._request("PUT", f"/keys/{key_id}", payload=payload)
