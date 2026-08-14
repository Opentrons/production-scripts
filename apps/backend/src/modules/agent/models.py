from typing import Literal

from pydantic import BaseModel, Field


class AgentAttachmentReference(BaseModel):
    id: str = Field(pattern=r"^[0-9a-f]{32}$")
    name: str = Field(min_length=1, max_length=255)
    size: int = Field(ge=0, le=5 * 1024 * 1024)


class AgentChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=100000)


class AgentChatRequest(BaseModel):
    messages: list[AgentChatMessage] = Field(min_length=1, max_length=30)
    context: str = Field(default="", max_length=12000)
    attachments: list[AgentAttachmentReference] = Field(default_factory=list, max_length=150)


class AgentStatusResponse(BaseModel):
    configured: bool
    model: str
    tool_count: int = 0
    knowledge_count: int = 0
    max_tool_rounds: int = 0
