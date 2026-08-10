from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from api.models import HealthResponse, MarkMessageReadResponse, MessageListResponse
from modules.system import health as health_service
from modules.system import messages as message_service
from modules.system import simulating as simulating_service


router = APIRouter()


class SimulatingStatusResponse(BaseModel):
    simulating: bool
    persistence: str
    db_root: str
    active_db_dir: str
    business_db_dir: str
    simulating_db_dir: str
    platform_db_path: str


class SimulatingUpdateRequest(BaseModel):
    simulating: bool = Field(description="启用后 Mongo 业务默认改走 SQLite")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return await run_in_threadpool(health_service.get_health_status)


@router.get("/system/simulating", response_model=SimulatingStatusResponse)
async def get_simulating_status():
    return await run_in_threadpool(simulating_service.get_status)


@router.put("/system/simulating", response_model=SimulatingStatusResponse)
async def update_simulating_status(request: SimulatingUpdateRequest):
    return await run_in_threadpool(simulating_service.set_enabled, request.simulating)


@router.get("/messages", response_model=MessageListResponse)
async def get_messages():
    return await run_in_threadpool(message_service.get_messages)


@router.put("/messages/read-all", response_model=MarkMessageReadResponse)
async def mark_all_messages_read():
    return await run_in_threadpool(message_service.mark_all_messages_read)


@router.put("/messages/{message_id}/read", response_model=MarkMessageReadResponse)
async def mark_message_read(message_id: str):
    return await run_in_threadpool(message_service.mark_message_read, message_id)
