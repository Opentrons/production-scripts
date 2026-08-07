from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from api.models import (
    RobotActionResponse,
    RobotFileContentResponse,
    RobotFileListResponse,
    RobotFileWriteRequest,
    RobotTestingDataSelectionRequest,
)
from core.logging import get_logger
from modules.robots import opentrons_control as opentrons_control_service
from modules.robots.files.ssh_client import OpentronsSshError


logger = get_logger(__name__)
router = APIRouter()

@router.get("/robots/{ip}/files", response_model=RobotFileListResponse)
async def list_robot_files(ip: str, path: str = "/"):
    try:
        return await run_in_threadpool(opentrons_control_service.list_robot_files, ip, path)
    except OpentronsSshError as exc:
        logger.warning("SSH file list failed for robot %s path %s: %s", ip, path, exc)
        raise HTTPException(status_code=502, detail={"message": f"SSH 目录读取失败: {exc}"}) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"message": f"目录不存在: {path}"}) from exc


@router.get("/robots/{ip}/files/content", response_model=RobotFileContentResponse)
async def read_robot_file(ip: str, path: str):
    try:
        return await run_in_threadpool(opentrons_control_service.read_robot_file, ip, path)
    except OpentronsSshError as exc:
        raise HTTPException(status_code=502, detail={"message": f"SSH 文件读取失败: {exc}"}) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"message": f"文件不存在: {path}"}) from exc


@router.put("/robots/{ip}/files/content", response_model=RobotActionResponse)
async def write_robot_file(ip: str, request: RobotFileWriteRequest):
    data = await run_in_threadpool(
        opentrons_control_service.write_robot_file,
        ip,
        request.path,
        request.content,
        create_if_missing=request.create_if_missing,
    )
    message = "File saved" if data.get("success") else "File skipped"
    return RobotActionResponse(success=bool(data.get("success")), message=message, data=data)


@router.post("/robots/{ip}/files/upload", response_model=RobotActionResponse)
async def upload_robot_file(
    ip: str,
    path: str = Form(...),
    file: UploadFile = File(...),
):
    content = await file.read()
    data = await run_in_threadpool(opentrons_control_service.upload_robot_file, ip, path, content)
    return RobotActionResponse(success=True, message="File uploaded", data=data)


@router.delete("/robots/{ip}/files", response_model=RobotActionResponse)
async def delete_robot_file(ip: str, path: str):
    await run_in_threadpool(opentrons_control_service.delete_robot_file, ip, path)
    return RobotActionResponse(success=True, message="Deleted")


@router.get("/robots/{ip}/files/download")
async def download_robot_file(ip: str, path: str):
    try:
        filename, content, media_type = await run_in_threadpool(
            opentrons_control_service.download_robot_file,
            ip,
            path,
        )
    except OpentronsSshError as exc:
        raise HTTPException(status_code=502, detail={"message": f"SSH 文件下载失败: {exc}"}) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"message": f"文件不存在: {path}"}) from exc
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/robots/{ip}/testing-data", response_model=RobotFileListResponse)
async def list_robot_testing_data(ip: str, path: str | None = None):
    try:
        return await run_in_threadpool(opentrons_control_service.list_robot_testing_data, ip, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    except OpentronsSshError as exc:
        logger.warning("SSH testing data list failed for robot %s path %s: %s", ip, path, exc)
        raise HTTPException(status_code=502, detail={"message": f"SSH 测试数据读取失败: {exc}"}) from exc


@router.post("/robots/{ip}/testing-data/download")
async def download_robot_testing_data(ip: str, request: RobotTestingDataSelectionRequest):
    try:
        filename, content, media_type = await run_in_threadpool(
            opentrons_control_service.download_robot_testing_data,
            ip,
            request.paths,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    except OpentronsSshError as exc:
        raise HTTPException(status_code=502, detail={"message": f"SSH 测试数据下载失败: {exc}"}) from exc
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/robots/{ip}/testing-data", response_model=RobotActionResponse)
async def delete_robot_testing_data(ip: str, request: RobotTestingDataSelectionRequest):
    try:
        data = await run_in_threadpool(
            opentrons_control_service.delete_robot_testing_data,
            ip,
            request.paths,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    except OpentronsSshError as exc:
        raise HTTPException(status_code=502, detail={"message": f"SSH 测试数据删除失败: {exc}"}) from exc
    return RobotActionResponse(success=True, message="Deleted", data=data)
