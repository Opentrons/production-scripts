import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, WebSocket, status
from fastapi.responses import StreamingResponse
from starlette.websockets import WebSocketDisconnect

from modules.agent import attachment_store, download_store
from modules.agent.models import AgentChatRequest, AgentStatusResponse
from modules.agent.knowledge.models import KnowledgeDocument, KnowledgeDocumentInput, KnowledgeSearchResponse
from modules.agent.knowledge.service import knowledge_service
from modules.agent.protocol_analysis.models import (
    OddRemoteDeviceListResponse,
    OddRemoteInputRequest,
    OddRemoteInputResponse,
    OddRemoteMetrics,
    OddRemoteSessionInfo,
    OpentronsEnvironmentResponse,
    ProtocolAnalysisResponse,
)
from modules.agent.protocol_analysis.odd_remote import (
    ODD_DEVTOOLS_PORT,
    capture_odd_screenshot,
    list_odd_devices,
    odd_input,
    odd_metrics,
    odd_session_info,
    probe_odd_devtools,
)
from modules.agent.protocol_analysis.odd_stream import run_odd_stream
from modules.agent.protocol_analysis.service import ProtocolAnalysisErrorExc, protocol_analysis_service
from modules.agent.schedules.models import (
    AgentSchedule,
    AgentScheduleInput,
    AgentScheduleListResponse,
    AgentScheduleRun,
    AgentScheduleRunListResponse,
)
from modules.agent.schedules.service import agent_schedule_service
from modules.agent.service import ProductionAgentService, agent_service
from modules.auth.dependencies import ACCESS_COOKIE_NAME, get_auth_service, require_authenticated_user
from modules.auth.service import AuthenticationError
from modules.auth.store import AuthUser


router = APIRouter(prefix="/agent", tags=["agent"])
# WebSocket routes cannot sit under routers that inject HTTP Request dependencies
# (protected_router's require_platform_access), or Starlette returns 404 on upgrade.
odd_stream_router = APIRouter(prefix="/agent", tags=["agent"])

_TEXT_IMPORT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".log", ".tsv"}
_MAX_IMPORT_BYTES = 1_500_000


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


@router.post("/knowledge/import")
async def import_agent_knowledge(
    files: list[UploadFile] = File(...),
    category: str = Form(default="imported"),
    user: AuthUser = Depends(require_authenticated_user),
):
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个知识库文件")
    imported: list[KnowledgeDocument] = []
    errors: list[str] = []
    for upload in files[:20]:
        filename = (upload.filename or "knowledge.txt").strip()
        lower = filename.casefold()
        if not any(lower.endswith(ext) for ext in _TEXT_IMPORT_EXTENSIONS):
            errors.append(f"{filename}: 仅支持文本类文件")
            continue
        raw = await upload.read()
        if len(raw) > _MAX_IMPORT_BYTES:
            errors.append(f"{filename}: 超过大小限制")
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="ignore")
        content = text.strip()
        if not content:
            errors.append(f"{filename}: 内容为空")
            continue
        title = filename.rsplit(".", 1)[0][:200] or filename
        document = knowledge_service.upsert(
            KnowledgeDocumentInput(
                title=title,
                content=content[:30000],
                category=(category or "imported").strip() or "imported",
                tags=["imported"],
                source=f"import:{filename}",
                metadata={"imported_by": user.id, "filename": filename},
            )
        )
        imported.append(document)
    return {
        "imported": imported,
        "imported_count": len(imported),
        "errors": errors,
        "storage": knowledge_service.storage,
    }


@router.delete("/knowledge/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent_knowledge(document_id: str, confirm: bool = False):
    if not confirm:
        raise HTTPException(status_code=409, detail="删除知识文档需要 confirm=true")
    try:
        if not knowledge_service.delete(document_id):
            raise HTTPException(status_code=404, detail="知识文档不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/schedules", response_model=AgentScheduleListResponse)
def list_agent_schedules():
    return agent_schedule_service.list_schedules()


@router.post("/schedules", response_model=AgentSchedule, status_code=status.HTTP_201_CREATED)
def create_agent_schedule(
    payload: AgentScheduleInput,
    user: AuthUser = Depends(require_authenticated_user),
):
    return agent_schedule_service.create_schedule(payload, created_by=user.id)


@router.put("/schedules/{schedule_id}", response_model=AgentSchedule)
def update_agent_schedule(schedule_id: str, payload: AgentScheduleInput):
    try:
        return agent_schedule_service.update_schedule(schedule_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="定时任务不存在") from exc


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent_schedule(schedule_id: str):
    if not agent_schedule_service.delete_schedule(schedule_id):
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/schedule-runs", response_model=AgentScheduleRunListResponse)
def list_agent_schedule_runs(
    schedule_id: str = "",
    limit: int = Query(default=30, ge=1, le=100),
):
    return agent_schedule_service.list_runs(schedule_id or None, limit=limit)


@router.post("/schedules/{schedule_id}/run", response_model=AgentScheduleRun)
def run_agent_schedule_now(schedule_id: str):
    try:
        return agent_schedule_service.trigger_schedule(schedule_id, trigger="manual")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="定时任务不存在") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/attachments", status_code=status.HTTP_201_CREATED)
async def upload_agent_attachment(
    file: UploadFile = File(...),
    user: AuthUser = Depends(require_authenticated_user),
):
    try:
        return await attachment_store.save_attachment(file, user.id)
    except attachment_store.AttachmentTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except attachment_store.AttachmentUnsupportedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent_attachment(
    attachment_id: str,
    user: AuthUser = Depends(require_authenticated_user),
):
    try:
        attachment_store.delete_attachment(attachment_id, user.id)
    except attachment_store.AttachmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/downloads/testing-data/{request_id}")
async def download_agent_robot_testing_data(
    request_id: str,
    user: AuthUser = Depends(require_authenticated_user),
):
    from modules.robots import opentrons_control
    from modules.robots.files.ssh_client import OpentronsSshError

    try:
        request = download_store.resolve_robot_testing_data_request(request_id, user.id)
        filename, content, media_type = await asyncio.to_thread(
            opentrons_control.download_robot_testing_data,
            request["ip"],
            request["paths"],
        )
    except download_store.AgentDownloadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except OpentronsSshError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"SSH 测试数据下载失败: {exc}") from exc
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/chat/stream")
async def chat_stream(
    payload: AgentChatRequest,
    user: AuthUser = Depends(require_authenticated_user),
) -> StreamingResponse:
    if not agent_service.configured:
        raise HTTPException(status_code=503, detail="未配置 PRODUCTION_PLATFORM_LLM_API_KEY")
    try:
        attachments = attachment_store.validate_references(payload.attachments, user.id)
    except attachment_store.AttachmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    async def scoped_events() -> AsyncIterator[str]:
        token = attachment_store.set_attachment_scope(
            user.id,
            {attachment["id"] for attachment in attachments},
        )
        try:
            async for event in stream_agent_events(payload):
                yield event
        finally:
            attachment_store.reset_attachment_scope(token)

    return StreamingResponse(
        scoped_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/protocol-analysis/environment", response_model=OpentronsEnvironmentResponse)
async def get_protocol_analysis_environment(
    user: AuthUser = Depends(require_authenticated_user),
) -> OpentronsEnvironmentResponse:
    _ = user
    return await protocol_analysis_service.environment()


@router.get("/protocol-analysis/odd-devices", response_model=OddRemoteDeviceListResponse)
async def get_protocol_analysis_odd_devices(
    user: AuthUser = Depends(require_authenticated_user),
) -> OddRemoteDeviceListResponse:
    _ = user
    try:
        payload = await list_odd_devices()
        return OddRemoteDeviceListResponse.model_validate(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/protocol-analysis/odd-probe")
async def probe_protocol_analysis_odd(
    ip: str = Query(..., min_length=3),
    port: int = Query(default=ODD_DEVTOOLS_PORT, ge=1, le=65535),
    user: AuthUser = Depends(require_authenticated_user),
) -> dict:
    _ = user
    try:
        return await probe_odd_devtools(ip, port)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/protocol-analysis/odd-session", response_model=OddRemoteSessionInfo)
async def get_protocol_analysis_odd_session(
    ip: str = Query(..., min_length=3),
    port: int = Query(default=ODD_DEVTOOLS_PORT, ge=1, le=65535),
    user: AuthUser = Depends(require_authenticated_user),
) -> OddRemoteSessionInfo:
    _ = user
    try:
        payload = await odd_session_info(ip, port)
        return OddRemoteSessionInfo.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/protocol-analysis/odd-metrics", response_model=OddRemoteMetrics)
async def get_protocol_analysis_odd_metrics(
    ip: str = Query(..., min_length=3),
    port: int = Query(default=ODD_DEVTOOLS_PORT, ge=1, le=65535),
    user: AuthUser = Depends(require_authenticated_user),
) -> OddRemoteMetrics:
    _ = user
    try:
        payload = await odd_metrics(ip, port)
        return OddRemoteMetrics.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/protocol-analysis/odd-input", response_model=OddRemoteInputResponse)
async def post_protocol_analysis_odd_input(
    payload: OddRemoteInputRequest,
    user: AuthUser = Depends(require_authenticated_user),
) -> OddRemoteInputResponse:
    _ = user
    try:
        result = await odd_input(
            payload.ip,
            port=payload.port,
            event=payload.model_dump(),
        )
        return OddRemoteInputResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/protocol-analysis/odd-screenshot")
async def get_protocol_analysis_odd_screenshot(
    ip: str = Query(..., min_length=3),
    port: int = Query(default=ODD_DEVTOOLS_PORT, ge=1, le=65535),
    quality: int = Query(default=55, ge=20, le=90),
    user: AuthUser = Depends(require_authenticated_user),
) -> Response:
    _ = user
    try:
        data = await capture_odd_screenshot(ip, port=port, quality=quality)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "X-ODD-Devtools-Port": str(port),
        },
    )


@odd_stream_router.websocket("/protocol-analysis/odd-stream")
async def protocol_analysis_odd_stream(
    websocket: WebSocket,
    ip: str = Query(..., min_length=3),
    port: int = Query(default=ODD_DEVTOOLS_PORT, ge=1, le=65535),
    quality: int = Query(default=45, ge=20, le=80),
) -> None:
    token = (websocket.cookies.get(ACCESS_COOKIE_NAME) or "").strip()
    if not token:
        authorization = websocket.headers.get("Authorization", "")
        scheme, _, bearer = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = bearer.strip()
    if not token:
        await websocket.close(code=4401)
        return
    try:
        get_auth_service().verify_access_token(token)
    except AuthenticationError:
        await websocket.close(code=4401)
        return
    except Exception:
        await websocket.close(code=1011)
        return

    await websocket.accept()
    try:
        await run_odd_stream(websocket, ip=ip, port=port, quality=quality)
    except WebSocketDisconnect:
        return
    except ValueError as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
        await websocket.close(code=1008)
    except Exception as exc:  # noqa: BLE001
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
        await websocket.close(code=1011)


@router.post("/protocol-analysis/analyze", response_model=ProtocolAnalysisResponse)
async def analyze_protocol(
    protocol_files: list[UploadFile] = File(...),
    labware_files: list[UploadFile] | None = File(default=None),
    rtp_values: str = Form(default="{}"),
    opentrons_version: str = Form(default=""),
    csv_variable_names: list[str] | None = Form(default=None),
    csv_files: list[UploadFile] | None = File(default=None),
    user: AuthUser = Depends(require_authenticated_user),
) -> ProtocolAnalysisResponse:
    _ = user
    try:
        return await protocol_analysis_service.analyze(
            protocol_files=protocol_files,
            labware_files=labware_files or [],
            rtp_values_json=rtp_values,
            csv_variable_names=csv_variable_names or [],
            csv_files=csv_files or [],
            opentrons_version=opentrons_version,
        )
    except ProtocolAnalysisErrorExc as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
