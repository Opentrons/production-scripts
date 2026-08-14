from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import PurePosixPath
import re
from threading import RLock, Timer
from time import monotonic
from typing import Any, Iterator
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse
from uuid import uuid4

import requests

from modules.protocol_monitor import service
from modules.robots.api_client.client import OpentronsHttpClient
from modules.robots.files.ssh_client import OpentronsSshClient, OpentronsSshError


_HLS_ROOT = "/hls/"
_URI_ATTRIBUTE = re.compile(r'URI="([^"]+)"')
_INACTIVE_RUN_STATUSES = {"idle", "stopped", "failed", "succeeded"}
_LIVE_STREAM_ENV_PATH = "/data/opentrons-live-stream.env"
_IDLE_STREAM_SSH_TIMEOUT_SECONDS = 8
_IDLE_STREAM_LEASE_SECONDS = 20.0
_LEASE_LOCK = RLock()
_IDLE_STREAM_LEASES: dict[tuple[str, str], "_IdleStreamLeaseState"] = {}
_DEVICE_OPERATION_LOCKS: dict[tuple[str, str], RLock] = {}

logger = logging.getLogger(__name__)


class LivestreamUpstreamError(RuntimeError):
    pass


@dataclass(frozen=True)
class LivestreamAsset:
    response: requests.Response
    device_ip: str
    device_port: int
    asset_path: str

    @property
    def is_playlist(self) -> bool:
        content_type = self.response.headers.get("Content-Type", "").casefold()
        return self.asset_path.casefold().endswith(".m3u8") or "mpegurl" in content_type


@dataclass
class _IdleStreamLeaseState:
    device_ip: str
    device_port: int
    leases: dict[str, float] = field(default_factory=dict)
    timer: Timer | None = None


def _device_key(room_id: str, device_id: str) -> tuple[str, str]:
    return room_id, device_id


def _device_operation_lock(key: tuple[str, str]) -> RLock:
    with _LEASE_LOCK:
        return _DEVICE_OPERATION_LOCKS.setdefault(key, RLock())


def _has_active_run(client: OpentronsHttpClient) -> bool:
    for run in client.list_runs():
        if not isinstance(run, dict) or not bool(run.get("current", True)):
            continue
        status = str(run.get("status") or "").casefold()
        if status and status not in _INACTIVE_RUN_STATUSES:
            return True
    return False


def _set_idle_stream_status_over_ssh(device_ip: str, *, enabled: bool) -> None:
    status = "ON" if enabled else "OFF"
    command = (
        "set -eu; "
        f"config={_LIVE_STREAM_ENV_PATH}; "
        'test -f "$config"; '
        f"sed -i 's/^STATUS=.*/STATUS={status}/' \"$config\"; "
        f"grep -qx 'STATUS={status}' \"$config\"; "
        "systemctl restart opentrons-live-stream"
    )
    if enabled:
        command += "; systemctl is-active --quiet opentrons-live-stream"
    ssh = OpentronsSshClient(device_ip)
    ssh.TIMEOUT = _IDLE_STREAM_SSH_TIMEOUT_SECONDS
    try:
        exit_code, _stdout, stderr = ssh.exec_command(
            command,
            timeout=_IDLE_STREAM_SSH_TIMEOUT_SECONDS,
        )
    except OpentronsSshError as exc:
        raise LivestreamUpstreamError(f"设备空闲直播需要 SSH 连接: {exc}") from exc
    if exit_code != 0:
        action = "启动" if enabled else "关闭"
        detail = stderr.strip() or f"无法{action} opentrons-live-stream"
        raise LivestreamUpstreamError(f"设备空闲直播{action}失败: {detail}")


def _configure_camera_enabled(client: OpentronsHttpClient) -> None:
    current = client.unwrap_data(client.request("GET", "/camera"))
    error_recovery_enabled = bool(
        current.get("errorRecoveryCameraEnabled", False)
        if isinstance(current, dict)
        else False
    )
    client.request(
        "POST",
        "/camera",
        json_body={
            "data": {
                "cameraEnabled": True,
                "liveStreamEnabled": True,
                "errorRecoveryCameraEnabled": error_recovery_enabled,
            }
        },
    )


def _client_for_device(device: dict[str, Any]) -> OpentronsHttpClient:
    return OpentronsHttpClient(
        str(device["ip"]),
        int(device.get("port", 31950)),
        timeout=8,
    )


def _has_idle_stream_leases(key: tuple[str, str]) -> bool:
    with _LEASE_LOCK:
        state = _IDLE_STREAM_LEASES.get(key)
        return bool(state and state.leases)


def _schedule_lease_expiry_locked(
    key: tuple[str, str],
    state: _IdleStreamLeaseState,
) -> None:
    if state.timer is not None:
        state.timer.cancel()
    next_expiry = min(state.leases.values()) + _IDLE_STREAM_LEASE_SECONDS
    delay = max(0.1, next_expiry - monotonic())
    timer = Timer(delay, _expire_idle_stream_leases, args=(key,))
    timer.daemon = True
    state.timer = timer
    timer.start()


def _register_idle_stream_lease(
    key: tuple[str, str],
    device_ip: str,
    device_port: int = 31950,
) -> str:
    lease_id = uuid4().hex
    with _LEASE_LOCK:
        state = _IDLE_STREAM_LEASES.get(key)
        if state is None:
            state = _IdleStreamLeaseState(device_ip=device_ip, device_port=device_port)
            _IDLE_STREAM_LEASES[key] = state
        else:
            state.device_ip = device_ip
            state.device_port = device_port
        state.leases[lease_id] = monotonic()
        _schedule_lease_expiry_locked(key, state)
    return lease_id


def touch(room_id: str, device_id: str, lease_id: str | None) -> bool:
    if not lease_id:
        return False
    key = _device_key(room_id, device_id)
    with _LEASE_LOCK:
        state = _IDLE_STREAM_LEASES.get(key)
        if state is None or lease_id not in state.leases:
            return False
        state.leases[lease_id] = monotonic()
    return True


def _disable_idle_stream_if_unused(
    key: tuple[str, str],
    device_ip: str,
    device_port: int = 31950,
) -> bool:
    with _device_operation_lock(key):
        if _has_idle_stream_leases(key):
            return False
        device = {"ip": device_ip, "port": device_port}
        client = _client_for_device(device)
        try:
            if _has_active_run(client):
                return False
        except Exception as exc:
            logger.warning("Skip idle camera shutdown for %s: %s", device_ip, exc)
            return False

        _set_idle_stream_status_over_ssh(device_ip, enabled=False)

        try:
            run_started_during_shutdown = _has_active_run(client)
        except Exception as exc:
            _set_idle_stream_status_over_ssh(device_ip, enabled=True)
            logger.warning(
                "Restored camera stream for %s after run-state verification failed: %s",
                device_ip,
                exc,
            )
            return False
        if run_started_during_shutdown:
            try:
                _configure_camera_enabled(client)
            except Exception:
                _set_idle_stream_status_over_ssh(device_ip, enabled=True)
                raise
            return False
        return True


def _expire_idle_stream_leases(key: tuple[str, str]) -> None:
    device_ip = ""
    device_port = 31950
    with _LEASE_LOCK:
        state = _IDLE_STREAM_LEASES.get(key)
        if state is None:
            return
        state.timer = None
        expires_before = monotonic() - _IDLE_STREAM_LEASE_SECONDS
        for lease_id, last_seen in list(state.leases.items()):
            if last_seen <= expires_before:
                state.leases.pop(lease_id, None)
        if state.leases:
            _schedule_lease_expiry_locked(key, state)
            return
        device_ip = state.device_ip
        device_port = state.device_port
        _IDLE_STREAM_LEASES.pop(key, None)
    try:
        _disable_idle_stream_if_unused(key, device_ip, device_port)
    except Exception as exc:
        logger.warning("Failed to close expired idle camera stream for %s: %s", device_ip, exc)


def release(room_id: str, device_id: str, lease_id: str) -> dict[str, bool]:
    key = _device_key(room_id, device_id)
    device_ip = ""
    device_port = 31950
    released = False
    with _LEASE_LOCK:
        state = _IDLE_STREAM_LEASES.get(key)
        if state is not None and lease_id in state.leases:
            released = True
            state.leases.pop(lease_id, None)
            if state.leases:
                _schedule_lease_expiry_locked(key, state)
            else:
                if state.timer is not None:
                    state.timer.cancel()
                device_ip = state.device_ip
                device_port = state.device_port
                _IDLE_STREAM_LEASES.pop(key, None)
    stopped = (
        _disable_idle_stream_if_unused(key, device_ip, device_port)
        if device_ip
        else False
    )
    return {"released": released, "stopped": stopped}


def enable(room_id: str, device_id: str) -> dict[str, bool | str | None]:
    device = service.get_device(room_id, device_id)
    key = _device_key(room_id, device_id)
    with _device_operation_lock(key):
        client = _client_for_device(device)
        _configure_camera_enabled(client)
        idle_override = not _has_active_run(client)
        lease_id: str | None = None
        if idle_override:
            _set_idle_stream_status_over_ssh(str(device["ip"]), enabled=True)
            lease_id = _register_idle_stream_lease(
                key,
                str(device["ip"]),
                int(device.get("port", 31950)),
            )
        return {
            "enabled": True,
            "idle_override": idle_override,
            "lease_id": lease_id,
        }


def _normalize_asset_path(asset_path: str) -> str:
    normalized = asset_path.strip().lstrip("/")
    path = PurePosixPath(normalized)
    if not normalized or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("直播资源路径无效")
    return path.as_posix()


def open_asset(
    room_id: str,
    device_id: str,
    asset_path: str,
    *,
    range_header: str | None = None,
) -> LivestreamAsset:
    device = service.get_device(room_id, device_id)
    normalized_path = _normalize_asset_path(asset_path)
    encoded_path = quote(normalized_path, safe="/")
    url = f"http://{device['ip']}:{int(device.get('port', 31950))}{_HLS_ROOT}{encoded_path}"
    headers = {"Range": range_header} if range_header else None
    try:
        response = requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=(4, 20),
        )
    except requests.RequestException as exc:
        raise LivestreamUpstreamError("无法连接设备摄像头流") from exc
    if response.status_code >= 400:
        status_code = response.status_code
        response.close()
        raise LivestreamUpstreamError(f"设备摄像头流返回 HTTP {status_code}")
    return LivestreamAsset(
        response=response,
        device_ip=str(device["ip"]),
        device_port=int(device.get("port", 31950)),
        asset_path=normalized_path,
    )


def iter_asset_content(asset: LivestreamAsset) -> Iterator[bytes]:
    try:
        yield from asset.response.iter_content(chunk_size=64 * 1024)
    finally:
        asset.response.close()


def _proxy_uri(
    uri: str,
    asset: LivestreamAsset,
    proxy_base: str,
    lease_id: str | None = None,
) -> str:
    upstream_base = (
        f"http://{asset.device_ip}:{asset.device_port}{_HLS_ROOT}{asset.asset_path}"
    )
    resolved = urlparse(urljoin(upstream_base, uri))
    if resolved.hostname != asset.device_ip or (resolved.port or 80) != asset.device_port:
        raise LivestreamUpstreamError("直播清单包含不受信任的外部资源")
    if not resolved.path.startswith(_HLS_ROOT):
        raise LivestreamUpstreamError("直播清单资源路径无效")
    relative_path = _normalize_asset_path(resolved.path[len(_HLS_ROOT) :])
    proxied = f"{proxy_base}/{quote(relative_path, safe='/')}"
    query = [
        (key, value)
        for key, value in parse_qsl(resolved.query, keep_blank_values=True)
        if key != "lease_id"
    ]
    if lease_id:
        query.append(("lease_id", lease_id))
    return f"{proxied}?{urlencode(query)}" if query else proxied


def rewrite_playlist(
    content: str,
    asset: LivestreamAsset,
    proxy_base: str,
    lease_id: str | None = None,
) -> str:
    rewritten: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            line = _proxy_uri(stripped, asset, proxy_base, lease_id)
        elif 'URI="' in line:
            line = _URI_ATTRIBUTE.sub(
                lambda match: f'URI="{_proxy_uri(match.group(1), asset, proxy_base, lease_id)}"',
                line,
            )
        rewritten.append(line)
    return "\n".join(rewritten) + "\n"
