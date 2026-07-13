from __future__ import annotations

import asyncio
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from bson import ObjectId
from fastapi import UploadFile
import pytest

from api.services import file_resources


class FakeCursor(list):
    def sort(self, key: str, direction: int = 1):
        reverse = direction < 0
        super().sort(key=lambda item: item.get(key), reverse=reverse)
        return self


class FakeCollection:
    def __init__(self):
        self.documents: list[dict] = []

    def create_index(self, *args, **kwargs):
        return None

    def find_one(self, query: dict):
        return next((document for document in self.documents if self._matches(document, query)), None)

    def find(self, query: dict):
        return FakeCursor(deepcopy([document for document in self.documents if self._matches(document, query)]))

    def insert_one(self, document: dict):
        saved = deepcopy(document)
        saved.setdefault("_id", ObjectId())
        document.setdefault("_id", saved["_id"])
        self.documents.append(saved)
        return SimpleNamespace(inserted_id=saved["_id"])

    def update_one(self, query: dict, update: dict):
        document = self.find_one(query)
        if document is not None:
            document.update(deepcopy(update.get("$set", {})))
        return SimpleNamespace(matched_count=1 if document else 0)

    def find_one_and_delete(self, query: dict):
        for index, document in enumerate(self.documents):
            if self._matches(document, query):
                return self.documents.pop(index)
        return None

    @staticmethod
    def _matches(document: dict, query: dict) -> bool:
        return all(document.get(key) == value for key, value in query.items())


@pytest.fixture
def fake_resource_collections(monkeypatch: pytest.MonkeyPatch):
    projects = FakeCollection()
    versions = FakeCollection()
    monkeypatch.setattr(file_resources, "get_resource_collections", lambda: (projects, versions))
    return projects, versions


def make_upload(filename: str = "release.zip", content: bytes = b"resource-content") -> UploadFile:
    return UploadFile(file=BytesIO(content), filename=filename)


def test_create_list_update_download_and_delete_version(
    fake_resource_collections,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    projects, versions = fake_resource_collections
    monkeypatch.setattr(file_resources.setting, "FILE_RESOURCE_DIR", str(tmp_path))

    created = asyncio.run(
        file_resources.create_version(
            project_id=None,
            project_name="Firmware Tools",
            project_description="Factory firmware resources",
            version="1.0.0",
            version_notes="Initial release",
            upload=make_upload(),
        )
    )

    assert created["version"] == "1.0.0"
    assert created["filename"] == "release.zip"
    assert created["file_size"] == len(b"resource-content")
    assert len(projects.documents) == 1
    assert len(versions.documents) == 1

    project_list = file_resources.list_projects()
    assert project_list["total"] == 1
    assert project_list["projects"][0]["name"] == "Firmware Tools"
    assert project_list["projects"][0]["versions"][0]["version_notes"] == "Initial release"

    updated = file_resources.update_version(
        created["id"],
        {"version": "1.0.1", "version_notes": "Patch release"},
    )
    assert updated["version"] == "1.0.1"
    assert updated["version_notes"] == "Patch release"

    download_path, filename, content_type = file_resources.resolve_download(created["id"])
    assert download_path.read_bytes() == b"resource-content"
    assert filename == "release.zip"
    assert content_type == "application/zip"

    result = file_resources.delete_version(created["id"])
    assert result == {"success": True, "deleted_version_id": created["id"]}
    assert not download_path.exists()
    assert versions.documents == []


def test_rejects_duplicate_project_version(
    fake_resource_collections,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(file_resources.setting, "FILE_RESOURCE_DIR", str(tmp_path))
    first = asyncio.run(
        file_resources.create_version(
            project_id=None,
            project_name="Robot Assets",
            project_description="",
            version="2.0",
            version_notes="",
            upload=make_upload("first.bin"),
        )
    )

    with pytest.raises(file_resources.FileResourceValidationError, match="已存在"):
        asyncio.run(
            file_resources.create_version(
                project_id=first["project_id"],
                project_name="Robot Assets",
                project_description="",
                version="2.0",
                version_notes="duplicate",
                upload=make_upload("second.bin"),
            )
        )


def test_safe_filename_removes_path_and_unsafe_characters() -> None:
    assert file_resources.safe_filename("../../release @ final?.zip") == "release _ final_.zip"
