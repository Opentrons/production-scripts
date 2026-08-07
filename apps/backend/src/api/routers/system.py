from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from api.models import HealthResponse, MarkMessageReadResponse, MessageListResponse
from modules.system import health as health_service
from modules.system import messages as message_service


router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return await run_in_threadpool(health_service.get_health_status)


@router.get("/messages", response_model=MessageListResponse)
async def get_messages():
    return await run_in_threadpool(message_service.get_messages)


@router.put("/messages/read-all", response_model=MarkMessageReadResponse)
async def mark_all_messages_read():
    return await run_in_threadpool(message_service.mark_all_messages_read)


@router.put("/messages/{message_id}/read", response_model=MarkMessageReadResponse)
async def mark_message_read(message_id: str):
    return await run_in_threadpool(message_service.mark_message_read, message_id)
