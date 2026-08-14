from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

import core.config as setting
from api.models import (
    RobotActionResponse,
    RobotProtocolAnalyzeRequest,
    RobotProtocolListResponse,
    RobotRunActionRequest,
    RobotRunCreateRequest,
    RobotRunListResponse,
)
from modules.robots import opentrons_protocols as opentrons_protocols_service


router = APIRouter()

@router.get("/robots/{ip}/protocols", response_model=RobotProtocolListResponse)
async def list_robot_protocols(ip: str, port: int = setting.ROBOT_HEALTH_PORT):
    protocols = await run_in_threadpool(opentrons_protocols_service.list_protocols, ip, port)
    return RobotProtocolListResponse(protocols=protocols)


@router.get("/robots/{ip}/protocols/{protocol_id}/download")
async def download_robot_protocol(
    ip: str,
    protocol_id: str,
    format: str = Query("json", pattern="^(json|source)$"),
    port: int = setting.ROBOT_HEALTH_PORT,
):
    if format == "source":
        filename, content, media_type = await run_in_threadpool(
            opentrons_protocols_service.download_protocol_source,
            ip,
            protocol_id,
        )
    else:
        filename, content = await run_in_threadpool(
            opentrons_protocols_service.download_protocol_bundle,
            ip,
            protocol_id,
            port,
        )
        media_type = "application/json"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/robots/{ip}/protocols/upload", response_model=RobotActionResponse)
async def upload_robot_protocol(
    ip: str,
    files: list[UploadFile] = File(...),
    key: str | None = Form(None),
    protocol_kind: str | None = Form(None),
    port: int = setting.ROBOT_HEALTH_PORT,
):
    file_payloads: list[tuple[str, bytes]] = []
    for upload in files:
        content = await upload.read()
        file_payloads.append((upload.filename or "protocol.py", content))
    data = await run_in_threadpool(
        opentrons_protocols_service.upload_protocol,
        ip,
        file_payloads,
        key=key,
        protocol_kind=protocol_kind,
        port=port,
    )
    return RobotActionResponse(success=True, message="Protocol uploaded", data=data)


@router.post("/robots/{ip}/protocols/{protocol_id}/analyze", response_model=RobotActionResponse)
async def analyze_robot_protocol(ip: str, protocol_id: str, request: RobotProtocolAnalyzeRequest):
    analyses = await run_in_threadpool(
        opentrons_protocols_service.analyze_protocol,
        ip,
        protocol_id,
        body=request.body,
        port=request.port,
    )
    return RobotActionResponse(success=True, message="Analysis started", data={"analyses": analyses})


@router.get("/robots/{ip}/protocols/{protocol_id}/analyses", response_model=RobotActionResponse)
async def get_robot_protocol_analyses(ip: str, protocol_id: str, port: int = setting.ROBOT_HEALTH_PORT):
    analyses = await run_in_threadpool(
        opentrons_protocols_service.list_protocol_analyses,
        ip,
        protocol_id,
        port,
    )
    return RobotActionResponse(success=True, data={"analyses": analyses})


@router.get("/robots/{ip}/data-files", response_model=RobotActionResponse)
async def list_robot_data_files(ip: str, port: int = setting.ROBOT_HEALTH_PORT):
    files = await run_in_threadpool(opentrons_protocols_service.list_data_files, ip, port)
    return RobotActionResponse(success=True, data={"files": files})


@router.get("/robots/{ip}/protocols/{protocol_id}/data-files", response_model=RobotActionResponse)
async def list_robot_protocol_data_files(
    ip: str,
    protocol_id: str,
    port: int = setting.ROBOT_HEALTH_PORT,
):
    files = await run_in_threadpool(
        opentrons_protocols_service.list_protocol_data_files,
        ip,
        protocol_id,
        port,
    )
    return RobotActionResponse(success=True, data={"files": files})


@router.post("/robots/{ip}/data-files/upload", response_model=RobotActionResponse)
async def upload_robot_data_file(
    ip: str,
    file: UploadFile = File(...),
    port: int = setting.ROBOT_HEALTH_PORT,
):
    filename = file.filename or "data.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files are supported for dataFiles upload",
        )
    content = await file.read()
    data = await run_in_threadpool(
        opentrons_protocols_service.upload_data_file,
        ip,
        filename,
        content,
        port=port,
    )
    return RobotActionResponse(success=True, message="CSV uploaded", data=data)


@router.get("/robots/{ip}/runs", response_model=RobotRunListResponse)
async def list_robot_runs(ip: str, port: int = setting.ROBOT_HEALTH_PORT):
    runs = await run_in_threadpool(opentrons_protocols_service.list_runs, ip, port)
    return RobotRunListResponse(runs=runs)


@router.post("/robots/{ip}/runs", response_model=RobotActionResponse)
async def create_robot_run(ip: str, request: RobotRunCreateRequest):
    result = await run_in_threadpool(
        opentrons_protocols_service.create_and_play_run,
        ip,
        request.protocol_id,
        request.port,
    )
    return RobotActionResponse(success=True, message="Run created and started", data=result)


@router.post("/robots/{ip}/runs/{run_id}/actions", response_model=RobotActionResponse)
async def control_robot_run(ip: str, run_id: str, request: RobotRunActionRequest):
    action = await run_in_threadpool(
        opentrons_protocols_service.run_control_action,
        ip,
        run_id,
        request.action_type,
        request.port,
    )
    return RobotActionResponse(success=True, message="Run action sent", data=action)
