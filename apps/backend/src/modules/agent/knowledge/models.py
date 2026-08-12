from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class KnowledgeDocumentInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=30000)
    category: str = Field(default="general", max_length=80)
    tags: list[str] = Field(default_factory=list, max_length=30)
    source: str = Field(default="manual", max_length=300)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocument(KnowledgeDocumentInput):
    id: str
    created_at: str
    updated_at: str


class KnowledgeSearchResponse(BaseModel):
    documents: list[KnowledgeDocument] = Field(default_factory=list)
    total: int = 0
    storage: str
