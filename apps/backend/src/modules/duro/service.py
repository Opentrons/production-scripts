from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from modules.duro.client import DuroApiError, DuroClient
from modules.duro.models import (
    DuroBomNode,
    DuroComponentChildrenResponse,
    DuroProductBomResponse,
    DuroProductSearchRequest,
    DuroProductSearchResponse,
)
from core.config import DURO_PRODUCT_CACHE_SECONDS


class DuroService:
    def __init__(
        self,
        client: DuroClient,
        cache_seconds: int = DURO_PRODUCT_CACHE_SECONDS,
        cache_path: Path | None = None,
    ) -> None:
        self.client = client
        self.cache_seconds = max(0, cache_seconds)
        self.cache_path = cache_path
        self._lock = threading.RLock()
        self._search_cache: dict[str, tuple[float, DuroProductSearchResponse]] = {}
        self._product_bom_cache: dict[str, tuple[float, DuroProductBomResponse]] = {}
        self._component_cache: dict[str, tuple[float, DuroComponentChildrenResponse]] = {}
        if self.cache_path is not None:
            self._initialize_disk_cache()

    def search_products(
        self,
        payload: DuroProductSearchRequest,
        refresh: bool = False,
    ) -> DuroProductSearchResponse:
        cache_key = json.dumps(payload.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        with self._lock:
            cached = self._search_cache.get(cache_key)
            if not refresh and cached:
                return cached[1].model_copy(update={"cached": True})
        if not refresh:
            disk_cached = self._get_disk_cached(
                f"products:rest-v1:{cache_key}", DuroProductSearchResponse
            )
            if disk_cached is not None:
                with self._lock:
                    self._search_cache[cache_key] = (time.monotonic(), disk_cached)
                return disk_cached.model_copy(update={"cached": True})

        response = self.client.search_products(payload)
        with self._lock:
            self._search_cache[cache_key] = (time.monotonic(), response)
        self._set_disk_cached(f"products:rest-v1:{cache_key}", response)
        return response

    def list_products(self, refresh: bool = False) -> DuroProductSearchResponse:
        return self.search_products(DuroProductSearchRequest(), refresh=refresh)

    def get_product_bom(self, product_id: str, refresh: bool = False) -> DuroProductBomResponse:
        normalized_id = product_id.strip()
        disk_key = f"product-bom:rest-v3:{normalized_id}"
        cached = self._get_cached(self._product_bom_cache, normalized_id, refresh)
        if cached is not None:
            return cached.model_copy(update={"cached": True})
        if not refresh:
            disk_cached = self._get_disk_cached(disk_key, DuroProductBomResponse)
            if disk_cached is not None:
                self._set_cached(self._product_bom_cache, normalized_id, disk_cached)
                return disk_cached.model_copy(update={"cached": True})

        product = self.client.get_product(normalized_id)
        product.setdefault("_id", normalized_id)
        children = self._map_children(product.get("children"), normalized_id)
        material_total_count = self._count_leaf_materials(
            children,
            refresh=refresh,
            ancestors=frozenset({normalized_id}),
        )
        root = self._map_entity(
            product,
            node_type="product",
            children=children,
            has_children=bool(children),
            child_count=len(children),
        )
        response = DuroProductBomResponse(
            product_id=normalized_id,
            root=root,
            direct_child_count=len(children),
            material_total_count=material_total_count,
            source_url=self._product_source_url(normalized_id),
        )
        self._set_cached(self._product_bom_cache, normalized_id, response)
        self._set_disk_cached(disk_key, response)
        return response

    def _product_source_url(self, product_id: str) -> str:
        """Build a user-facing Duro product URL across client implementations."""
        base_url = getattr(self.client, "app_url", None) or getattr(
            self.client, "base_url", None
        )
        if not base_url:
            graphql_url = str(getattr(self.client, "graphql_url", "")).rstrip("/")
            base_url = graphql_url.removesuffix("/graphql")
        return f"{str(base_url).rstrip('/')}/product/view/{product_id}"

    def get_component_children(
        self,
        component_id: str,
        refresh: bool = False,
    ) -> DuroComponentChildrenResponse:
        normalized_id = component_id.strip()
        disk_key = f"component:rest-v2:{normalized_id}"
        cached = self._get_cached(self._component_cache, normalized_id, refresh)
        if cached is not None:
            return cached.model_copy(update={"cached": True})
        if not refresh:
            disk_cached = self._get_disk_cached(disk_key, DuroComponentChildrenResponse)
            if disk_cached is not None:
                self._set_cached(self._component_cache, normalized_id, disk_cached)
                return disk_cached.model_copy(update={"cached": True})

        component = self.client.get_component(normalized_id)
        children = self._map_children(component.get("children"), normalized_id)
        response = DuroComponentChildrenResponse(
            component_id=normalized_id,
            children=children,
            count=len(children),
        )
        self._set_cached(self._component_cache, normalized_id, response)
        self._set_disk_cached(disk_key, response)
        return response

    def _count_leaf_materials(
        self,
        nodes: list[DuroBomNode],
        refresh: bool,
        ancestors: frozenset[str],
    ) -> int:
        # Count each BOM tree leaf once; the leaf relationship quantity is ignored.
        total = 0
        for node in nodes:
            if node.has_children:
                if node.id in ancestors:
                    continue
                children = self.get_component_children(node.id, refresh=refresh).children
                total += self._count_leaf_materials(
                    children,
                    refresh=refresh,
                    ancestors=ancestors | {node.id},
                )
                continue
            total += 1
        return total

    def search_product_bom(
        self,
        product_id: str,
        query: str,
        max_nodes: int = 5000,
    ) -> DuroProductBomResponse:
        keyword = query.strip().casefold()
        if not keyword:
            return self.get_product_bom(product_id)

        response = self.get_product_bom(product_id)
        visited_nodes = 0

        def matches(node: DuroBomNode) -> bool:
            return any(
                keyword in str(value).casefold()
                for value in (node.cpn, node.name, node.alias, node.id)
                if value
            )

        def expand_and_filter(node: DuroBomNode, ancestors: frozenset[str]) -> DuroBomNode | None:
            nonlocal visited_nodes
            visited_nodes += 1
            if visited_nodes > max_nodes:
                raise DuroApiError(f"Duro BOM 节点超过 {max_nodes}，已停止搜索")

            children = node.children
            if node.node_type != "product" and node.has_children and node.id not in ancestors:
                children = self.get_component_children(node.id).children

            next_ancestors = ancestors | {node.id}
            matched_children = [
                matched
                for child in children
                if (matched := expand_and_filter(child, next_ancestors)) is not None
            ]
            if matches(node) or matched_children:
                return node.model_copy(
                    update={
                        "children": matched_children,
                        "has_children": bool(matched_children),
                    }
                )
            return None

        matched_root = expand_and_filter(response.root, frozenset())
        root = matched_root or response.root.model_copy(update={"children": [], "has_children": False})
        return response.model_copy(
            update={
                "root": root,
                "direct_child_count": len(root.children),
                "cached": response.cached,
            }
        )

    def _initialize_disk_cache(self) -> None:
        assert self.cache_path is not None
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.cache_path, timeout=10) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS duro_cache (
                    cache_key TEXT PRIMARY KEY,
                    expires_at REAL NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )

    def _get_disk_cached(self, key: str, model_type: type[BaseModel]) -> Any | None:
        if self.cache_path is None:
            return None
        with self._lock, sqlite3.connect(self.cache_path, timeout=10) as connection:
            row = connection.execute(
                "SELECT payload FROM duro_cache WHERE cache_key = ?", (key,)
            ).fetchone()
            if row is None:
                return None
        try:
            return model_type.model_validate_json(row[0])
        except ValueError:
            with self._lock, sqlite3.connect(self.cache_path, timeout=10) as connection:
                connection.execute("DELETE FROM duro_cache WHERE cache_key = ?", (key,))
            return None

    def _set_disk_cached(self, key: str, value: BaseModel) -> None:
        if self.cache_path is None:
            return
        with self._lock, sqlite3.connect(self.cache_path, timeout=10) as connection:
            connection.execute(
                """
                INSERT INTO duro_cache (cache_key, expires_at, payload) VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    expires_at = excluded.expires_at,
                    payload = excluded.payload
                """,
                (key, 0, value.model_dump_json()),
            )

    def _map_children(self, value: Any, parent_id: str) -> list[DuroBomNode]:
        if not isinstance(value, list):
            return []
        nodes: list[DuroBomNode] = []
        for index, relationship in enumerate(value):
            if not isinstance(relationship, dict):
                continue
            entity = relationship.get("component") or relationship.get("assemblyRevision")
            if isinstance(entity, str):
                entity = {"_id": entity}
            if not isinstance(entity, dict):
                entity = relationship
            entity_id = self._value(entity, "_id", "id")
            if entity_id is None:
                continue
            children_hint = entity.get("children")
            node = self._map_entity(
                entity,
                node_type="component",
                relationship=relationship,
                has_children=isinstance(children_hint, list) and bool(children_hint),
                child_count=len(children_hint) if isinstance(children_hint, list) else None,
            )
            if not node.relationship_id:
                node.relationship_id = f"{parent_id}:{node.id}:{index}"
            nodes.append(node)
        return nodes

    def _map_entity(
        self,
        entity: dict[str, Any],
        node_type: str,
        relationship: dict[str, Any] | None = None,
        children: list[DuroBomNode] | None = None,
        has_children: bool = False,
        child_count: int | None = None,
    ) -> DuroBomNode:
        relationship = relationship or {}
        entity_id = self._value(entity, "_id", "id")
        return DuroBomNode(
            id=str(entity_id or ""),
            relationship_id=self._string_value(relationship, "_id", "id"),
            node_type=node_type,
            name=str(self._value(entity, "name") or ""),
            cpn=self._string_value(entity, "cpn"),
            cpn_variant=self._value(entity, "cpnVariant", "cpn_variant"),
            alias=self._string_value(entity, "alias"),
            revision=self._string_value(entity, "revision"),
            status=self._string_value(entity, "status"),
            quantity=self._value(relationship, "quantity", "qty"),
            item_number=self._value(relationship, "itemNumber", "item_number"),
            notes=self._string_value(relationship, "notes", "note"),
            reference_designators=self._value(
                relationship,
                "refDes",
                "referenceDesignators",
                "reference_designators",
            ),
            waste=self._value(relationship, "waste"),
            unit_of_measure=self._value(
                relationship,
                "unitOfMeasure",
                "unit_of_measure",
                "uom",
            )
            or self._value(entity, "unitOfMeasure", "unit_of_measure", "uom"),
            has_children=has_children,
            child_count=child_count,
            children=children or [],
        )

    def _get_cached(self, cache: dict[str, tuple[float, Any]], key: str, refresh: bool) -> Any | None:
        with self._lock:
            cached = cache.get(key)
            if not refresh and cached:
                return cached[1]
        return None

    def _set_cached(self, cache: dict[str, tuple[float, Any]], key: str, value: Any) -> None:
        with self._lock:
            cache[key] = (time.monotonic(), value)

    @staticmethod
    def _value(source: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = source.get(key)
            if value is not None:
                return value
        return None

    @classmethod
    def _string_value(cls, source: dict[str, Any], *keys: str) -> str | None:
        value = cls._value(source, *keys)
        return str(value) if value not in (None, "") else None
