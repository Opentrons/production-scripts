from __future__ import annotations

import asyncio
import inspect
import json
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable


SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:password|passwd|secret|token|api[_-]?key|authorization|cookie|private[_-]?key)",
    re.IGNORECASE,
)


def sanitize_tool_data(value: Any, *, depth: int = 0) -> Any:
    if depth > 8:
        return "[内容层级过深，已截断]"
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {
            str(key): "[已隐藏]" if SENSITIVE_KEY_PATTERN.search(str(key)) else sanitize_tool_data(item, depth=depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [sanitize_tool_data(item, depth=depth + 1) for item in list(value)[:500]]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return f"[二进制数据 {len(value)} bytes]"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    category: str = "platform"
    mutating: bool = False

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolExecutionResult:
    tool: str
    ok: bool
    data: Any = None
    error: str | None = None
    duration_ms: int = 0

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "ok": self.ok,
            "tool": self.tool,
            "duration_ms": self.duration_ms,
        }
        if self.ok:
            payload["data"] = sanitize_tool_data(self.data)
        else:
            payload["error"] = self.error or "工具执行失败"
        return payload

    def for_model(self, max_chars: int = 24000) -> str:
        text = json.dumps(self.as_dict(), ensure_ascii=False, default=str)
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + f"... [工具结果已截断，原长度 {len(text)} 字符]"


async def execute_handler(tool: AgentTool, arguments: dict[str, Any]) -> ToolExecutionResult:
    started = time.perf_counter()
    try:
        if inspect.iscoroutinefunction(tool.handler):
            data = await tool.handler(**arguments)
        else:
            data = await asyncio.to_thread(tool.handler, **arguments)
            if inspect.isawaitable(data):
                data = await data
        return ToolExecutionResult(
            tool=tool.name,
            ok=True,
            data=data,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
    except Exception as exc:
        return ToolExecutionResult(
            tool=tool.name,
            ok=False,
            error=str(exc),
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
