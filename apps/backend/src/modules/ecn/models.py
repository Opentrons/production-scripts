from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class EcnRecord(BaseModel):
    id: str
    table: Literal["eng", "ipqc"] = "eng"
    source_row: int = 0
    ecn_number: str = ""
    ecn_title: str = ""
    product_name: str = ""
    category: str = "ECN"
    form_number: str = ""
    change_item: str = ""
    before_change: str = ""
    after_change: str = ""
    change_date: str = ""
    changed_by: str = ""
    change_category: Literal["software", "material", "drawing", "process", "other"] | None = None
    affected_document: Literal["drawing", "bom", "sop", "sip", "other"] | None = None
    approved_by: str = ""
    record_url: str = ""
    folder_id: str = ""
    duro_number: str = ""
    origin: Literal["google", "created"] = "google"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    extra_fields: dict[str, str] = Field(default_factory=dict)


class EcnRecordsResponse(BaseModel):
    records: list[EcnRecord] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
    source_url: str
    storage: Literal["mongodb"] = "mongodb"
    bootstrapped: bool = False
    next_ecn_number: str
    changed_by_options: list[str] = Field(default_factory=list)
    status_options: list[str] = Field(default_factory=list)
    table: Literal["eng", "ipqc"] = "eng"


class EcnCreateRequest(BaseModel):
    ecn_number: str = Field(min_length=1, max_length=32)
    ecn_title: str = Field(min_length=1, max_length=180)
    product_model: str = Field(min_length=1, max_length=120)
    change_item: str = Field(default="", max_length=500)
    before_change: str = Field(default="", max_length=500)
    after_change: str = Field(default="", max_length=500)
    change_date: date | None = None
    changed_by: str = Field(min_length=1, max_length=120)
    change_category: Literal["software", "material", "drawing", "process", "other"] | None = None
    affected_document: Literal["drawing", "bom", "sop", "sip", "other"] | None = None


class EcnCreateResponse(BaseModel):
    record: EcnRecord
    year_folder_created: bool
    folder_url: str
    spreadsheet_url: str


class EcnUpdateRequest(BaseModel):
    ecn_title: str = Field(min_length=1, max_length=180)
    product_name: str = Field(max_length=120)
    change_item: str = Field(max_length=500)
    before_change: str = Field(max_length=500)
    after_change: str = Field(max_length=500)
    change_date: str = Field(max_length=80)
    changed_by: str = Field(max_length=120)
    change_category: Literal["software", "material", "drawing", "process", "other"] | None = None
    affected_document: Literal["drawing", "bom", "sop", "sip", "other"] | None = None
    approved_by: str = Field(max_length=120)
    duro_number: str = Field(max_length=120)


class EcnSyncDifference(BaseModel):
    source_row: int
    ecn_number: str = ""
    form_number: str = ""
    changed_fields: list[str] = Field(default_factory=list)


class EcnSyncCheckResponse(BaseModel):
    in_sync: bool
    google_total: int
    mongodb_total: int
    missing_count: int = 0
    extra_count: int = 0
    changed_count: int = 0
    missing_in_mongodb: list[EcnSyncDifference] = Field(default_factory=list)
    extra_in_mongodb: list[EcnSyncDifference] = Field(default_factory=list)
    changed: list[EcnSyncDifference] = Field(default_factory=list)
    checked_at: datetime
    source_url: str


class EcnMonitorSettings(BaseModel):
    enabled: bool = False
    interval_minutes: int = Field(default=1440, ge=5, le=10080)
    scan_items: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None
    last_run_at: datetime | None = None


class EcnRiskScanRequest(BaseModel):
    scan_items: list[str] | None = None


class EcnRiskScanLog(BaseModel):
    at: datetime
    step: str
    title: str
    status: Literal["running", "success", "warning", "error", "info"] = "info"
    message: str
    checked_count: int | None = None
    alert_count: int | None = None
    issues: list[dict] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)


class EcnRiskScanResult(BaseModel):
    id: str
    scan_date: str
    scanned_at: datetime
    started_at: datetime
    finished_at: datetime
    trigger: str
    selected_items: list[str] = Field(default_factory=list)
    sync_records: list[dict] = Field(default_factory=list)
    process: list[str] = Field(default_factory=list)
    process_logs: list[EcnRiskScanLog] = Field(default_factory=list)
    total_alerts: int = 0
    categories: list[dict] = Field(default_factory=list)
