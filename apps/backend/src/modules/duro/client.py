from __future__ import annotations

import base64
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from modules.duro.models import (
    DuroConnectionStatus,
    DuroProduct,
    DuroProductSearchRequest,
    DuroProductSearchResponse,
    utc_now,
)
from core.config import (
    DURO_API_KEY_PATH,
    DURO_GRAPHQL_URL,
    DURO_REQUEST_TIMEOUT_SECONDS,
)


class DuroApiError(RuntimeError):
    pass


class DuroAuthenticationError(DuroApiError):
    pass


class DuroClient:
    _APP_URL = "https://mfg.duro.app"

    _PRODUCTS_QUERY = """
        query ProductionPlatformProducts($first: Int, $after: String) {
          products(libraryType: GENERAL) {
            connection(first: $first, after: $after) {
              totalCount
              pageInfo { hasNextPage endCursor }
              edges {
                node {
                  id name alias description revisionValue status lastModified
                  cpn { displayValue variant }
                  images { id name mime size src key archived }
                }
              }
            }
          }
        }
    """
    _PRODUCT_BY_ID_QUERY = """
        query ProductionPlatformProduct($ids: [ID]) {
          productsByIds(ids: $ids) {
            id name alias description revisionValue status lastModified
            cpn { displayValue variant }
            children {
              quantity itemNumber notes refDes waste
              component {
                id name alias revisionValue status unitOfMeasure
                cpn { displayValue variant }
                children { component { id } }
              }
              assemblyRevision { id revisionValue }
            }
          }
        }
    """
    _COMPONENT_BY_ID_QUERY = """
        query ProductionPlatformComponent($ids: [ID]) {
          componentsByIds(ids: $ids) {
            id name alias description revisionValue status lastModified unitOfMeasure
            cpn { displayValue variant }
            children {
              quantity itemNumber notes refDes waste
              component {
                id name alias revisionValue status unitOfMeasure
                cpn { displayValue variant }
                children { component { id } }
              }
              assemblyRevision { id revisionValue }
            }
          }
        }
    """

    def __init__(
        self,
        graphql_url: str = DURO_GRAPHQL_URL,
        api_key_path: Path = DURO_API_KEY_PATH,
        timeout_seconds: int = DURO_REQUEST_TIMEOUT_SECONDS,
        api_key: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.graphql_url = graphql_url.rstrip("/")
        # Keep the user-facing Duro URL separate from the GraphQL endpoint.
        self.app_url = self._APP_URL
        self.api_key_path = Path(api_key_path)
        self.timeout_seconds = timeout_seconds
        self.api_key = self._normalize_api_key(api_key or "")
        self.session = session or requests.Session()

    def search_products(self, payload: DuroProductSearchRequest) -> DuroProductSearchResponse:
        return self._search_products_graphql(payload, self._required_api_key())

    def get_product(self, product_id: str) -> dict[str, Any]:
        return self._get_graphql_entity(
            product_id,
            query=self._PRODUCT_BY_ID_QUERY,
            response_key="productsByIds",
            operation="Duro 产品 BOM",
            api_key=self._required_api_key(),
        )

    def get_component(self, component_id: str) -> dict[str, Any]:
        return self._get_graphql_entity(
            component_id,
            query=self._COMPONENT_BY_ID_QUERY,
            response_key="componentsByIds",
            operation="Duro 组件 BOM",
            api_key=self._required_api_key(),
        )

    def connection_status(self) -> DuroConnectionStatus:
        api_key = self._api_key()
        expires_at = self._api_key_expiry(api_key) if api_key else None
        return DuroConnectionStatus(
            configured=bool(api_key),
            api_key_valid=bool(api_key)
            and (expires_at is None or expires_at > datetime.now(timezone.utc)),
            api_key_expires_at=expires_at,
            base_url=self.graphql_url,
        )

    def update_api_key(self, api_key: str) -> DuroConnectionStatus:
        value = self._normalize_api_key(api_key)
        if not value:
            raise DuroAuthenticationError("Duro API Key 不能为空")
        expires_at = self._api_key_expiry(value)
        if expires_at is not None and expires_at <= datetime.now(timezone.utc):
            raise DuroAuthenticationError(f"Duro API Key 已过期: {expires_at.isoformat()}")

        self.api_key_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.api_key_path.parent,
                prefix=f".{self.api_key_path.name}.",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                os.chmod(temporary_path, 0o600)
                handle.write(f"{value}\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.api_key_path)
            os.chmod(self.api_key_path, 0o600)
        except OSError as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise DuroAuthenticationError(
                f"无法写入 Duro API Key 文件: {self.api_key_path}"
            ) from exc

        self.api_key = value
        return self.connection_status()

    def _api_key(self) -> str:
        value = self.api_key
        if not value and self.api_key_path.exists():
            try:
                value = self.api_key_path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise DuroAuthenticationError(
                    f"无法读取 Duro API Key 文件: {self.api_key_path}"
                ) from exc
        if not value:
            value = os.getenv("PRODUCTION_PLATFORM_DURO_API_KEY", "").strip()
        return self._normalize_api_key(value)

    def _required_api_key(self) -> str:
        value = self._api_key()
        if not value:
            raise DuroAuthenticationError(
                f"未配置 Duro API Key，请写入 {self.api_key_path} 或设置 "
                "PRODUCTION_PLATFORM_DURO_API_KEY"
            )
        expires_at = self._api_key_expiry(value)
        if expires_at is not None and expires_at <= datetime.now(timezone.utc):
            raise DuroAuthenticationError(f"Duro API Key 已过期: {expires_at.isoformat()}")
        return value

    def _search_products_graphql(
        self,
        payload: DuroProductSearchRequest,
        api_key: str,
    ) -> DuroProductSearchResponse:
        products: list[dict[str, Any]] = []
        after: str | None = None
        total_count = 0
        while True:
            data = self._graphql_data(
                self._PRODUCTS_QUERY,
                {"first": 100, "after": after},
                "Duro 产品搜索",
                api_key,
            )
            product_data = data.get("products")
            connection = product_data.get("connection") if isinstance(product_data, dict) else None
            if not isinstance(connection, dict):
                raise DuroApiError("Duro 产品 GraphQL 接口缺少 connection 对象")
            total_count = int(connection.get("totalCount") or 0)
            edges = connection.get("edges")
            if not isinstance(edges, list):
                raise DuroApiError("Duro 产品 GraphQL 接口 edges 格式错误")
            for edge in edges:
                node = edge.get("node") if isinstance(edge, dict) else None
                if isinstance(node, dict):
                    products.append(self._normalize_graphql_entity(node))

            page_info = connection.get("pageInfo")
            if not isinstance(page_info, dict) or not page_info.get("hasNextPage"):
                break
            next_cursor = page_info.get("endCursor")
            if not isinstance(next_cursor, str) or not next_cursor or next_cursor == after:
                raise DuroApiError("Duro 产品 GraphQL 分页游标无效")
            after = next_cursor

        sort_key = self._graphql_sort_key(payload.sort)
        products.sort(
            key=lambda item: (
                item.get(sort_key) is not None,
                str(item.get(sort_key) or "").casefold(),
            ),
            reverse=payload.reverse,
        )
        if payload.limit:
            start = (payload.page - 1) * payload.limit
            products = products[start : start + payload.limit]
        validated = [DuroProduct.model_validate(item) for item in products]
        return DuroProductSearchResponse(
            success=True,
            count=total_count or len(validated),
            products=validated,
            request=payload,
            fetched_at=utc_now(),
        )

    def _get_graphql_entity(
        self,
        entity_id: str,
        *,
        query: str,
        response_key: str,
        operation: str,
        api_key: str,
    ) -> dict[str, Any]:
        normalized_id = entity_id.strip()
        if not normalized_id:
            raise DuroApiError(f"{operation}缺少 ID")
        data = self._graphql_data(query, {"ids": [normalized_id]}, operation, api_key)
        entities = data.get(response_key)
        if not isinstance(entities, list):
            raise DuroApiError(f"{operation} GraphQL 接口缺少 {response_key} 数组")
        if not entities or not isinstance(entities[0], dict):
            raise DuroApiError(f"{operation}未找到 ID 为 {normalized_id} 的数据")
        return self._normalize_graphql_entity(entities[0])

    def _graphql_data(
        self,
        query: str,
        variables: dict[str, Any],
        operation: str,
        api_key: str,
    ) -> dict[str, Any]:
        try:
            response = self.session.post(
                self.graphql_url,
                headers={
                    "accept": "application/json",
                    "apiToken": api_key,
                    "content-type": "application/json",
                },
                json={"query": query, "variables": variables},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise DuroApiError(f"{operation} GraphQL 请求失败") from exc
        if response.status_code in {401, 403}:
            raise DuroAuthenticationError("Duro API Key 已失效或没有产品读取权限")
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict) and self._is_unauthorized(body):
            raise DuroAuthenticationError("Duro API Key 未被接受或没有产品读取权限")
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DuroApiError(f"{operation} GraphQL 请求失败: HTTP {response.status_code}") from exc
        if body is None:
            try:
                body = response.json()
            except ValueError as exc:
                raise DuroApiError(f"{operation} GraphQL 接口返回了无效 JSON") from exc
        if not isinstance(body, dict):
            raise DuroApiError(f"{operation} GraphQL 接口返回格式错误")
        if body.get("errors"):
            raise DuroApiError(self._response_error_message(body, operation))
        data = body.get("data")
        if not isinstance(data, dict):
            raise DuroApiError(f"{operation} GraphQL 接口缺少 data 对象")
        return data

    @classmethod
    def _normalize_graphql_entity(cls, entity: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(entity)
        normalized["_id"] = str(entity.get("id") or entity.get("_id") or "")
        normalized["revision"] = entity.get("revisionValue") or entity.get("revision")
        cpn = entity.get("cpn")
        if isinstance(cpn, dict):
            normalized["cpn"] = cpn.get("displayValue")
            normalized["cpnVariant"] = cpn.get("variant")
        images = entity.get("images")
        if isinstance(images, list):
            normalized["images"] = [
                {**image, "_id": image.get("id")}
                for image in images
                if isinstance(image, dict)
            ]
        children = entity.get("children")
        if isinstance(children, list):
            normalized_children: list[Any] = []
            for relationship in children:
                if not isinstance(relationship, dict):
                    normalized_children.append(relationship)
                    continue
                normalized_relationship = dict(relationship)
                for key in ("component", "assemblyRevision"):
                    child = relationship.get(key)
                    if isinstance(child, dict):
                        normalized_relationship[key] = cls._normalize_graphql_entity(child)
                normalized_children.append(normalized_relationship)
            normalized["children"] = normalized_children
        return normalized

    @staticmethod
    def _graphql_sort_key(value: str) -> str:
        return {
            "_id": "_id",
            "id": "_id",
            "revisionValue": "revision",
        }.get(value, value)

    @staticmethod
    def _normalize_api_key(value: str) -> str:
        normalized = value.strip()
        if normalized.lower().startswith("bearer "):
            normalized = normalized[7:].strip()
        return normalized

    @staticmethod
    def _api_key_expiry(api_key: str) -> datetime | None:
        try:
            payload_segment = api_key.split(".")[1]
            padding = "=" * (-len(payload_segment) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_segment + padding))
            expires_at = payload.get("exp")
            return datetime.fromtimestamp(int(expires_at), tz=timezone.utc) if expires_at else None
        except (IndexError, ValueError, TypeError, json.JSONDecodeError):
            return None

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
        return any(
            "unauthorized" in value.lower() or "unauthenticated" in value.lower()
            for value in values
        )

    @staticmethod
    def _response_error_message(body: Any, operation: str = "Duro 产品") -> str:
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
