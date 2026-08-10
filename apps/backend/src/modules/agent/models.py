from typing import Literal

from pydantic import BaseModel, Field


class AgentChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20000)


class AgentChatRequest(BaseModel):
    messages: list[AgentChatMessage] = Field(min_length=1, max_length=30)
    context: str = Field(default="", max_length=12000)


class AgentStatusResponse(BaseModel):
    configured: bool
    model: str
