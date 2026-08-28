from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DuroProductSearchRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    page: int = Field(default=1, ge=1)
    sort: str = "lastModified"
    reverse: bool = True
    limit: int = Field(default=0, ge=0)
    lean: bool = False
    populate: str = "images"


class DuroProduct(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = Field(alias="_id")
    name: str = ""
    cpn: str | None = None
    cpn_variant: Any = Field(default=None, alias="cpnVariant")
    alias: str | None = None
    description: str | None = None
    revision: str | None = None
    status: str | None = None
    company: Any = None
    eid: Any = None
    images: list[Any] = Field(default_factory=list)
    revisions: list[Any] = Field(default_factory=list)
    last_modified: int | str | None = Field(default=None, alias="lastModified")
    modified: int | str | None = None
    created: int | str | None = None
    last_release_prd_rev: Any = Field(default=None, alias="lastReleasePrdRev")
    previous_revision: Any = Field(default=None, alias="previousRevision")
    previous_status: Any = Field(default=None, alias="previousStatus")


class DuroProductSearchResponse(BaseModel):
    success: bool = True
    count: int = 0
    products: list[DuroProduct] = Field(default_factory=list)
    request: DuroProductSearchRequest
    cached: bool = False
    fetched_at: datetime = Field(default_factory=utc_now)


class DuroBomNode(BaseModel):
    id: str
    relationship_id: str | None = None
    node_type: str = "component"
    name: str = ""
    cpn: str | None = None
    cpn_variant: Any = None
    alias: str | None = None
    revision: str | None = None
    status: str | None = None
    quantity: Any = None
    item_number: Any = None
    notes: str | None = None
    reference_designators: Any = None
    waste: Any = None
    unit_of_measure: Any = None
    has_children: bool = False
    child_count: int | None = None
    children: list["DuroBomNode"] = Field(default_factory=list)


class DuroProductBomResponse(BaseModel):
    success: bool = True
    product_id: str
    root: DuroBomNode
    direct_child_count: int = 0
    material_total_count: int = 0
    source_url: str
    cached: bool = False
    fetched_at: datetime = Field(default_factory=utc_now)


class DuroComponentChildrenResponse(BaseModel):
    success: bool = True
    component_id: str
    children: list[DuroBomNode] = Field(default_factory=list)
    count: int = 0
    cached: bool = False
    fetched_at: datetime = Field(default_factory=utc_now)


class DuroConnectionStatus(BaseModel):
    configured: bool
    api_key_valid: bool
    api_key_expires_at: datetime | None = None
    base_url: str


class DuroApiKeyUpdate(BaseModel):
    duro_api_key: SecretStr = Field(min_length=1, max_length=8192)
