"""Fetch Opentrons App logs from a robot over HTTP and bundle them into a zip.

The bundle includes the standard app logs used by the GRAV11 log package:
``api.log``, ``can_bus.log``, ``serial.log``, ``touchscreen.log``,
``update_server.log``, and ``server.log``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import io
import zipfile
from datetime import datetime, timezone

from modules.robots.api_client.client import OpentronsApiError, OpentronsHttpClient

STANDARD_LOG_IDENTIFIERS = (
    "api.log",
    "can_bus.log",
    "serial.log",
    "touchscreen.log",
    "update_server.log",
    "server.log",
)

# Robot log endpoints can take several minutes to build large journald
# responses. Keep this separate from the normal API request timeout.
APP_LOG_REQUEST_TIMEOUT = 5 * 60

_ZIP_MEMBER_ROOT = "opentrons-logs"


def _log_identifier(path: str) -> str:
    name = path.strip().split("?", 1)[0].split("#", 1)[0].rstrip("/").split("/")[-1]
    if not name:
        return ""
    return name if name.endswith(".log") else f"{name}.log"


def _safe_member_name(path: str) -> str:
    """Turn a robot log path like ``/logs/api.log`` into a safe zip member name."""
    name = _log_identifier(path)
    if not name:
        name = "opentrons.log"
    return f"{_ZIP_MEMBER_ROOT}/{name}"


def _unique_member_name(member: str, used: set[str]) -> str:
    if member not in used:
        used.add(member)
        return member
    base, dot, suffix = member.rpartition(".")
    candidate = f"{base}-1.{suffix}" if dot else f"{member}-1"
    counter = 2
    while candidate in used:
        candidate = f"{base}-{counter}.{suffix}" if dot else f"{member}-{counter}"
        counter += 1
    used.add(candidate)
    return candidate


def _fetch_log_sources(
    client: OpentronsHttpClient,
) -> list[tuple[str, bytes]]:
    """Collect (member_name, content) pairs from the fixed robot log endpoints."""
    sources = [f"/logs/{identifier}" for identifier in STANDARD_LOG_IDENTIFIERS]

    def fetch_one(path: str) -> tuple[str, bytes] | None:
        try:
            response = client.request_raw("GET", path, timeout=APP_LOG_REQUEST_TIMEOUT)
        except OpentronsApiError:
            # A single missing log must not fail the whole bundle.
            return None
        return _safe_member_name(path), response.content

    # The robot spends most of the time querying journald for each endpoint.
    # Fetch the independent endpoints concurrently, while executor.map keeps
    # the archive order stable.
    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        fetched = executor.map(fetch_one, sources)

    entries: list[tuple[str, bytes]] = []
    used_members: set[str] = set()
    for item in fetched:
        if item is None:
            continue
        member, content = item
        entries.append((_unique_member_name(member, used_members), content))
    return entries


def collect_opentrons_app_logs(ip: str, port: int) -> tuple[bytes, str]:
    """Fetch the robot's Opentrons service logs and return ``(zip_bytes, filename)``.

    Raises:
        ValueError: no log content could be collected from the robot.
    """
    client = OpentronsHttpClient(ip, port=port)
    entries = _fetch_log_sources(client)
    if not entries:
        raise ValueError(f"机器人 {ip} 没有可下载的 Opentrons 服务日志")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for member, content in entries:
            archive.writestr(member, content)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_ip = ip.replace(":", "-")
    filename = f"opentrons-app-logs-{safe_ip}-{stamp}.zip"
    return buffer.getvalue(), filename
