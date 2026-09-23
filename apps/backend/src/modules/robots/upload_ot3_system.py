#!/usr/bin/env python3
"""Upload an OT3 system update zip to an Opentrons robot.

Flow:
  1. GET  /server/update/health
  2. POST /server/update/begin
  3. POST /server/update/{token}/file
  4. Poll /server/update/{token}/status until done
  5. POST /server/update/{token}/commit
  6. POST /server/restart

The upload field name is fixed to ``system-update.zip`` because that is what the
OpenEmbedded update server accepts for Flex / OT3 systems.

Demo:
python3 /Users/andy/projects/som-dev/scripts/upload_ot3_system.py 192.168.0.103 /Users/andy/Downloads/ot3-system-9.1.0.zip --cancel-existing --wait-online
"""

from __future__ import annotations

import argparse
import http.client
import json
import mimetypes
import ssl
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


DEFAULT_PORT = 31950
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_POLL_INTERVAL_S = 2.0
DEFAULT_WAIT_INTERVAL_S = 5.0
DEFAULT_WAIT_TIMEOUT_S = 900.0
DEFAULT_CHUNK_SIZE = 1024 * 1024
UPLOAD_FIELD_NAME = "system-update.zip"
EXPECTED_ROBOT_MODEL = "OT-3 Standard"


class RobotUpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Endpoint:
    scheme: str
    host: str
    port: int

    @property
    def authority(self) -> str:
        if ":" in self.host and not self.host.startswith("["):
            return f"[{self.host}]:{self.port}"
        return f"{self.host}:{self.port}"


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def human_bytes(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(n)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)}{unit}"
            return f"{value:.1f}{unit}"
        value /= 1024.0
    return f"{n}B"


def parse_endpoint(raw: str) -> Endpoint:
    if "://" not in raw:
        raw = f"http://{raw}"

    parsed = urlparse(raw)
    if not parsed.hostname:
        raise ValueError(f"invalid robot host: {raw!r}")
    if parsed.path not in ("", "/"):
        raise ValueError("do not include a path in the robot host")

    return Endpoint(
        scheme=parsed.scheme or "http",
        host=parsed.hostname,
        port=parsed.port or DEFAULT_PORT,
    )


def build_headers(bearer_token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    return headers


class RobotUpdateClient:
    def __init__(
        self,
        endpoint: Endpoint,
        bearer_token: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        insecure: bool = False,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        on_progress: Callable[[int, int, int], None] | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.bearer_token = bearer_token
        self.timeout_s = timeout_s
        self.chunk_size = chunk_size
        self.on_progress = on_progress
        self._headers = build_headers(bearer_token)
        self._ssl_context = (
            ssl._create_unverified_context() if insecure else ssl.create_default_context()
        )

    def _connection(self) -> http.client.HTTPConnection:
        if self.endpoint.scheme == "https":
            return http.client.HTTPSConnection(
                self.endpoint.host,
                self.endpoint.port,
                timeout=self.timeout_s,
                context=self._ssl_context,
            )
        return http.client.HTTPConnection(
            self.endpoint.host, self.endpoint.port, timeout=self.timeout_s
        )

    def _request_json(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        extra_headers: dict[str, str] | None = None,
        ok_statuses: set[int] | None = None,
    ) -> tuple[int, dict[str, Any] | None, str]:
        headers = dict(self._headers)
        if extra_headers:
            headers.update(extra_headers)

        conn = self._connection()
        try:
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
            text = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(text) if text.strip() else None
            except json.JSONDecodeError:
                data = None

            allowed = ok_statuses or {200}
            if resp.status not in allowed:
                raise RobotUpdateError(
                    f"{method} {path} -> {resp.status} {resp.reason}: "
                    f"{text.strip() or '<empty>'}"
                )
            return resp.status, data, text
        finally:
            conn.close()

    def health(self) -> dict[str, Any]:
        _, data, _ = self._request_json("GET", "/server/update/health")
        if not isinstance(data, dict):
            raise RobotUpdateError("unexpected /server/update/health payload")
        return data

    def begin(self, cancel_existing: bool = False) -> dict[str, Any]:
        try:
            _, data, _ = self._request_json(
                "POST", "/server/update/begin", ok_statuses={201}
            )
        except RobotUpdateError as exc:
            if "409" not in str(exc) or not cancel_existing:
                raise

            eprint("已有更新会话，正在取消并重试...")
            self._request_json("POST", "/server/update/cancel", ok_statuses={200})
            _, data, _ = self._request_json(
                "POST", "/server/update/begin", ok_statuses={201}
            )

        if not isinstance(data, dict) or "token" not in data:
            raise RobotUpdateError("begin did not return a token")
        return data

    def upload(
        self,
        token: str,
        file_path: Path,
        field_name: str = UPLOAD_FIELD_NAME,
    ) -> dict[str, Any]:
        file_size = file_path.stat().st_size
        boundary = f"----opentrons-{uuid.uuid4().hex}"
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        preamble = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field_name}"; '
            f'filename="{file_path.name}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode("utf-8")
        closing = f"\r\n--{boundary}--\r\n".encode("utf-8")
        content_length = len(preamble) + file_size + len(closing)

        conn = self._connection()
        headers = dict(self._headers)
        headers.update(
            {
                "Host": self.endpoint.authority,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(content_length),
            }
        )

        try:
            conn.putrequest(
                "POST",
                f"/server/update/{token}/file",
                skip_host=True,
                skip_accept_encoding=True,
            )
            for key, value in headers.items():
                conn.putheader(key, value)
            conn.endheaders()

            conn.send(preamble)
            sent = 0
            last_pct = -1
            with file_path.open("rb") as fh:
                while True:
                    chunk = fh.read(self.chunk_size)
                    if not chunk:
                        break
                    conn.send(chunk)
                    sent += len(chunk)
                    pct = int((sent * 100) / file_size) if file_size else 100
                    if pct != last_pct:
                        last_pct = pct
                        self._render_upload_progress(sent, file_size, pct)
            conn.send(closing)
            print(file=sys.stderr)

            resp = conn.getresponse()
            text = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(text) if text.strip() else None
            except json.JSONDecodeError:
                data = None

            if resp.status != 201:
                raise RobotUpdateError(
                    f"POST /server/update/{token}/file -> {resp.status} {resp.reason}: "
                    f"{text.strip() or '<empty>'}"
                )
            if not isinstance(data, dict):
                raise RobotUpdateError("upload did not return session state")
            return data
        finally:
            conn.close()

    def status(self, token: str) -> dict[str, Any]:
        _, data, _ = self._request_json(
            "GET", f"/server/update/{token}/status", ok_statuses={200}
        )
        if not isinstance(data, dict):
            raise RobotUpdateError("unexpected status payload")
        return data

    def commit(self, token: str) -> dict[str, Any]:
        _, data, _ = self._request_json(
            "POST", f"/server/update/{token}/commit", ok_statuses={200}
        )
        if not isinstance(data, dict):
            raise RobotUpdateError("unexpected commit payload")
        return data

    def restart(self) -> dict[str, Any]:
        _, data, _ = self._request_json("POST", "/server/restart", ok_statuses={200})
        if not isinstance(data, dict):
            raise RobotUpdateError("unexpected restart payload")
        return data

    def wait_for_boot(
        self, timeout_s: float, interval_s: float, previous_boot_id: str | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_s
        observed_offline = False
        last_message: str | None = None
        while True:
            if time.monotonic() >= deadline:
                raise RobotUpdateError(f"robot did not reboot within {timeout_s:.0f}s")
            try:
                health = self.health()
            except (OSError, RobotUpdateError) as exc:
                observed_offline = True
                if time.monotonic() >= deadline:
                    raise RobotUpdateError(
                        f"robot did not come back online within {timeout_s:.0f}s"
                    ) from exc
                time.sleep(interval_s)
                continue

            boot_id = health.get("bootId")
            rebooted = (boot_id != previous_boot_id) if previous_boot_id and boot_id else observed_offline
            if not rebooted:
                time.sleep(interval_s)
                continue

            message = (
                f"已重启回来: bootId={health.get('bootId', 'unknown')} "
                f"system={health.get('systemVersion', 'unknown')}"
            )
            if message != last_message:
                print(message)
                last_message = message
            return health

    def _render_upload_progress(self, sent: int, total: int, pct: int) -> None:
        if self.on_progress:
            self.on_progress(sent, total, pct)
            return
        msg = (
            f"\r上传中: {pct:3d}% "
            f"({human_bytes(sent)}/{human_bytes(total)})"
        )
        print(msg, end="", file=sys.stderr, flush=True)


def format_status(status: dict[str, Any]) -> str:
    stage = str(status.get("stage", "unknown"))
    message = status.get("message")
    progress = status.get("progress")
    if isinstance(progress, (int, float)):
        pct = int(round(progress * 100)) if progress <= 1 else int(round(progress))
        if message:
            return f"{stage}: {message} ({pct}%)"
        return f"{stage} ({pct}%)"
    if message:
        return f"{stage}: {message}"
    return stage


def poll_until_done(
    client: RobotUpdateClient,
    token: str,
    interval_s: float,
) -> dict[str, Any]:
    last_line: str | None = None
    while True:
        status = client.status(token)
        line = format_status(status)
        if line != last_line:
            print(f"状态: {line}")
            last_line = line

        stage = str(status.get("stage", "unknown"))
        if stage == "error":
            raise RobotUpdateError(
                f"{status.get('error', 'update error')}: {status.get('message', '')}"
            )
        if stage == "done":
            return status
        time.sleep(interval_s)


def print_health_summary(health: dict[str, Any]) -> None:
    print(
        "健康: "
        f"model={health.get('robotModel', 'unknown')}, "
        f"system={health.get('systemVersion', 'unknown')}, "
        f"api={health.get('apiServerVersion', 'unknown')}, "
        f"update={health.get('updateServerVersion', 'unknown')}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Upload an ot3-system.zip file to an Opentrons OT-3 robot"
    )
    parser.add_argument("robot", help="robot host, e.g. 192.168.0.103 or http://host:31950")
    parser.add_argument("zipfile", help="path to ot3-system.zip")
    parser.add_argument(
        "--token",
        default=None,
        help="optional bearer token for Authorization: Bearer ...",
    )
    parser.add_argument(
        "--cancel-existing",
        action="store_true",
        help="cancel an existing update session and retry begin",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL_S,
        help="seconds between status polls",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help="socket timeout in seconds",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help="upload chunk size in bytes",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="disable TLS certificate verification for https:// hosts",
    )
    parser.add_argument(
        "--wait-online",
        action="store_true",
        help="after restart, wait for /server/update/health to come back",
    )
    parser.add_argument(
        "--wait-timeout",
        type=float,
        default=DEFAULT_WAIT_TIMEOUT_S,
        help="seconds to wait for the robot to come back online",
    )
    parser.add_argument(
        "--wait-interval",
        type=float,
        default=DEFAULT_WAIT_INTERVAL_S,
        help="seconds between boot polls",
    )
    args = parser.parse_args(argv)

    zip_path = Path(args.zipfile).expanduser().resolve()
    if not zip_path.exists():
        raise SystemExit(f"file not found: {zip_path}")
    if not zip_path.is_file():
        raise SystemExit(f"not a file: {zip_path}")

    endpoint = parse_endpoint(args.robot)
    client = RobotUpdateClient(
        endpoint=endpoint,
        bearer_token=args.token,
        timeout_s=args.timeout,
        insecure=args.insecure,
        chunk_size=args.chunk_size,
    )

    print(f"目标: {endpoint.scheme}://{endpoint.authority}")
    print(f"文件: {zip_path}")

    health = client.health()
    print_health_summary(health)

    robot_model = health.get("robotModel")
    if robot_model is not None and robot_model != EXPECTED_ROBOT_MODEL:
        raise SystemExit(
            f"这台机器的 robotModel 是 {robot_model!r}，不是 {EXPECTED_ROBOT_MODEL!r}。"
            " 这个脚本是给 OT-3 / Flex 系统包用的。"
        )

    session = client.begin(cancel_existing=args.cancel_existing)
    token = str(session["token"])
    print(f"会话: {token}")

    upload_state = client.upload(token, zip_path)
    print(f"上传后: {format_status(upload_state)}")

    final_state = poll_until_done(client, token, args.poll_interval)
    print(f"写入完成: {format_status(final_state)}")

    commit_state = client.commit(token)
    print(f"提交后: {format_status(commit_state)}")

    restart_state = client.restart()
    print(f"重启请求: {restart_state.get('message', 'ok')}")

    if args.wait_online:
        client.wait_for_boot(args.wait_timeout, args.wait_interval, health.get("bootId"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
