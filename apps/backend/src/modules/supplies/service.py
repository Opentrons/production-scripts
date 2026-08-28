from __future__ import annotations

from typing import Any

from modules.supplies.models import (
    SupplementaryMaterial,
    SupplementaryMaterialCreate,
    SupplementaryMaterialUpdate,
)
from modules.supplies.repository import (
    DuplicateSupplementaryMaterialError,
)


class SupplementaryMaterialNotFoundError(LookupError):
    pass


class SupplementaryMaterialService:
    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def list(self, query: str | None = None) -> list[SupplementaryMaterial]:
        return self.repository.list(query)

    def create(self, payload: SupplementaryMaterialCreate) -> SupplementaryMaterial:
        return self.repository.create(payload)

    def update(
        self,
        material_id: str,
        payload: SupplementaryMaterialUpdate,
    ) -> SupplementaryMaterial:
        material = self.repository.update(material_id, payload)
        if material is None:
            raise SupplementaryMaterialNotFoundError(f"辅料不存在: {material_id}")
        return material

    def delete(self, material_id: str) -> None:
        if not self.repository.delete(material_id):
            raise SupplementaryMaterialNotFoundError(f"辅料不存在: {material_id}")
