import asyncio
import json

from modules.agent.models import AgentChatMessage, AgentChatRequest
from modules.agent.routes import stream_agent_events
from modules.agent.service import ProductionAgentService


class FakeLLM:
    configured = True
    model = "test-model"

    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []
        self.system_prompt = ""

    async def stream_chat(self, messages, *, system_prompt):
        self.messages = messages
        self.system_prompt = system_prompt
        yield "生产"
        yield "建议"


def build_request() -> AgentChatRequest:
    return AgentChatRequest(
        messages=[AgentChatMessage(role="user", content="如何排查上传失败？")],
        context="当前页面：上传记录",
    )


def test_agent_delegates_conversation_and_context_to_llm() -> None:
    llm = FakeLLM()
    service = ProductionAgentService(llm)  # type: ignore[arg-type]

    async def collect() -> list[str]:
        return [chunk async for chunk in service.stream_chat(build_request())]

    chunks = asyncio.run(collect())

    assert chunks == ["生产", "建议"]
    assert llm.messages == [{"role": "user", "content": "如何排查上传失败？"}]
    assert "Opentrons 生产平台" in llm.system_prompt
    assert "当前页面：上传记录" in llm.system_prompt


def test_agent_sse_stream_emits_chunks_and_done_event() -> None:
    service = ProductionAgentService(FakeLLM())  # type: ignore[arg-type]

    async def collect() -> list[dict[str, str]]:
        events = []
        async for event in stream_agent_events(build_request(), service):
            events.append(json.loads(event.removeprefix("data: ").strip()))
        return events

    events = asyncio.run(collect())

    assert events == [
        {"type": "chunk", "content": "生产"},
        {"type": "chunk", "content": "建议"},
        {"type": "done", "content": "生产建议"},
    ]
