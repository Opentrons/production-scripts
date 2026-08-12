from __future__ import annotations

import asyncio

import core.config as setting
from core import sqlite_store
from modules.agent.knowledge.models import KnowledgeDocumentInput
from modules.agent.knowledge.service import KnowledgeService, PLATFORM_KNOWLEDGE
from modules.agent.tools.google_sheets import clear_sheet_range, create_spreadsheet
from modules.agent.tools import platform
from modules.agent.tools.registry import tool_registry
from modules.agent.tools.runtime import AgentTool
from modules.agent.tools.registry import ToolRegistry


def test_tool_registry_exposes_broad_platform_capabilities() -> None:
    names = {item["function"]["name"] for item in tool_registry.schemas}

    assert tool_registry.count >= 30
    assert {
        "read_sheet_range",
        "create_spreadsheet",
        "update_sheet_range",
        "query_platform_database",
        "aggregate_platform_database",
        "query_devices",
        "query_unit_tracker",
        "search_opentrons_official_docs",
        "read_opentrons_official_doc",
        "search_opentrons_source",
        "read_opentrons_source",
        "search_knowledge",
        "save_knowledge",
    } <= names


def test_google_sheet_mutations_require_confirmation_without_opening_google() -> None:
    assert create_spreadsheet("测试表格")["status"] == "confirmation_required"
    assert clear_sheet_range("1234567890abcdef", "Sheet1!A1:B2")["status"] == "confirmation_required"


def test_database_aggregate_can_analyze_more_than_query_page_limit(monkeypatch) -> None:
    class Collection:
        _store = object()

        def find(self, _filters):
            return [{"group": "all", "value": index} for index in range(500)]

    monkeypatch.setattr(platform, "_resolve_collection", lambda *_args: Collection())

    result = platform.aggregate_platform_database(
        dataset="upload_records",
        value_field="value",
        operation="sum",
        limit=500,
    )

    assert result["analyzed_records"] == 500
    assert result["groups"][0]["value"] == sum(range(500))


def test_tool_results_redact_sensitive_keys() -> None:
    registry = ToolRegistry(
        [AgentTool("secret_test", "test", {"type": "object", "properties": {}}, lambda: {"api_key": "secret", "value": 1})]
    )

    result = asyncio.run(registry.execute("secret_test", {}))

    assert result.as_dict()["data"] == {"api_key": "[已隐藏]", "value": 1}


def test_knowledge_service_uses_sqlite_and_supports_search_and_updates(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "platform.sqlite3"
    monkeypatch.setattr(setting, "use_sqlite_persistence", lambda: True)
    monkeypatch.setattr(setting, "resolve_sqlite_path", lambda *_args, **_kwargs: database_path)
    sqlite_store._STORE_CACHE.clear()
    service = KnowledgeService()

    assert service.count() == len(PLATFORM_KNOWLEDGE)
    search_result = service.search("Unit Tracker Google", limit=3)
    assert search_result["storage"] == "sqlite"
    assert search_result["documents"][0]["id"] == "platform-unit-tracker"

    saved = service.upsert(
        KnowledgeDocumentInput(
            title="P50M 排障经验",
            content="出现上传失败时先检查 CSV sheet 名称和条码。",
            category="troubleshooting",
            tags=["P50M", "上传失败"],
        )
    )
    assert service.search("P50M 上传失败")["documents"][0]["id"] == saved.id
    assert service.delete(saved.id) is True
    assert service.delete(saved.id) is False


def test_knowledge_service_seeds_opentrons_api_guidance(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "platform.sqlite3"
    monkeypatch.setattr(setting, "use_sqlite_persistence", lambda: True)
    monkeypatch.setattr(setting, "resolve_sqlite_path", lambda *_args, **_kwargs: database_path)
    sqlite_store._STORE_CACHE.clear()
    service = KnowledgeService()

    search_result = service.search("Robot Server HTTP API OpenAPI", category="opentrons", limit=3)

    assert search_result["documents"][0]["id"] == "opentrons-http-api"
    assert "docs.opentrons.com/http/api_reference.html" in search_result["documents"][0]["content"]
