from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _SupplementaryMaterialTextModel(BaseModel):
    @field_validator(
        "material_number",
        "english_name",
        "chinese_name",
        "eid",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        return None if value is None else str(value).strip()


class SupplementaryMaterialCreate(_SupplementaryMaterialTextModel):
    material_number: str = Field(min_length=1, max_length=100)
    english_name: str = Field(default="", max_length=500)
    chinese_name: str = Field(default="", max_length=500)
    eid: str = Field(default="", max_length=100)


class SupplementaryMaterialUpdate(_SupplementaryMaterialTextModel):
    material_number: str | None = Field(default=None, min_length=1, max_length=100)
    english_name: str | None = Field(default=None, max_length=500)
    chinese_name: str | None = Field(default=None, max_length=500)
    eid: str | None = Field(default=None, max_length=100)


class SupplementaryMaterial(SupplementaryMaterialCreate):
    id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SupplementaryMaterialSyncStatus(BaseModel):
    source_url: str
    interval_seconds: int
    auto_sync_enabled: bool = True
    last_synced_at: datetime | None = None
    last_error: str = ""
    syncing: bool = False


class SupplementaryMaterialListResponse(BaseModel):
    items: list[SupplementaryMaterial] = Field(default_factory=list)
    total: int = 0
    sync_status: SupplementaryMaterialSyncStatus | None = None


class SupplementaryMaterialSyncResult(BaseModel):
    source_url: str
    synced_at: datetime
    total: int
    created_count: int = 0
    updated_count: int = 0
    removed_count: int = 0
