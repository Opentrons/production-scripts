from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests
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

OPENTRONS_GITHUB_REPO = "Opentrons/opentrons"
OPENTRONS_COMMITS_URL = f"https://github.com/{OPENTRONS_GITHUB_REPO}/commits"


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
        self._github_commit_cache: dict[str, str | None] = {}
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

        disk_key = "duro-version-catalog:v4"
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

        self._enrich_commit_ids(groups, refresh=refresh)

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
    def _extract_version(text: str, kind: str) -> str:
        label = "App" if kind == "app" else r"(?:FW|Firmware)"
        label_match = re.search(
            rf"^\s*(?:[A-Za-z0-9 _./-]+\s+)?{label}\s*[:：]\s*(.*)$",
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if not label_match:
            return ""
        value = label_match.group(1).strip()

        # Duro details may include the firmware version in a path or suffix,
        # such as "controller-v52" or "controller/V52".
        version_match = re.search(
            r"(?<![A-Za-z0-9])v\d+(?:\.\d+){0,3}\b",
            value,
            flags=re.IGNORECASE,
        )
        if version_match:
            return version_match.group(0).lower()

        # Keep supporting details that contain a bare numeric version.
        version_match = re.match(r"\d+(?:\.\d+){0,3}\b", value)
        if not version_match:
            return ""
        return f"v{version_match.group(0)}"

    @classmethod
    def _extract_commit_hash(cls, text: str) -> str | None:
        # Scripts: <ref>
        # or Scripts: https://.../tree/<ref>
        # or Scripts:\nhttps://.../tree/<ref>
        scripts_match = re.search(
            r"^\s*Scripts?\s*[:：]\s*(.*)$",
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if scripts_match:
            value = scripts_match.group(1).strip()
            ref = cls._extract_git_ref(value)
            if ref:
                return ref
            rest = text[scripts_match.end() :].lstrip("\r\n")
            next_line = rest.splitlines()[0] if rest else ""
            ref = cls._extract_git_ref(next_line)
            if ref:
                return ref

        # Some Duro records do not have Scripts, but store the test ref under
        # labels like "Hardware Testing Tag" or "Release Branch".
        for line in text.splitlines():
            label, separator, value = line.partition(":")
            if not separator:
                label, separator, value = line.partition("：")
            if not separator:
                continue
            if re.search(r"\b(?:Tag|Branch)\s*$", label.strip(), flags=re.IGNORECASE):
                ref = cls._extract_git_ref(value)
                if ref:
                    return ref

        # Protocol: .../xxxx.py -> xxxx.py
        match = re.search(
            r"^\s*Protocol\s*[:：]\s*.*?([^/\s]+\.py)\b",
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if match:
            return match.group(1).strip()

        return None

    @staticmethod
    def _extract_git_ref(value: str) -> str:
        text = value.strip()
        if not text:
            return ""
        tree_match = re.search(r"/tree/([^\s?#]+)", text)
        if tree_match:
            return tree_match.group(1).rstrip("/")
        return text.split()[0].strip().rstrip("/")

    @staticmethod
    def _extract_test_tag(text: str) -> str | None:
        match = re.search(r"(?:hardware\s+testing\s+tag|test\s+tag)\s*[:=]\s*([^\s]+)", text, flags=re.IGNORECASE)
        return match.group(1).strip() if match else None

    @classmethod
    def commits_page_url(cls, commit_hash: str) -> str:
        return f"{OPENTRONS_COMMITS_URL}/{commit_hash.strip()}/"

    @staticmethod
    def _is_resolvable_commit_ref(value: str) -> bool:
        text = value.strip()
        if not text or text.lower().endswith(".py"):
            return False
        # Protocol filenames and nested tree paths are not Git refs.
        if "/" in text:
            return False
        return True

    def _enrich_commit_ids(self, groups: list[DuroVersionGroup], *, refresh: bool = False) -> None:
        refs = sorted(
            {
                child.test_commit_hash.strip()
                for group in groups
                for child in group.children
                if child.test_commit_hash and self._is_resolvable_commit_ref(child.test_commit_hash)
            }
        )
        if not refs:
            return

        resolved: dict[str, str | None] = {}
        missing: list[str] = []
        with self._lock:
            for ref in refs:
                if not refresh and ref in self._github_commit_cache:
                    resolved[ref] = self._github_commit_cache[ref]
                else:
                    missing.append(ref)

        if missing:
            with ThreadPoolExecutor(max_workers=min(6, max(1, len(missing)))) as executor:
                futures = {executor.submit(self._resolve_github_commit_id, ref): ref for ref in missing}
                for future, ref in futures.items():
                    try:
                        resolved[ref] = future.result()
                    except Exception:
                        resolved[ref] = None
            with self._lock:
                for ref in missing:
                    self._github_commit_cache[ref] = resolved.get(ref)

        for group in groups:
            for child in group.children:
                ref = (child.test_commit_hash or "").strip()
                commit_id = resolved.get(ref)
                if commit_id:
                    child.test_commit_id = commit_id

    def _resolve_github_commit_id(self, ref: str) -> str | None:
        """Resolve the tip commit SHA for a branch/tag/ref on Opentrons/opentrons."""

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "production-scripts-duro",
        }
        token = (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = requests.get(
                f"https://api.github.com/repos/{OPENTRONS_GITHUB_REPO}/commits",
                params={"sha": ref, "per_page": 1},
                headers=headers,
                timeout=15,
            )
            if response.status_code != 200:
                return None
            payload = response.json()
            if not isinstance(payload, list) or not payload:
                return None
            sha = payload[0].get("sha") if isinstance(payload[0], dict) else None
            return str(sha).strip() or None
        except (requests.RequestException, ValueError, TypeError, IndexError, KeyError):
            return None

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
