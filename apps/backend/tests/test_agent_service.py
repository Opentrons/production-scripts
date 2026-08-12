import asyncio
import json

from modules.agent.models import AgentChatMessage, AgentChatRequest
from modules.agent.routes import stream_agent_events
from modules.agent.service import ProductionAgentService
from modules.agent.tools.runtime import AgentTool
from modules.agent.tools.registry import ToolRegistry


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
    assert "Python Protocol API 与 Robot Server HTTP API" in llm.system_prompt
    assert "源码相对路径、行号和 Git revision" in llm.system_prompt
    assert "用户最新一条真实输入的主要自然语言" in llm.system_prompt
    assert "工具证据使用中文而切换回答语言" in llm.system_prompt


def test_agent_prompt_follows_latest_real_user_message_language() -> None:
    llm = FakeLLM()
    service = ProductionAgentService(llm)  # type: ignore[arg-type]
    request = AgentChatRequest(
        messages=[
            AgentChatMessage(role="user", content="请检查设备状态"),
            AgentChatMessage(role="assistant", content="请提供设备地址。"),
            AgentChatMessage(role="user", content="Please check 192.168.6.36 and answer in English."),
        ],
        context="当前页面：设备管理",
    )

    async def collect() -> list[str]:
        return [chunk async for chunk in service.stream_chat(request)]

    asyncio.run(collect())

    assert "英文输入用英文" in llm.system_prompt
    assert "用户明确指定回答语言时以其指定为准" in llm.system_prompt


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


def test_agent_loops_through_tools_before_final_answer() -> None:
    class ToolLLM:
        configured = True
        model = "tool-model"

        def __init__(self) -> None:
            self.round = 0
            self.received_messages = []

        async def stream_tool_round(self, messages, *, system_prompt, tools):
            self.received_messages = messages
            self.round += 1
            if self.round == 1:
                yield {"type": "chunk", "content": "我先查询内部数据。"}
                yield {
                    "type": "round_done",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {"name": "lookup", "arguments": '{"barcode":"FLX1"}'},
                            }
                        ],
                    },
                }
                return
            yield {"type": "chunk", "content": "查询完成"}
            yield {"type": "round_done", "message": {"role": "assistant", "content": "查询完成"}}

    registry = ToolRegistry(
        [
            AgentTool(
                name="lookup",
                description="lookup",
                parameters={"type": "object", "properties": {}},
                handler=lambda barcode: {"barcode": barcode, "status": "success"},
            )
        ]
    )
    llm = ToolLLM()
    service = ProductionAgentService(llm, tools=registry, max_tool_rounds=4)  # type: ignore[arg-type]

    async def collect():
        return [event async for event in service.stream_events(build_request())]

    events = asyncio.run(collect())

    assert [event.type for event in events] == ["tool_start", "tool_result", "chunk"]
    assert events[1].data == {
        "call_id": "call-1",
        "name": "lookup",
        "ok": True,
        "duration_ms": events[1].data["duration_ms"],
    }
    assert llm.received_messages[-1]["role"] == "tool"
    assert '"status": "success"' in llm.received_messages[-1]["content"]


def test_agent_uses_clean_evidence_context_for_forced_final_answer() -> None:
    class BudgetLLM:
        configured = True
        model = "tool-model"

        def __init__(self) -> None:
            self.round = 0
            self.final_messages = []
            self.final_prompt = ""

        async def stream_tool_round(self, messages, *, system_prompt, tools):
            self.round += 1
            if tools:
                yield {
                    "type": "round_done",
                    "message": {
                        "role": "assistant",
                        "content": "准备查询",
                        "tool_calls": [
                            {
                                "id": f"call-{self.round}",
                                "type": "function",
                                "function": {"name": "lookup", "arguments": "{}"},
                            }
                        ],
                    },
                }
                return
            self.final_messages = messages
            self.final_prompt = system_prompt
            yield {"type": "chunk", "content": "数据源不可用。"}
            yield {
                "type": "chunk",
                "content": '<｜｜DSML｜｜tool_calls><｜｜DSML｜｜invoke name="lookup"></｜｜DSML｜｜invoke></｜｜DSML｜｜tool_calls>',
            }
            yield {"type": "round_done", "message": {"role": "assistant", "content": "ignored"}}

    llm = BudgetLLM()
    service = ProductionAgentService(
        llm,  # type: ignore[arg-type]
        tools=ToolRegistry([AgentTool("lookup", "lookup", {"type": "object", "properties": {}}, lambda: {"status": "offline"})]),
        max_tool_rounds=2,
    )

    async def collect():
        return [event async for event in service.stream_events(build_request())]

    events = asyncio.run(collect())
    answer = "".join(event.content for event in events if event.type == "chunk")

    assert answer == "数据源不可用。"
    assert all(message.get("role") != "tool" for message in llm.final_messages)
    assert "工具 lookup" in llm.final_messages[-1]["content"]
    assert "不得继续调用工具" in llm.final_prompt
    assert "用户最新一条真实输入所使用的语言" in llm.final_prompt


def test_agent_blocks_repeated_identical_tool_calls() -> None:
    calls = 0

    class RepeatingLLM:
        configured = True
        model = "tool-model"

        def __init__(self) -> None:
            self.round = 0
            self.messages = []

        async def stream_tool_round(self, messages, *, system_prompt, tools):
            self.messages = messages
            self.round += 1
            if self.round <= 3:
                yield {
                    "type": "round_done",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{"id": f"call-{self.round}", "type": "function", "function": {"name": "repeat", "arguments": "{}"}}],
                    },
                }
            else:
                yield {"type": "chunk", "content": "已停止重复查询"}
                yield {"type": "round_done", "message": {"role": "assistant", "content": "已停止重复查询"}}

    def handler():
        nonlocal calls
        calls += 1
        return {"value": calls}

    service = ProductionAgentService(
        RepeatingLLM(),  # type: ignore[arg-type]
        tools=ToolRegistry([AgentTool("repeat", "repeat", {"type": "object", "properties": {}}, handler)]),
        max_tool_rounds=5,
    )

    async def collect():
        return [event async for event in service.stream_events(build_request())]

    events = asyncio.run(collect())

    assert calls == 2
    assert any(event.type == "tool_result" and event.data and event.data.get("error") == "重复调用已阻止" for event in events)
