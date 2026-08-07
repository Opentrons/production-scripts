from __future__ import annotations

import io
import stat
import zipfile
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from modules.robots import opentrons_control
from modules.robots.files.ssh_client import OpentronsSshClient, OpentronsSshError


def test_testing_data_path_validation(monkeypatch):
    monkeypatch.setattr(opentrons_control.setting, "ROBOT_TESTING_DATA_DIR", "/data/testing_data")

    assert opentrons_control._normalize_testing_data_path(None, allow_root=True) == "/data/testing_data"
    assert (
        opentrons_control._normalize_testing_data_path("folder/result.csv", allow_root=False)
        == "/data/testing_data/folder/result.csv"
    )
    assert (
        opentrons_control._normalize_testing_data_path(
            "/data/testing_data/folder/../result.csv",
            allow_root=False,
        )
        == "/data/testing_data/result.csv"
    )

    with pytest.raises(ValueError, match="必须位于"):
        opentrons_control._normalize_testing_data_path("../../etc/passwd", allow_root=False)
    with pytest.raises(ValueError, match="必须位于"):
        opentrons_control._normalize_testing_data_path("/data/testing_data_other/file", allow_root=False)
    with pytest.raises(ValueError, match="根目录"):
        opentrons_control._normalize_testing_data_path("/data/testing_data", allow_root=False)


def test_testing_data_download_and_delete_use_fixed_root(monkeypatch):
    calls: dict[str, object] = {}

    class FakeFileService:
        def __init__(self, ip: str):
            calls["ip"] = ip

        def download_files_as_zip(self, paths: list[str], *, root_path: str) -> bytes:
            calls["download_paths"] = paths
            calls["root_path"] = root_path
            return b"zip-content"

        def delete_paths(self, paths: list[str]) -> list[str]:
            calls["delete_paths"] = paths
            return paths

    monkeypatch.setattr(opentrons_control.setting, "ROBOT_TESTING_DATA_DIR", "/data/testing_data")
    monkeypatch.setattr(opentrons_control, "OpentronsFileService", FakeFileService)

    filename, content, media_type = opentrons_control.download_robot_testing_data(
        "192.168.6.126",
        ["folder/a.txt", "/data/testing_data/folder/a.txt", "b.txt"],
    )
    assert filename == "testing-data-192-168-6-126.zip"
    assert content == b"zip-content"
    assert media_type == "application/zip"
    assert calls["download_paths"] == [
        "/data/testing_data/folder/a.txt",
        "/data/testing_data/b.txt",
    ]
    assert calls["root_path"] == "/data/testing_data"

    result = opentrons_control.delete_robot_testing_data(
        "192.168.6.126",
        ["folder", "b.txt"],
    )
    assert result["deleted_count"] == 2
    assert calls["delete_paths"] == [
        "/data/testing_data/folder",
        "/data/testing_data/b.txt",
    ]


class FakeSftp:
    def __init__(self):
        self.modes = {
            "/data/testing_data/folder": stat.S_IFDIR,
            "/data/testing_data/folder/a.txt": stat.S_IFREG,
            "/data/testing_data/b.txt": stat.S_IFREG,
        }
        self.contents = {
            "/data/testing_data/folder/a.txt": b"alpha",
            "/data/testing_data/b.txt": b"beta",
        }
        self.removed: list[str] = []
        self.removed_dirs: list[str] = []

    def lstat(self, path: str):
        if path not in self.modes:
            raise FileNotFoundError(path)
        return SimpleNamespace(st_mode=self.modes[path])

    def listdir_attr(self, path: str):
        if path == "/data/testing_data/folder":
            return [SimpleNamespace(filename="a.txt", st_mode=stat.S_IFREG)]
        return []

    def open(self, path: str, _mode: str):
        return io.BytesIO(self.contents[path])

    def remove(self, path: str):
        self.removed.append(path)

    def rmdir(self, path: str):
        self.removed_dirs.append(path)


def test_ssh_client_packages_multiple_paths_and_collapses_children(monkeypatch):
    client = OpentronsSshClient("192.168.6.126")
    sftp = FakeSftp()

    @contextmanager
    def fake_connect():
        yield None, sftp

    monkeypatch.setattr(client, "connect", fake_connect)

    content = client.download_paths_as_zip(
        [
            "/data/testing_data/folder/a.txt",
            "/data/testing_data/folder",
            "/data/testing_data/b.txt",
        ],
        root_dir="/data/testing_data",
    )

    with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
        assert archive.namelist() == ["b.txt", "folder/", "folder/a.txt"]
        assert archive.read("b.txt") == b"beta"
        assert archive.read("folder/a.txt") == b"alpha"


def test_ssh_client_rejects_archive_paths_outside_root():
    with pytest.raises(OpentronsSshError, match="outside archive root"):
        OpentronsSshClient._relative_archive_name("/data/testing_data", "/etc/passwd")


def test_ssh_client_deletes_directories_recursively(monkeypatch):
    client = OpentronsSshClient("192.168.6.126")
    sftp = FakeSftp()

    @contextmanager
    def fake_connect():
        yield None, sftp

    monkeypatch.setattr(client, "connect", fake_connect)
    monkeypatch.setattr(client, "remount_read_write", lambda _path: None)

    deleted = client.delete_paths([
        "/data/testing_data/folder/a.txt",
        "/data/testing_data/folder",
        "/data/testing_data/b.txt",
    ])

    assert deleted == ["/data/testing_data/b.txt", "/data/testing_data/folder"]
    assert sftp.removed == ["/data/testing_data/b.txt", "/data/testing_data/folder/a.txt"]
    assert sftp.removed_dirs == ["/data/testing_data/folder"]
