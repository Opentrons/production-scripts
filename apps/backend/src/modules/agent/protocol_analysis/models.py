from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class OpentronsEnvironmentResponse(BaseModel):
    available: bool
    root: str | None = None
    python: str | None = None
    detail: str
    candidates: list[str] = Field(default_factory=list)
    versions: list[str] = Field(default_factory=list)
    default_version: str | None = None
    selected_version: str | None = None


class ProtocolAnalysisError(BaseModel):
    id: str | None = None
    errorType: str | None = None
    detail: str
    errorCode: str | None = None


class ProtocolAnalysisResponse(BaseModel):
    session_id: str
    protocol_name: str
    filenames: list[str]
    result: Literal["ok", "not-ok", "parameter-value-required", "error"] | str
    robot_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    run_time_parameters: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[ProtocolAnalysisError] = Field(default_factory=list)
    command_count: int = 0
    labware_count: int = 0
    pipette_count: int = 0
    module_count: int = 0
    liquid_count: int = 0
    analysis: dict[str, Any] = Field(default_factory=dict)
    opentrons_root: str | None = None
    opentrons_version: str | None = None
    stderr: str | None = None


class OddRemoteDevice(BaseModel):
    ip: str
    api_port: int = 31950
    name: str
    robot_model: str | None = None
    robot_type: str | None = None
    version: str | None = None
    service_status: str | None = None
    odd_devtools_port: int = 9223
    odd_available: bool = False
    odd_title: str | None = None
    odd_browser: str | None = None
    odd_detail: str | None = None
    odd_origin: str | None = None


class OddRemoteDeviceListResponse(BaseModel):
    devtools_port: int = 9223
    robot_api_port: int = 31950
    total: int = 0
    odd_ready_count: int = 0
    devices: list[OddRemoteDevice] = Field(default_factory=list)
    hint: str = ""


class OddRemoteSessionInfo(BaseModel):
    ip: str
    port: int
    origin: str
    browser: str | None = None
    protocol_version: str | None = None
    title: str | None = None
    url: str | None = None
    webSocketDebuggerUrl: str | None = None
    inspector_url: str | None = None
    width: float | None = None
    height: float | None = None


class OddRemoteMetrics(BaseModel):
    ip: str
    port: int
    width: float
    height: float
    title: str | None = None


class OddRemoteInputRequest(BaseModel):
    ip: str
    port: int = 9223
    type: str
    x: float
    y: float
    button: str = "left"
    clickCount: int = 1
    deltaX: float = 0
    deltaY: float = 0
    steps: int = 8


class OddRemoteInputResponse(BaseModel):
    ok: bool = True
    width: float | None = None
    height: float | None = None
    x: float | None = None
    y: float | None = None
