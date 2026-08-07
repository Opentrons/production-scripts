from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from api.models import (
    FileResourceDeleteResponse,
    FileResourceProjectsResponse,
    FileResourceVersionResponse,
    FileResourceVersionUpdateRequest,
)
from core.logging import get_logger
from modules.resources import file_resources as file_resource_service


logger = get_logger(__name__)
router = APIRouter()

@router.get("/file-resources/projects", response_model=FileResourceProjectsResponse)
async def list_file_resource_projects():
    try:
        return await run_in_threadpool(file_resource_service.list_projects)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/file-resources/versions", response_model=FileResourceVersionResponse)
async def create_file_resource_version(
    project_id: str | None = Form(None),
    project_name: str = Form(""),
    project_description: str = Form(""),
    version: str = Form(...),
    version_notes: str = Form(""),
    file: UploadFile = File(...),
):
    try:
        created_version = await file_resource_service.create_version(
            project_id=project_id,
            project_name=project_name,
            project_description=project_description,
            version=version,
            version_notes=version_notes,
            upload=file,
        )
        return {"success": True, "version": created_version}
    except file_resource_service.FileResourceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except file_resource_service.FileResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("File resource upload failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="文件上传失败") from exc


@router.put("/file-resources/versions/{version_id}", response_model=FileResourceVersionResponse)
async def update_file_resource_version(version_id: str, request: FileResourceVersionUpdateRequest):
    try:
        updates = request.model_dump(exclude_unset=True) if hasattr(request, "model_dump") else request.dict(exclude_unset=True)
        version = await run_in_threadpool(file_resource_service.update_version, version_id, updates)
        return {"success": True, "version": version}
    except file_resource_service.FileResourceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except file_resource_service.FileResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/file-resources/versions/{version_id}/download")
async def download_file_resource_version(version_id: str):
    try:
        file_path, filename, content_type = await run_in_threadpool(
            file_resource_service.resolve_download,
            version_id,
        )
        return FileResponse(file_path, media_type=content_type, filename=filename)
    except file_resource_service.FileResourceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except file_resource_service.FileResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/file-resources/versions/{version_id}", response_model=FileResourceDeleteResponse)
async def delete_file_resource_version(version_id: str):
    try:
        return await run_in_threadpool(file_resource_service.delete_version, version_id)
    except file_resource_service.FileResourceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except file_resource_service.FileResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
