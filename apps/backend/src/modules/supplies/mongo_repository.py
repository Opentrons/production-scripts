from __future__ import annotations

import re
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from core.persistence import get_document_collection
from modules.supplies.models import (
    SupplementaryMaterial,
    SupplementaryMaterialCreate,
    SupplementaryMaterialUpdate,
)
from modules.supplies.repository import DuplicateSupplementaryMaterialError
from modules.supplies.seed import INITIAL_SUPPLEMENTARY_MATERIALS


class MongoSupplementaryMaterialRepository:
    """MongoDB repository used by non-simulating production processes."""

    COLLECTION = "supplementary_materials"
    META_COLLECTION = "supplementary_material_meta"
    SEED_VERSION = "2026-08-28-v1"

    def __init__(self, *, seed_initial: bool = False) -> None:
        self._seed_initial = seed_initial
        self._initialized = False
        self._lock = RLock()

    def list(self, query: str | None = None) -> list[SupplementaryMaterial]:
        collection = self._collection()
        normalized_query = (query or "").strip()
        selector: dict[str, object] = {}
        if normalized_query:
            expression = {"$regex": re.escape(normalized_query), "$options": "i"}
            selector = {
                "$or": [
                    {"material_number": expression},
                    {"english_name": expression},
                    {"chinese_name": expression},
                    {"eid": expression},
                ]
            }
        documents = collection.find(selector).sort("material_number", 1)
        return [self._from_document(document) for document in documents]

    def get(self, material_id: str) -> SupplementaryMaterial | None:
        document = self._collection().find_one({"_id": material_id})
        return self._from_document(document) if document else None

    def create(self, payload: SupplementaryMaterialCreate) -> SupplementaryMaterial:
        now = datetime.now(timezone.utc)
        material = SupplementaryMaterial(
            id=f"supply_{uuid4().hex[:12]}",
            **payload.model_dump(),
            created_at=now,
            updated_at=now,
        )
        try:
            self._collection().insert_one(self._to_document(material))
        except DuplicateKeyError as exc:
            raise DuplicateSupplementaryMaterialError(
                f"物料编号已存在: {material.material_number}"
            ) from exc
        return material

    def update(
        self,
        material_id: str,
        payload: SupplementaryMaterialUpdate,
    ) -> SupplementaryMaterial | None:
        current = self.get(material_id)
        if current is None:
            return None
        changes = {
            key: value
            for key, value in payload.model_dump(exclude_unset=True).items()
            if value is not None
        }
        updated = current.model_copy(
            update={**changes, "updated_at": datetime.now(timezone.utc)}
        )
        try:
            self._collection().replace_one(
                {"_id": material_id}, self._to_document(updated)
            )
        except DuplicateKeyError as exc:
            raise DuplicateSupplementaryMaterialError(
                f"物料编号已存在: {updated.material_number}"
            ) from exc
        return updated

    def delete(self, material_id: str) -> bool:
        result = self._collection().delete_one({"_id": material_id})
        return getattr(result, "deleted_count", 0) > 0

    def _collection(self):
        self._ensure_initialized()
        return get_document_collection(self.COLLECTION)

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            collection = get_document_collection(self.COLLECTION)
            collection.create_index("material_number", unique=True)
            collection.create_index("updated_at")
            if self._seed_initial:
                self._seed_initial_materials(collection)
            self._initialized = True

    def _seed_initial_materials(self, collection) -> None:
        meta = get_document_collection(self.META_COLLECTION)
        if meta.find_one({"_id": "seed_version"}) is not None:
            return
        now = datetime.now(timezone.utc)
        for material_number, english_name, chinese_name, eid in INITIAL_SUPPLEMENTARY_MATERIALS:
            material = SupplementaryMaterial(
                id=f"supply_{uuid4().hex[:12]}",
                material_number=material_number,
                english_name=english_name,
                chinese_name=chinese_name,
                eid=eid,
                created_at=now,
                updated_at=now,
            )
            collection.update_one(
                {"material_number": material_number},
                {"$setOnInsert": self._to_document(material)},
                upsert=True,
            )
        meta.update_one(
            {"_id": "seed_version"},
            {"$set": {"value": self.SEED_VERSION, "updated_at": now}},
            upsert=True,
        )

    @staticmethod
    def _to_document(material: SupplementaryMaterial) -> dict[str, object]:
        document = material.model_dump(mode="python")
        document["_id"] = document.pop("id")
        return document

    @staticmethod
    def _from_document(document: dict[str, object]) -> SupplementaryMaterial:
        payload = dict(document)
        payload["id"] = str(payload.pop("_id", payload.get("id", "")))
        return SupplementaryMaterial.model_validate(payload)
