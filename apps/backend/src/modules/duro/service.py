from __future__ import annotations

import json
import sqlite3
import threading
import time
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from modules.duro.client import DuroApiError, DuroClient
from modules.duro.models import (
    DuroBomNode,
    DuroComponentChildrenResponse,
    DuroVersionCatalogResponse,
    DuroVersionComponent,
    DuroVersionGroup,
    DuroProductBomResponse,
    DuroProductSearchRequest,
    DuroProductSearchResponse,
    utc_now,
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
        self._version_catalog_cache: tuple[float, DuroVersionCatalogResponse] | None = None
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

    def get_version_catalog(self, refresh: bool = False) -> DuroVersionCatalogResponse:
        """Return Duro software/version touchpoints and their full child details."""

        disk_key = "duro-version-catalog:v2"
        with self._lock:
            if not refresh and self._version_catalog_cache is not None:
                return self._version_catalog_cache[1].model_copy(update={"cached": True})
        if not refresh:
            disk_cached = self._get_disk_cached(disk_key, DuroVersionCatalogResponse)
            if disk_cached is not None:
                with self._lock:
                    self._version_catalog_cache = (time.monotonic(), disk_cached)
                return disk_cached.model_copy(update={"cached": True})

        products_response = self.list_products(refresh=refresh)
        groups: list[DuroVersionGroup] = []
        matched_product_ids: set[str] = set()
        seen_groups: set[tuple[str, str]] = set()
        raw_products: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(products_response.products)))) as executor:
            futures = {
                executor.submit(self.client.get_product, product.id): product.id
                for product in products_response.products
            }
            for future, product_id in futures.items():
                raw_products[product_id] = future.result()

        raw_components: dict[str, dict[str, Any]] = {}
        for product in products_response.products:
            raw_product = raw_products.get(product.id) or {}
            for relationship, parent_entity, parent_path in self._find_version_parents(
                raw_product.get("children"),
                [str(product.cpn or product.name or product.id)],
            ):
                parent_id = self._entity_id(parent_entity)
                if not parent_id:
                    continue
                group_key = (product.id, parent_id)
                if group_key in seen_groups:
                    continue
                seen_groups.add(group_key)
                matched_product_ids.add(product.id)
                detailed_parent = raw_components.get(parent_id)
                if detailed_parent is None:
                    detailed_parent = self.client.get_component(parent_id)
                    raw_components[parent_id] = detailed_parent
                parent_entity = detailed_parent or parent_entity
                children = self._collect_version_children(
                    parent_entity,
                    parent_path,
                    visited={parent_id},
                )
                groups.append(
                    DuroVersionGroup(
                        product_id=product.id,
                        product_cpn=product.cpn,
                        product_name=product.name,
                        product_revision=product.revision,
                        parent_id=parent_id,
                        parent_cpn=self._string_value(parent_entity, "cpn"),
                        parent_name=str(self._value(parent_entity, "name") or ""),
                        parent_revision=self._string_value(parent_entity, "revision"),
                        parent_description=str(self._value(parent_entity, "description") or ""),
                        children=children,
                    )
                )

        response = DuroVersionCatalogResponse(
            products_scanned=len(products_response.products),
            matched_products=len(matched_product_ids),
            parent_menu_count=len(groups),
            child_component_count=sum(len(group.children) for group in groups),
            groups=groups,
            fetched_at=utc_now(),
        )
        with self._lock:
            self._version_catalog_cache = (time.monotonic(), response)
        self._set_disk_cached(disk_key, response)
        return response

    def _find_version_parents(
        self,
        relationships: Any,
        path: list[str],
    ) -> list[tuple[dict[str, Any], dict[str, Any], list[str]]]:
        if not isinstance(relationships, list):
            return []
        matches: list[tuple[dict[str, Any], dict[str, Any], list[str]]] = []
        for relationship in relationships:
            if not isinstance(relationship, dict):
                continue
            entity = self._relationship_entity(relationship)
            if not isinstance(entity, dict):
                continue
            label = str(
                self._value(entity, "cpn", "name", "_id", "id") or ""
            ).strip()
            next_path = [*path, label] if label else list(path)
            if self._is_version_parent(entity):
                matches.append((relationship, entity, next_path))
            matches.extend(self._find_version_parents(entity.get("children"), next_path))
        return matches

    def _collect_version_children(
        self,
        parent_entity: dict[str, Any],
        parent_path: list[str],
        visited: set[str],
    ) -> list[DuroVersionComponent]:
        children = parent_entity.get("children")
        if not isinstance(children, list):
            return []
        collected: list[DuroVersionComponent] = []
        for relationship in children:
            if not isinstance(relationship, dict):
                continue
            entity = self._relationship_entity(relationship)
            if isinstance(entity, str):
                entity = {"_id": entity}
            if not isinstance(entity, dict):
                continue
            entity_id = self._entity_id(entity)
            if not entity_id or entity_id in visited:
                continue
            visited.add(entity_id)
            if "children" not in entity or (not entity.get("name") and not entity.get("cpn")):
                entity = self.client.get_component(entity_id)
            label = str(self._value(entity, "cpn", "name", "_id", "id") or entity_id)
            detail = self._version_component_detail(
                entity,
                relationship,
                [*parent_path, label],
            )
            collected.append(detail)
            collected.extend(self._collect_version_children(entity, [*parent_path, label], visited))
        return collected

    @classmethod
    def _version_component_detail(
        cls,
        entity: dict[str, Any],
        relationship: dict[str, Any],
        path: list[str],
    ) -> DuroVersionComponent:
        specs = cls._dict_list(entity.get("specs"))
        custom_specs = cls._dict_list(entity.get("customSpecs"))
        custom_properties = cls._dict_list(entity.get("customProperties"))
        description = str(entity.get("description") or "")
        source_lines = [description]
        for collection in (specs, custom_specs, custom_properties):
            for item in collection:
                key = str(item.get("key") or item.get("name") or "").strip()
                value = str(item.get("value") or item.get("description") or "").strip()
                if key or value:
                    source_lines.append(f"{key}: {value}".strip(": "))
        source_text = "\n".join(line for line in source_lines if line).strip()
        return DuroVersionComponent(
            id=cls._entity_id(entity),
            cpn=cls._string_value(entity, "cpn"),
            name=str(entity.get("name") or ""),
            revision=cls._string_value(entity, "revision", "revisionValue"),
            status=cls._string_value(entity, "status"),
            category=cls._string_value(entity, "category"),
            quantity=cls._value(relationship, "quantity", "qty"),
            description=description,
            app_version=cls._extract_version(source_text, "app"),
            firmware_version=cls._extract_version(source_text, "firmware"),
            test_commit_hash=cls._extract_commit_hash(source_text),
            test_tag=cls._extract_test_tag(source_text),
            path=path,
            specs=specs,
            custom_specs=custom_specs,
            custom_properties=custom_properties,
            source_text=source_text,
        )

    @staticmethod
    def _dict_list(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    @classmethod
    def _is_version_parent(cls, entity: dict[str, Any]) -> bool:
        fields = [
            entity.get("cpn"),
            entity.get("name"),
            entity.get("description"),
            entity.get("category"),
        ]
        for collection_name in ("specs", "customSpecs", "customProperties"):
            for item in cls._dict_list(entity.get(collection_name)):
                fields.extend((item.get("key"), item.get("name"), item.get("value")))
        text = " ".join(str(value or "") for value in fields)
        return bool(
            re.search(r"\bSOFTWARE\b", text, flags=re.IGNORECASE)
            and re.search(r"\bFIRMWARE\b", text, flags=re.IGNORECASE)
        )

    @staticmethod
    def _relationship_entity(relationship: dict[str, Any]) -> Any:
        return relationship.get("component") or relationship.get("assemblyRevision") or relationship

    @staticmethod
    def _entity_id(entity: dict[str, Any]) -> str:
        return str(entity.get("_id") or entity.get("id") or "").strip()

    @staticmethod
    def _extract_version(text: str, kind: str) -> str | None:
        if kind == "app":
            patterns = (
                r"(?:desktop\s+app|app(?:lication)?\s+version|software\s+version)\s*[:=\-]?\s*(?:v)?([0-9]+(?:\.[0-9]+){1,3})\b",
                r"Opentrons-v([0-9]+(?:\.[0-9]+){1,3})\b",
            )
        else:
            patterns = (
                r"(?:robot\s+)?firmware(?:\s+version)?\s*[:=\-]?\s*(v?[0-9]+(?:\.[0-9]+){0,3}(?:[-+][A-Za-z0-9._-]+)?)",
                r"ot3-firmware/releases/(?:download|tag)/v?([0-9]+(?:\.[0-9]+){0,3})",
            )
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                return value if value.lower().startswith("v") else f"v{value}"
        return None

    @staticmethod
    def _extract_commit_hash(text: str) -> str | None:
        patterns = (
            r"(?:test\s+)?commit(?:\s+hash)?\s*[:=#\-]\s*([0-9a-f]{7,40})\b",
            r"/commit/([0-9a-f]{7,40})\b",
        )
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _extract_test_tag(text: str) -> str | None:
        match = re.search(r"(?:hardware\s+testing\s+tag|test\s+tag)\s*[:=]\s*([^\s]+)", text, flags=re.IGNORECASE)
        return match.group(1).strip() if match else None

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
