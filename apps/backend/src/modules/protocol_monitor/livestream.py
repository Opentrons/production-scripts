from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
from typing import Iterator
from urllib.parse import quote, urljoin, urlparse

import requests

from modules.protocol_monitor import service
from modules.robots.api_client.client import OpentronsHttpClient


_HLS_ROOT = "/hls/"
_URI_ATTRIBUTE = re.compile(r'URI="([^"]+)"')


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


def enable(room_id: str, device_id: str) -> dict[str, bool]:
    device = service.get_device(room_id, device_id)
    client = OpentronsHttpClient(
        str(device["ip"]),
        int(device.get("port", 31950)),
        timeout=8,
    )
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
    return {"enabled": True}


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


def _proxy_uri(uri: str, asset: LivestreamAsset, proxy_base: str) -> str:
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
    return f"{proxied}?{resolved.query}" if resolved.query else proxied


def rewrite_playlist(content: str, asset: LivestreamAsset, proxy_base: str) -> str:
    rewritten: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            line = _proxy_uri(stripped, asset, proxy_base)
        elif 'URI="' in line:
            line = _URI_ATTRIBUTE.sub(
                lambda match: f'URI="{_proxy_uri(match.group(1), asset, proxy_base)}"',
                line,
            )
        rewritten.append(line)
    return "\n".join(rewritten) + "\n"
