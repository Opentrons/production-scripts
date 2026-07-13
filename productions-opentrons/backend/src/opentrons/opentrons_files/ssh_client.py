from __future__ import annotations

import io
import posixpath
import shlex
import stat
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

import paramiko

import settings as setting


@dataclass
class RemoteFileEntry:
    name: str
    path: str
    is_dir: bool
    size: int
    modified_at: int | None


class OpentronsSshError(Exception):
    pass


class OpentronsSshClient:
    TIMEOUT = 30

    def __init__(
        self,
        ip: str,
        *,
        username: str = "root",
        password: str = "",
        key_path: str | None = None,
    ):
        self.ip = ip
        self.username = username
        self.password = password
        self.key_path = key_path or setting.ROBOT_KEY_PATH

    @contextmanager
    def connect(self) -> Iterator[tuple[paramiko.SSHClient, paramiko.SFTPClient]]:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            try:
                client.connect(
                    self.ip,
                    username=self.username,
                    key_filename=self.key_path,
                    timeout=self.TIMEOUT,
                )
            except Exception:
                if not self.password:
                    raise
                client.connect(
                    self.ip,
                    username=self.username,
                    password=self.password,
                    timeout=self.TIMEOUT,
                )
            sftp = client.open_sftp()
            yield client, sftp
        except (paramiko.SSHException, OSError, TimeoutError) as exc:
            raise OpentronsSshError(str(exc)) from exc
        finally:
            try:
                client.close()
            except Exception:
                pass

    def test_connection(self) -> bool:
        with self.connect():
            return True

    def exec_command(self, command: str) -> tuple[int, str, str]:
        with self.connect() as (client, _sftp):
            _stdin, stdout, stderr = client.exec_command(command, timeout=self.TIMEOUT)
            exit_code = stdout.channel.recv_exit_status()
            return exit_code, stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")

    def reboot(self) -> None:
        exit_code, _stdout, stderr = self.exec_command("reboot")
        if exit_code not in (0, -1):
            raise OpentronsSshError(stderr or "Reboot command failed")

    def list_dir(self, remote_path: str) -> list[RemoteFileEntry]:
        normalized = remote_path or "/"
        entries: list[RemoteFileEntry] = []
        with self.connect() as (_client, sftp):
            for attr in sftp.listdir_attr(normalized):
                full_path = f"{normalized.rstrip('/')}/{attr.filename}"
                entries.append(
                    RemoteFileEntry(
                        name=attr.filename,
                        path=full_path,
                        is_dir=stat.S_ISDIR(attr.st_mode),
                        size=attr.st_size,
                        modified_at=attr.st_mtime,
                    )
                )
        entries.sort(key=lambda item: (not item.is_dir, item.name.lower()))
        return entries

    def read_text(self, remote_path: str) -> str:
        with self.connect() as (_client, sftp):
            with sftp.open(remote_path, "r") as remote_file:
                return remote_file.read().decode("utf-8", errors="replace")

    def write_text(self, remote_path: str, content: str, *, create_if_missing: bool = True) -> bool:
        if not create_if_missing:
            with self.connect() as (_client, sftp):
                try:
                    attrs = sftp.stat(remote_path)
                except FileNotFoundError:
                    return False
                if stat.S_ISDIR(attrs.st_mode):
                    raise OpentronsSshError(f"Path is a directory: {remote_path}")

        self.remount_read_write(remote_path)
        with self.connect() as (_client, sftp):
            if not create_if_missing:
                try:
                    attrs = sftp.stat(remote_path)
                except FileNotFoundError:
                    return False
                if stat.S_ISDIR(attrs.st_mode):
                    raise OpentronsSshError(f"Path is a directory: {remote_path}")
            with sftp.open(remote_path, "w") as remote_file:
                remote_file.write(content.encode("utf-8"))
        return True

    def write_bytes(self, remote_path: str, content: bytes) -> None:
        self.remount_read_write(remote_path)
        with self.connect() as (_client, sftp):
            with sftp.open(remote_path, "wb") as remote_file:
                remote_file.write(content)

    def remount_read_write(self, remote_path: str) -> None:
        target_dir = posixpath.dirname((remote_path or "/").rstrip("/")) or "/"
        command = (
            f"cd {shlex.quote(target_dir)} && "
            "mount_point=$(df -P . 2>/dev/null | awk 'NR==2 {print $6}') && "
            'if [ -z "$mount_point" ]; then mount_point=/; fi && '
            'mount -o remount,rw "$mount_point"'
        )
        exit_code, _stdout, stderr = self.exec_command(command)
        if exit_code != 0:
            message = stderr.strip() or "Remount read-write failed"
            raise OpentronsSshError(message)

    def read_bytes(self, remote_path: str) -> bytes:
        with self.connect() as (_client, sftp):
            with sftp.open(remote_path, "rb") as remote_file:
                return remote_file.read()

    def path_exists(self, remote_path: str) -> bool:
        with self.connect() as (_client, sftp):
            try:
                sftp.stat(remote_path)
                return True
            except FileNotFoundError:
                return False

    def download_path(self, remote_path: str) -> tuple[str, bytes, str]:
        with self.connect() as (_client, sftp):
            try:
                attrs = sftp.stat(remote_path)
            except FileNotFoundError as exc:
                raise OpentronsSshError(f"Path not found: {remote_path}") from exc

            if stat.S_ISDIR(attrs.st_mode):
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    self._add_directory_to_zip(sftp, remote_path, remote_path, zip_file)
                folder_name = remote_path.rstrip("/").rsplit("/", 1)[-1] or "folder"
                return f"{folder_name}.zip", buffer.getvalue(), "application/zip"

            with sftp.open(remote_path, "rb") as remote_file:
                content = remote_file.read()
            filename = remote_path.rsplit("/", 1)[-1] or "download.bin"
            return filename, content, "application/octet-stream"

    def _add_directory_to_zip(
        self,
        sftp: paramiko.SFTPClient,
        remote_dir: str,
        root_dir: str,
        zip_file: zipfile.ZipFile,
    ) -> None:
        for attr in sftp.listdir_attr(remote_dir):
            full_path = f"{remote_dir.rstrip('/')}/{attr.filename}"
            if stat.S_ISDIR(attr.st_mode):
                self._add_directory_to_zip(sftp, full_path, root_dir, zip_file)
                continue
            archive_name = self._archive_name(root_dir, full_path)
            with sftp.open(full_path, "rb") as remote_file:
                zip_file.writestr(archive_name, remote_file.read())

    @staticmethod
    def _archive_name(root_dir: str, full_path: str) -> str:
        root = root_dir.rstrip("/") or "/"
        if root == "/":
            return full_path.lstrip("/")
        prefix = f"{root}/"
        if full_path.startswith(prefix):
            return full_path[len(prefix):]
        return posixpath.basename(full_path)

    def delete_path(self, remote_path: str) -> None:
        self.remount_read_write(remote_path)
        with self.connect() as (client, sftp):
            try:
                attrs = sftp.stat(remote_path)
            except FileNotFoundError as exc:
                raise OpentronsSshError(f"Path not found: {remote_path}") from exc

            if stat.S_ISDIR(attrs.st_mode):
                _stdin, stdout, stderr = client.exec_command(f"rm -rf {remote_path}", timeout=self.TIMEOUT)
                exit_code = stdout.channel.recv_exit_status()
                if exit_code != 0:
                    raise OpentronsSshError(stderr.read().decode("utf-8", errors="replace") or "Delete directory failed")
            else:
                sftp.remove(remote_path)
