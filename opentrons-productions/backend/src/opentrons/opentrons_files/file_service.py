from __future__ import annotations

from dataclasses import asdict

import settings as setting
from opentrons.opentrons_files.ssh_client import OpentronsSshClient, OpentronsSshError


class OpentronsFileService:
    DEFAULT_PATH = "/"

    def __init__(self, ip: str):
        self.ip = ip
        self.ssh = OpentronsSshClient(ip)

    def get_connection_status(self) -> dict:
        try:
            self.ssh.test_connection()
            return {"connected": True, "message": "SSH connected"}
        except Exception as exc:
            return {"connected": False, "message": str(exc)}

    def list_directory(self, path: str | None = None) -> dict:
        remote_path = path or self.DEFAULT_PATH
        entries = self.ssh.list_dir(remote_path)
        return {
            "path": remote_path,
            "entries": [asdict(entry) for entry in entries],
        }

    def read_file(self, path: str) -> dict:
        content = self.ssh.read_text(path)
        return {"path": path, "content": content}

    def write_file(self, path: str, content: str, *, create_if_missing: bool = True) -> dict:
        written = self.ssh.write_text(path, content, create_if_missing=create_if_missing)
        return {"path": path, "success": written, "skipped": not written}

    def upload_file(self, path: str, content: bytes) -> dict:
        self.ssh.write_bytes(path, content)
        return {"path": path, "success": True}

    def delete_path(self, path: str) -> dict:
        self.ssh.delete_path(path)
        return {"path": path, "success": True}

    def download_file(self, path: str) -> tuple[str, bytes, str]:
        return self.ssh.download_path(path)

    def find_protocol_source_dir(self, protocol_id: str) -> str:
        candidates = [
            f"{base.rstrip('/')}/{protocol_id}"
            for base in setting.ROBOT_PROTOCOL_SOURCE_BASES
        ]
        for remote_path in candidates:
            if self.ssh.path_exists(remote_path):
                return remote_path

        search_roots = " ".join(
            {
                base.rsplit("/protocols", 1)[0]
                for base in setting.ROBOT_PROTOCOL_SOURCE_BASES
            }
        )
        exit_code, stdout, _stderr = self.ssh.exec_command(
            f"find {search_roots} -type d -path '*/protocols/{protocol_id}' 2>/dev/null | head -n 1"
        )
        found = stdout.strip()
        if exit_code == 0 and found:
            return found

        raise OpentronsSshError(f"Protocol source directory not found for {protocol_id}")

    def download_protocol_source(self, protocol_id: str) -> tuple[str, bytes, str]:
        remote_dir = self.find_protocol_source_dir(protocol_id)
        entries = self.ssh.list_dir(remote_dir)
        files = [entry for entry in entries if not entry.is_dir]
        if len(files) == 1:
            return self.ssh.download_path(files[0].path)
        return self.ssh.download_path(remote_dir)
