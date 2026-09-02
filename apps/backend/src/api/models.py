from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class UploadDataRequest(BaseModel):
    csv_file_path: str
    zip_file_path: str | None = None
    record_id: str | None = None


class UploadRecordStartRequest(BaseModel):
    csv_file_name: str = Field(default="", max_length=255)
    zip_file_name: str | None = Field(default=None, max_length=255)
    source: str = Field(default="api", min_length=1, max_length=32)
    idempotency_key: str | None = Field(default=None, max_length=128)
    csv_size: int | None = Field(default=None, ge=0)
    csv_sha256: str | None = Field(default=None, min_length=64, max_length=64)


class UploadRecordFailureRequest(BaseModel):
    failure_stage: str = Field(default="request_transport", min_length=1, max_length=80)
    failure_code: str = Field(default="client_request_failed", min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=4000)
    detail: str | None = Field(default=None, max_length=10000)


class UploadDataResponse(BaseModel):
    csv_file: str | None = None
    zip_file: str | None = None
    success: bool
    record_id: str | None = None
    message: str | None = None
    status: str | None = None
    deduplicated: bool = False


class UploadFinishSettingUpdateRequest(BaseModel):
    model: str
    test_type: str
    require_finished: bool


class UploadFinishSettingResponse(BaseModel):
    options: list[dict[str, Any]] = Field(default_factory=list)
    settings: list[dict[str, Any]] = Field(default_factory=list)
    database_available: bool = True
    error: str | None = None


class UploadRecordListResponse(BaseModel):
    records: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    error: str | None = None


class UploadRecordStatsResponse(BaseModel):
    total: int = 0
    finished: int = 0
    success: int = 0
    failed: int = 0
    running: int = 0
    success_rate: float = 0
    highest_product: dict[str, Any] | None = None
    lowest_product: dict[str, Any] | None = None
    products: list[dict[str, Any]] = Field(default_factory=list)
    test_durations: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class UploadRecordFilterOptionsResponse(BaseModel):
    models: list[str] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=list)
    error: str | None = None


class UnitTrackerRowsResponse(BaseModel):
    columns: list[dict[str, Any]] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 100
    source: str = "mongodb"
    error: str | None = None


class UnitTrackerOptionsResponse(BaseModel):
    options: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class UnitTrackerSyncResponse(BaseModel):
    success: bool
    scanned: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class ProductStatusUpdateRequest(BaseModel):
    barcode: str
    status: str


class ProductStatusUpdateResponse(BaseModel):
    success: bool
    barcode: str
    status: str
    matched_count: int = 0
    modified_count: int = 0
    error: str | None = None


class ProductManagementListResponse(BaseModel):
    products: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 100
    error: str | None = None


class ProductManagementFilterOptionsResponse(BaseModel):
    models: list[str] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=list)
    test_types: list[str] = Field(default_factory=list)
    error: str | None = None


class ProductManagementSyncResponse(BaseModel):
    success: bool
    source_records: int = 0
    skipped_records: int = 0
    total_products: int = 0
    created_count: int = 0
    updated_count: int = 0
    error: str | None = None


class ProductManagementManualAddRequest(BaseModel):
    barcode: str
    status: str = "Testing"
    model: str
    oem: str
    test_type: str
    csv_link: str | None = None
    source_csv_path: str | None = None


class ProductManagementManualAddResponse(BaseModel):
    success: bool
    barcode: str
    created_product: bool = False
    added_test: bool = False
    product: dict[str, Any] | None = None
    error: str | None = None


class FileResourceProjectsResponse(BaseModel):
    projects: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class FileResourceVersionResponse(BaseModel):
    success: bool = True
    version: dict[str, Any]


class FileResourceVersionUpdateRequest(BaseModel):
    version: str | None = None
    version_notes: str | None = None


class FileResourceDeleteResponse(BaseModel):
    success: bool
    deleted_version_id: str


class InformationFile(BaseModel):
    id: str
    number: str
    subject: str
    product_model: str | None = None
    effective_date: str | None = None
    web_view_link: str


class InformationFilesResponse(BaseModel):
    kind: Literal["ecn", "contact"]
    year: int
    source_url: str
    files: list[InformationFile] = Field(default_factory=list)
    total: int = 0
    error: str | None = None


class DataLinksResponse(BaseModel):
    environment: str | None = None
    config_file: str | None = None
    current_date: str | None = None
    current_month: int | None = None
    links: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class MessageListResponse(BaseModel):
    messages: list[dict[str, Any]]
    total: int
    unread_count: int = 0
    error: str | None = None


class MarkMessageReadResponse(BaseModel):
    success: bool
    message: str | None = None
    error: str | None = None


class CollectionListResponse(BaseModel):
    collections: list[str]
    total: int
    error: str | None = None


class CollectionDataResponse(BaseModel):
    data: list[dict[str, Any]]
    total: int
    page: int | None = None
    page_size: int | None = None
    collection: str | None = None
    error: str | None = None


class CollectionFilterOptionsResponse(BaseModel):
    models: list[str] = Field(default_factory=list)
    types: list[str] = Field(default_factory=list)
    total_results: list[str] = Field(default_factory=list)
    error: str | None = None


class IntegrationCollectionDataItem(BaseModel):
    collection: str
    update_time: str
    sn: str | None = None
    model: str | None = None
    type: str | None = None
    total_result: str | None = None


class IntegrationCollectionDataResponse(BaseModel):
    data: list[IntegrationCollectionDataItem]
    count: int
    limit: int
    has_more: bool
    next_cursor: str | None = None
    collection: str
    snapshot_time: str


class TestDataResponse(BaseModel):
    data: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    error: str | None = None


class DataAnalysisPathRequest(BaseModel):
    file_paths: list[str] = Field(default_factory=list)


class DataAnalysisOnlineRequest(BaseModel):
    barcode: str | None = None
    product: str
    test_type: str
    csv_link: str


class DataAnalysisResponse(BaseModel):
    analyses: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)


class DataAnalysisSpecVolume(BaseModel):
    volume: float
    cv: float
    d: float


class DataAnalysisSpecRequest(BaseModel):
    product: str
    product_name: str | None = None
    analysis_product: str | None = None
    test_type: str = "gravimetric"
    test_name: str = "Gravimetric"
    volumes: list[DataAnalysisSpecVolume] = Field(default_factory=list)


class DataAnalysisSpecResponse(BaseModel):
    products: list[dict[str, Any]] = Field(default_factory=list)
    specs: list[dict[str, Any]] = Field(default_factory=list)
    storage: str = "default"
    error: str | None = None


class ServiceStatus(BaseModel):
    status: str
    message: str
    elapsed_ms: float | None = None


class HealthResponse(BaseModel):
    status: bool
    elapsed_ms: float | None = None
    checked_at: datetime | None = None
    services: dict[str, ServiceStatus]


class PullFolderResponse(BaseModel):
    success: bool
    message: str
    robot_ip: str
    folder_name: str
    zip_path: str | None = None
    pull_method: str
    target_dir: str | None = None
    file_name: str


class RobotInfo(BaseModel):
    ip: str
    port: int
    online: bool = False
    service_status: str = "unknown"
    version: str | None = None
    name: str | None = None
    robot_type: str | None = None
    robot_model: str | None = None
    serial_number: str | None = None
    error: str | None = None
    api_version: str | None = None
    min_api_version: str | None = None
    max_api_version: str | None = None
    fw_version: str | None = None
    health_fetch_failed: bool = False


class RobotCommandRequest(BaseModel):
    ips: list[str] = Field(min_length=1)
    port: int = 31950
    method: str = "GET"
    path: str
    body: dict[str, Any] | None = None
    timeout: int = 10


class RobotCommandResult(BaseModel):
    ip: str
    success: bool
    status_code: int | None = None
    response: Any = None
    error: str | None = None


class RobotBatchCommandResponse(BaseModel):
    results: list[RobotCommandResult]


class RobotSshCommandExecuteRequest(BaseModel):
    ip: str
    command: str = Field(min_length=1, max_length=20000)
    timeout: int = Field(default=30, ge=1, le=300)


class RobotSshCommandBatchExecuteRequest(BaseModel):
    ips: list[str] = Field(min_length=1, max_length=100)
    command: str = Field(min_length=1, max_length=20000)
    timeout: int = Field(default=30, ge=1, le=300)
    concurrency: int = Field(default=8, ge=1, le=20)


class RobotSshKeyInstallRequest(BaseModel):
    ips: list[str] = Field(min_length=1, max_length=100)
    timeout: int = Field(default=30, ge=1, le=300)
    concurrency: int = Field(default=4, ge=1, le=10)


class RobotCodeFlashRequest(BaseModel):
    ip: str = Field(min_length=1, max_length=64)
    command: str = Field(min_length=1, max_length=1000)
    timeout: int = Field(default=1800, ge=30, le=7200)
    branch: str = Field(min_length=1, max_length=255)
    pull: bool = False


class RobotSshCommandCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    command: str = Field(min_length=1, max_length=20000)
    description: str = Field(default="", max_length=500)
    tag: Literal["general", "risk"] = "general"


class RobotSshCommandUpdateRequest(RobotSshCommandCreateRequest):
    pass


class RobotVersionCaptureRequest(BaseModel):
    ip: str = Field(min_length=1, max_length=255)
    port: int = Field(default=31950, ge=1, le=65535)
    product_type: Literal[
        "robot",
        "pipette_single_channel",
        "pipette_8_channels",
        "pipette_96_channels_200ul",
        "pipette_96_channels_1000ul",
        "gripper",
    ]
    test_name: str = Field(min_length=1, max_length=200)


class RobotsScanResponse(BaseModel):
    total: int
    online_count: int
    offline_count: int
    abnormal_count: int = 0
    scan_network: str
    server_ip: str | None = None
    gateway: str
    scan_gateways: list[str] = Field(default_factory=list)
    online_robots: list[dict[str, Any]] = Field(default_factory=list)
    offline_robots: list[dict[str, Any]] = Field(default_factory=list)
    abnormal_robots: list[dict[str, Any]] = Field(default_factory=list)
    cached_at: str | None = None
    scan_started_at: str | None = None
    scan_duration_ms: int | None = None
    refreshing: bool = False
    last_error: str | None = None


class RobotScanGateway(BaseModel):
    gateway: str
    scan_range: str
    created_at: str | None = None
    updated_at: str | None = None


class RobotScanGatewayCreateRequest(BaseModel):
    gateway: str


class RobotScanGatewaysResponse(BaseModel):
    gateways: list[RobotScanGateway] = Field(default_factory=list)


class RobotControlSummaryResponse(BaseModel):
    ip: str
    port: int
    http_connected: bool
    ssh_connected: bool
    health: dict[str, Any] | None = None
    instruments: dict[str, Any] | None = None
    modules: dict[str, Any] | None = None
    positions: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)


class RobotHomeRequest(BaseModel):
    target: str = "robot"
    mount: str | None = None
    port: int = 31950


class RobotMoveRequest(BaseModel):
    target: str
    point: list[float] = Field(min_length=3, max_length=3)
    mount: str
    model: str | None = None
    port: int = 31950


class RobotResetRequest(BaseModel):
    axes: list[
        Literal[
            "x",
            "y",
            "leftZ",
            "rightZ",
            "leftPlunger",
            "rightPlunger",
            "extensionZ",
            "extensionJaw",
            "axis96ChannelCam",
        ]
    ] = Field(min_length=1, max_length=9)
    port: int = 31950


class RobotJogRunRequest(BaseModel):
    port: int = 31950


class RobotJogMoveRequest(BaseModel):
    direction: Literal[
        "up",
        "down",
        "left",
        "right",
        "z_up",
        "z_down",
        "plunger_up",
        "plunger_down",
    ]
    step_mm: float = Field(default=10, gt=0, le=100)
    mount: Literal["left", "right", "gripper"] = "left"
    port: int = 31950


class RobotJogGripperRequest(BaseModel):
    action: Literal["grip", "ungrip"]
    port: int = 31950


class RobotJogDropTipRequest(BaseModel):
    pipette_id: str = Field(min_length=1, max_length=100)
    home_after: bool | None = None
    port: int = 31950


class RobotBarcodeProvisionRequest(BaseModel):
    kind: Literal["robot", "pipette", "gripper", "hepauv"]
    serial: str = Field(min_length=1, max_length=64)
    mount: Literal["left", "right"] | None = None
    target_id: str | None = None
    port: int = 31950


class RobotBarcodeTargetsResponse(BaseModel):
    ip: str
    port: int
    http_connected: bool = False
    ssh_connected: bool = False
    simulating: bool = False
    targets: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class RobotFileWriteRequest(BaseModel):
    path: str
    content: str = ""
    create_if_missing: bool = True


class RobotFileListResponse(BaseModel):
    path: str
    entries: list[dict[str, Any]] = Field(default_factory=list)


class RobotFileContentResponse(BaseModel):
    path: str
    content: str


class RobotTestingDataSelectionRequest(BaseModel):
    paths: list[str] = Field(min_length=1, max_length=500)


class RobotActionResponse(BaseModel):
    success: bool = True
    message: str | None = None
    data: dict[str, Any] | None = None


class RobotProtocolListResponse(BaseModel):
    protocols: list[dict[str, Any]] = Field(default_factory=list)


class RobotRunListResponse(BaseModel):
    runs: list[dict[str, Any]] = Field(default_factory=list)


class RobotRunActionRequest(BaseModel):
    action_type: str
    port: int = 31950


class RobotRunCreateRequest(BaseModel):
    protocol_id: str
    port: int = 31950


class RobotProtocolAnalyzeRequest(BaseModel):
    body: dict[str, Any] | None = None
    port: int = 31950


class RobotLogDownloadDevice(BaseModel):
    ip: str
    name: str | None = None


class RobotLogDownloadRequest(BaseModel):
    devices: list[RobotLogDownloadDevice] = Field(min_length=1)
    folder_keys: list[str] = Field(min_length=1)
    concurrency: int = Field(default=4, ge=1, le=16)
