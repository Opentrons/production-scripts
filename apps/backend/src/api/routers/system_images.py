from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from modules.robots import system_images as service

router = APIRouter(prefix="/robots/system-images", tags=["system-images"])


class InstallRequest(BaseModel):
    ips: list[str] = Field(min_length=1, max_length=100)
    image: str = Field(min_length=1, max_length=200)
    port: int = Field(default=31950, ge=1, le=65535)


class DownloadRequest(BaseModel):
    url: str = Field(min_length=1, max_length=8192)


async def _call(function, *args):
    try:
        return await run_in_threadpool(function, *args)
    except FileNotFoundError as exc:
        raise HTTPException(404, detail={"message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(400, detail={"message": str(exc)}) from exc
    except OSError as exc:
        raise HTTPException(503, detail={"message": "镜像目录或任务存储不可用"}) from exc


@router.get("")
async def list_images():
    return await _call(service.list_images)


@router.get("/tasks")
async def list_tasks():
    return {"tasks": await _call(service.list_tasks)}


@router.post("/install", status_code=202)
async def install(request: InstallRequest):
    return {"tasks": await _call(service.create_install_tasks, request.ips, request.image, request.port)}


@router.post("/download", status_code=202)
async def download(request: DownloadRequest):
    return await _call(service.create_download_task, request.url)
