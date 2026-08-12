from __future__ import annotations

from typing import Any

from modules.agent.knowledge.models import KnowledgeDocumentInput
from modules.agent.knowledge.service import knowledge_service


def search_knowledge(query: str, category: str = "", limit: int = 8) -> dict[str, Any]:
    return knowledge_service.search(query, category=category or None, limit=limit)


def list_knowledge(category: str = "", limit: int = 30) -> dict[str, Any]:
    return knowledge_service.list_documents(category=category or None, limit=limit)


def save_knowledge(
    title: str,
    content: str,
    category: str = "general",
    tags: list[str] | None = None,
    source: str = "agent",
    document_id: str = "",
    confirm: bool = False,
) -> dict[str, Any]:
    if not confirm:
        return {
            "status": "confirmation_required",
            "action": f"保存知识文档《{str(title).strip()}》",
            "message": "请向用户确认知识内容准确且允许持久化，然后将 confirm 设为 true 再执行。",
        }
    document = knowledge_service.upsert(
        KnowledgeDocumentInput(
            title=title,
            content=content,
            category=category,
            tags=tags or [],
            source=source,
        ),
        document_id=document_id or None,
    )
    return {"status": "saved", "document": document.model_dump(mode="json")}


def delete_knowledge(document_id: str, confirm: bool = False) -> dict[str, Any]:
    if not confirm:
        return {
            "status": "confirmation_required",
            "action": f"删除知识文档 {document_id}",
            "message": "请向用户确认删除对象和影响，然后将 confirm 设为 true 再执行。",
        }
    return {"status": "deleted" if knowledge_service.delete(document_id) else "not_found", "document_id": document_id}
