import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from modules.agent.models import AgentChatRequest, AgentStatusResponse
from modules.agent.service import ProductionAgentService, agent_service


router = APIRouter(prefix="/agent", tags=["agent"])


def _sse_event(event_type: str, content: str = "") -> str:
    payload = json.dumps({"type": event_type, "content": content}, ensure_ascii=False)
    return f"data: {payload}\n\n"


async def stream_agent_events(
    payload: AgentChatRequest,
    service: ProductionAgentService = agent_service,
) -> AsyncIterator[str]:
    response_parts: list[str] = []
    try:
        async for chunk in service.stream_chat(payload):
            response_parts.append(chunk)
            yield _sse_event("chunk", chunk)
        yield _sse_event("done", "".join(response_parts))
    except RuntimeError as exc:
        yield _sse_event("error", str(exc))


@router.get("/status", response_model=AgentStatusResponse)
def get_agent_status() -> AgentStatusResponse:
    return AgentStatusResponse(configured=agent_service.configured, model=agent_service.model)


@router.post("/chat/stream")
async def chat_stream(payload: AgentChatRequest) -> StreamingResponse:
    if not agent_service.configured:
        raise HTTPException(status_code=503, detail="未配置 PRODUCTION_PLATFORM_LLM_API_KEY")
    return StreamingResponse(
        stream_agent_events(payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
