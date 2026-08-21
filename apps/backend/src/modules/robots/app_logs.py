"""Fetch Opentrons service logs from a robot over its HTTP API and zip them.

Mirrors the desktop Opentrons App's "Download Logs" behavior
(app/src/organisms/Desktop/Devices/RobotSettings/AdvancedTab/Troubleshooting.tsx):
read the ``GET /health`` ``logs`` list, fetch every log file over HTTP
(``GET /logs/...``), and bundle them into a single archive the browser can save.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone

from modules.robots.api_client.client import OpentronsApiError, OpentronsHttpClient

# Fallback syslog identifiers used when /health is unreachable or does not
# report a logs list (see robot_server/service/legacy/routers/logs.py).
FALLBACK_LOG_IDENTIFIERS = [
    "api",
    "api_server",
    "server",
    "serial",
    "touchscreen",
    "update_server",
    "can",
]
FALLBACK_LOG_RECORDS = 10000

_ZIP_MEMBER_ROOT = "opentrons-logs"


def _safe_member_name(path: str) -> str:
    """Turn a robot log path like ``/logs/api.log`` into a safe zip member name."""
    name = path.strip().rstrip("/").split("/")[-1]
    if not name:
        name = "opentrons.log"
    if "." not in name:
        name = f"{name}.log"
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
    health: dict,
) -> list[tuple[str, bytes]]:
    """Collect (member_name, content) pairs for every log the robot exposes."""
    sources: list[str] = []
    if isinstance(health, dict):
        logs = health.get("logs")
        if isinstance(logs, list):
            sources = [str(item) for item in logs if str(item).strip()]

    entries: list[tuple[str, bytes]] = []
    used_members: set[str] = set()

    if sources:
        for path in sources:
            try:
                response = client.request_raw("GET", path)
            except OpentronsApiError:
                # A single missing log must not fail the whole bundle.
                continue
            entries.append((_unique_member_name(_safe_member_name(path), used_members), response.content))
        return entries

    # Fallback: pull recent journald records for each known service.
    for identifier in FALLBACK_LOG_IDENTIFIERS:
        try:
            response = client.request_raw(
                "GET",
                f"/logs/{identifier}?format=text&records={FALLBACK_LOG_RECORDS}",
            )
        except OpentronsApiError:
            continue
        member = _unique_member_name(f"{_ZIP_MEMBER_ROOT}/{identifier}.log", used_members)
        entries.append((member, response.content))
    return entries


def collect_opentrons_app_logs(ip: str, port: int) -> tuple[bytes, str]:
    """Fetch the robot's Opentrons service logs and return ``(zip_bytes, filename)``.

    Raises:
        OpentronsApiError: the robot HTTP API could not be reached at all.
        ValueError: no log content could be collected from the robot.
    """
    client = OpentronsHttpClient(ip, port=port)
    try:
        health = client.get_health()
    except OpentronsApiError as exc:
        raise OpentronsApiError(f"无法连接机器人 {ip} 的 HTTP API: {exc}") from exc

    entries = _fetch_log_sources(client, health)
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
