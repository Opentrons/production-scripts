from __future__ import annotations

from pathlib import Path

import pytest

from modules.agent.tools import opentrons


def _build_source_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "opentrons"
    protocol_file = root / "api/src/opentrons/protocol_api/protocol_context.py"
    protocol_file.parent.mkdir(parents=True)
    protocol_file.write_text(
        "from typing import Any\n\nclass ProtocolContext:\n    pass\n",
        encoding="utf-8",
    )
    http_router = root / "robot-server/robot_server/health/router.py"
    http_router.parent.mkdir(parents=True)
    http_router.write_text('@router.get("/health")\nasync def get_health():\n    return {"ok": True}\n', encoding="utf-8")
    (root / "docs").mkdir()
    monkeypatch.setenv(opentrons.SOURCE_ROOTS_ENV, str(root))
    monkeypatch.setattr(opentrons, "_repo_revision", lambda _root: "abc123")
    return root


def test_opentrons_status_and_source_search_include_revision_and_line(tmp_path, monkeypatch) -> None:
    root = _build_source_repo(tmp_path, monkeypatch)

    status = opentrons.get_opentrons_knowledge_status()
    result = opentrons.search_opentrons_source("class ProtocolContext", scope="protocol_api", limit=5)

    assert status["source_available"] is True
    assert status["source_roots"][0]["path"] == str(root)
    assert status["source_roots"][0]["revision"] == "abc123"
    assert result["matches"][0] == {
        "root": str(root),
        "revision": "abc123",
        "path": "api/src/opentrons/protocol_api/protocol_context.py",
        "line": 3,
        "excerpt": "class ProtocolContext:",
        "matched_terms": ["class ProtocolContext", "class", "ProtocolContext"],
    }


def test_opentrons_source_read_is_line_numbered_and_blocks_escape(tmp_path, monkeypatch) -> None:
    _build_source_repo(tmp_path, monkeypatch)

    result = opentrons.read_opentrons_source(
        "robot-server/robot_server/health/router.py",
        start_line=1,
        end_line=2,
    )

    assert result["content"] == '1: @router.get("/health")\n2: async def get_health():'
    with pytest.raises(ValueError, match="相对路径"):
        opentrons.read_opentrons_source("../secret.txt")
    with pytest.raises(ValueError, match="隐藏"):
        opentrons.read_opentrons_source(".env")


def test_opentrons_official_catalog_routes_api_questions_and_rejects_other_domains() -> None:
    result = opentrons.search_opentrons_official_docs("Robot Server HTTP API runs", limit=3)

    assert result["documents"][0]["id"] == "http-api-reference"
    assert result["documents"][0]["url"] == "https://docs.opentrons.com/http/api_reference.html"
    with pytest.raises(ValueError, match="Opentrons 官方"):
        opentrons.read_opentrons_official_doc(url="https://example.com/private")


def test_official_document_excerpt_prioritizes_exact_endpoint() -> None:
    content = "\n".join(["intro", *[f"unrelated line {index}" for index in range(30)], "POST /runs", "Create a run.", "tail"])

    excerpt, match_count = opentrons._relevant_official_excerpt(content, "POST /runs", 200)

    assert match_count == 1
    assert "POST /runs\nCreate a run." in excerpt
    assert "intro" not in excerpt
