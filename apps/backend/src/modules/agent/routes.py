import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from modules.agent.models import AgentChatRequest, AgentStatusResponse
from modules.agent.knowledge.models import KnowledgeDocument, KnowledgeDocumentInput, KnowledgeSearchResponse
from modules.agent.knowledge.service import knowledge_service
from modules.agent.service import ProductionAgentService, agent_service


router = APIRouter(prefix="/agent", tags=["agent"])


def _sse_event(event_type: str, content: str = "", data: dict | None = None) -> str:
    payload_data = {"type": event_type, "content": content}
    if data is not None:
        payload_data["data"] = data
    payload = json.dumps(payload_data, ensure_ascii=False)
    return f"data: {payload}\n\n"


async def stream_agent_events(
    payload: AgentChatRequest,
    service: ProductionAgentService = agent_service,
) -> AsyncIterator[str]:
    response_parts: list[str] = []
    try:
        async for event in service.stream_events(payload):
            if event.type == "chunk":
                response_parts.append(event.content)
            yield _sse_event(event.type, event.content, event.data)
        yield _sse_event("done", "".join(response_parts))
    except RuntimeError as exc:
        yield _sse_event("error", str(exc))


@router.get("/status", response_model=AgentStatusResponse)
def get_agent_status() -> AgentStatusResponse:
    return AgentStatusResponse(
        configured=agent_service.configured,
        model=agent_service.model,
        tool_count=agent_service.tool_count,
        knowledge_count=agent_service.knowledge_count,
        max_tool_rounds=agent_service.max_tool_rounds,
    )


@router.get("/tools")
def list_agent_tools() -> dict:
    return {"tools": agent_service.tools.describe(), "total": agent_service.tool_count}


@router.get("/knowledge", response_model=KnowledgeSearchResponse)
def search_agent_knowledge(
    query: str = "",
    category: str = "",
    limit: int = Query(default=30, ge=1, le=200),
):
    if query.strip():
        return knowledge_service.search(query, category=category or None, limit=limit)
    return knowledge_service.list_documents(category=category or None, limit=limit)


@router.post("/knowledge", response_model=KnowledgeDocument, status_code=status.HTTP_201_CREATED)
def save_agent_knowledge(payload: KnowledgeDocumentInput, document_id: str = ""):
    return knowledge_service.upsert(payload, document_id=document_id or None)


@router.delete("/knowledge/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent_knowledge(document_id: str, confirm: bool = False):
    if not confirm:
        raise HTTPException(status_code=409, detail="删除知识文档需要 confirm=true")
    if not knowledge_service.delete(document_id):
        raise HTTPException(status_code=404, detail="知识文档不存在")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
