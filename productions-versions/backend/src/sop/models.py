from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SopCatalogEntry(BaseModel):
    row_number: int
    project: str = ""
    process: str = ""
    issue_date: str = ""
    link_label: str = ""
    link_url: str | None = None
    drive_file_id: str | None = None
    status: str = ""
    note: str = ""
    raw_values: list[str] = Field(default_factory=list)


class SopMasterSheetResponse(BaseModel):
    spreadsheet_id: str
    sheet_gid: int
    sheet_title: str
    source_url: str
    headers: list[str] = Field(default_factory=list)
    total_rows: int = 0
    linked_file_count: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
    entries: list[SopCatalogEntry] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=utc_now)
    cached: bool = False


class SopPdfPage(BaseModel):
    page_number: int
    text: str
    text_length: int
    category: Literal["instruction", "material_list", "tool_list"] = "instruction"


class SopBomMaterial(BaseModel):
    part_number: str
    name: str
    quantity: float | None = None
    quantity_complete: bool = True
    unit: str | None = None
    sections: list[str] = Field(default_factory=list)
    pages: list[int] = Field(default_factory=list)
    occurrences: int = 1
    confidence: float = Field(default=1, ge=0, le=1)
    source_lines: list[str] = Field(default_factory=list)


class SopBomSection(BaseModel):
    name: str
    page_number: int
    materials: list[SopBomMaterial] = Field(default_factory=list)


class SopQuantityDecision(BaseModel):
    event_id: str = ""
    page_numbers: list[int] = Field(default_factory=list)
    action: str = ""
    target: str = ""
    location: str = ""
    quantity_delta: float = 0
    accumulate: bool = False
    duplicate_of: str | None = None
    reason: str = ""
    evidence: str = ""


class SopPartReference(BaseModel):
    part_number: str
    name: str = ""
    occurrences: int = 0
    quantity: int = 0
    pages: list[int] = Field(default_factory=list)
    source_lines: list[str] = Field(default_factory=list)
    quantity_explanation: str = ""
    quantity_decisions: list[SopQuantityDecision] = Field(default_factory=list)


class SopPdfAnalysisResponse(BaseModel):
    file_id: str
    filename: str
    mime_type: str
    size: int
    modified_time: str | None = None
    page_count: int
    text_length: int
    text_truncated: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)
    pages: list[SopPdfPage] = Field(default_factory=list)
    bom_detected: bool = False
    bom_material_count: int = 0
    bom_occurrence_count: int = 0
    bom_sections: list[SopBomSection] = Field(default_factory=list)
    bom_materials: list[SopBomMaterial] = Field(default_factory=list)
    full_text_material_count: int = 0
    full_text_occurrence_count: int = 0
    full_text_references: list[SopPartReference] = Field(default_factory=list)
    ai_enabled: bool = False
    ai_used: bool = False
    ai_fallback: bool = False
    ai_error: str | None = None
    cached: bool = False
    analyzed_at: datetime = Field(default_factory=utc_now)
