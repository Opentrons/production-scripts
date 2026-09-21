from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.pip_settings import (
    LIQUID_CLASS_ROOT,
    PIPETTE_ROOT,
    PipSettingsGithubError,
    build_dataset,
    get_pip_settings_github_service,
    router,
)


def _document(path: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"sourcePath": path, "data": data}


def test_build_dataset_groups_revisions_profiles_and_liquid_classes() -> None:
    pipette_documents = [
        _document(
            f"{PIPETTE_ROOT}/general/single_channel/p50/3_0.json",
            {"displayName": "Flex 1-Channel 50 µL", "displayCategory": "FLEX", "channels": 1},
        ),
        _document(
            f"{PIPETTE_ROOT}/geometry/single_channel/p50/3_0.json",
            {"nozzleOffset": [0, 0, 0]},
        ),
        _document(
            f"{PIPETTE_ROOT}/liquid/single_channel/p50/default/3_0.json",
            {"defaultAspirateFlowRate": 35},
        ),
        _document(
            f"{PIPETTE_ROOT}/general/single_channel/p50/3_1.json",
            {"displayName": "Flex 1-Channel 50 µL", "channels": 1},
        ),
    ]
    liquid_documents = [
        _document(
            f"{LIQUID_CLASS_ROOT}/water/1.json",
            {
                "liquidClassName": "waterV2",
                "displayName": "Water",
                "description": "Water-like liquids",
                "schemaVersion": 1,
                "version": 1,
                "namespace": "opentrons",
                "byPipette": [{"pipetteModel": "flex_1channel_50", "byTipType": []}],
            },
        )
    ]

    dataset = build_dataset("edge", "abc123", pipette_documents, liquid_documents)

    assert dataset["source"]["branch"] == "edge"
    assert dataset["source"]["commit"] == "abc123"
    assert dataset["stats"] == {
        "pipetteTypes": 1,
        "pipetteDefinitionFiles": 4,
        "liquidClassDefinitionFiles": 1,
    }
    pipette = dataset["pipettes"][0]
    assert pipette["id"] == "single_channel/p50"
    assert pipette["liquidClassModel"] == "flex_1channel_50"
    assert [revision["version"] for revision in pipette["revisions"]] == ["3_0", "3_1"]
    assert pipette["revisions"][0]["liquid"]["default"]["data"]["defaultAspirateFlowRate"] == 35
    assert dataset["liquidClasses"][0]["displayName"] == "Water"


def test_build_dataset_rejects_branch_without_gen3_definitions() -> None:
    try:
        build_dataset("empty", "abc123", [], [])
    except PipSettingsGithubError as exc:
        assert exc.status_code == 404
        assert "does not contain Gen3" in str(exc)
    else:
        raise AssertionError("Expected a missing-definition error")


class FakePipSettingsService:
    async def search_branches(self, query: str) -> list[dict[str, str]]:
        assert query == "release"
        return [{"name": "release_8.5.0", "commit": "1234567890"}]

    async def load_branch(self, branch: str) -> dict[str, Any]:
        if branch == "missing":
            raise PipSettingsGithubError("Branch not found", 404)
        return {"source": {"branch": branch, "commit": "1234567890"}, "pipettes": []}


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_pip_settings_github_service] = FakePipSettingsService
    return TestClient(app)


def test_branch_search_endpoint_returns_matching_branches() -> None:
    response = _client().get("/tools/pip-settings/branches", params={"query": "release"})

    assert response.status_code == 200
    assert response.json() == {
        "branches": [{"name": "release_8.5.0", "commit": "1234567890"}]
    }


def test_dataset_endpoint_loads_exact_branch_and_maps_errors() -> None:
    client = _client()

    loaded = client.get("/tools/pip-settings/dataset", params={"branch": "feature/test"})
    missing = client.get("/tools/pip-settings/dataset", params={"branch": "missing"})

    assert loaded.status_code == 200
    assert loaded.json()["source"]["branch"] == "feature/test"
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Branch not found"
