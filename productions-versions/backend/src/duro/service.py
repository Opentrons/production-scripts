from __future__ import annotations

import json
import threading
import time
from typing import Any

from duro.client import DuroClient
from duro.models import (
    DuroBomNode,
    DuroComponentChildrenResponse,
    DuroProductBomResponse,
    DuroProductSearchRequest,
    DuroProductSearchResponse,
)
from settings import DURO_PRODUCT_CACHE_SECONDS


class DuroService:
    def __init__(self, client: DuroClient, cache_seconds: int = DURO_PRODUCT_CACHE_SECONDS) -> None:
        self.client = client
        self.cache_seconds = max(0, cache_seconds)
        self._lock = threading.RLock()
        self._search_cache: dict[str, tuple[float, DuroProductSearchResponse]] = {}
        self._product_bom_cache: dict[str, tuple[float, DuroProductBomResponse]] = {}
        self._component_cache: dict[str, tuple[float, DuroComponentChildrenResponse]] = {}

    def search_products(
        self,
        payload: DuroProductSearchRequest,
        refresh: bool = False,
    ) -> DuroProductSearchResponse:
        cache_key = json.dumps(payload.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        with self._lock:
            cached = self._search_cache.get(cache_key)
            if not refresh and cached and time.monotonic() - cached[0] < self.cache_seconds:
                return cached[1].model_copy(update={"cached": True})

        response = self.client.search_products(payload)
        with self._lock:
            self._search_cache[cache_key] = (time.monotonic(), response)
        return response

    def list_products(self, refresh: bool = False) -> DuroProductSearchResponse:
        return self.search_products(DuroProductSearchRequest(), refresh=refresh)

    def get_product_bom(self, product_id: str, refresh: bool = False) -> DuroProductBomResponse:
        normalized_id = product_id.strip()
        cached = self._get_cached(self._product_bom_cache, normalized_id, refresh)
        if cached is not None:
            return cached.model_copy(update={"cached": True})

        product = self.client.get_product(normalized_id)
        product.setdefault("_id", normalized_id)
        children = self._map_children(product.get("children"), normalized_id)
        root = self._map_entity(
            product,
            node_type="product",
            children=children,
            has_children=bool(children),
        )
        response = DuroProductBomResponse(
            product_id=normalized_id,
            root=root,
            direct_child_count=len(children),
            source_url=f"{self.client.base_url}/product/view/{normalized_id}",
        )
        self._set_cached(self._product_bom_cache, normalized_id, response)
        return response

    def get_component_children(
        self,
        component_id: str,
        refresh: bool = False,
    ) -> DuroComponentChildrenResponse:
        normalized_id = component_id.strip()
        cached = self._get_cached(self._component_cache, normalized_id, refresh)
        if cached is not None:
            return cached.model_copy(update={"cached": True})

        component = self.client.get_component(normalized_id)
        children = self._map_children(component.get("children"), normalized_id)
        response = DuroComponentChildrenResponse(
            component_id=normalized_id,
            children=children,
            count=len(children),
        )
        self._set_cached(self._component_cache, normalized_id, response)
        return response

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
            ),
            has_children=has_children,
            children=children or [],
        )

    def _get_cached(self, cache: dict[str, tuple[float, Any]], key: str, refresh: bool) -> Any | None:
        with self._lock:
            cached = cache.get(key)
            if not refresh and cached and time.monotonic() - cached[0] < self.cache_seconds:
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
