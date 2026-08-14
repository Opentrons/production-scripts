"""Remote Flex ODD access via Chrome DevTools Protocol.

Opentrons Flex ODD is an Electron app. When Developer Tools is enabled on the
robot, systemd exposes CDP publicly on port 9223 (proxy to localhost:9222).

Evidence in Opentrons / oe-core:
- opentrons-robot-app-devtools.socket ListenStream=9223
- Electron --remote-debugging-port=9222
- app-shell-odd toggles the socket from ODD Settings → Developer Tools
"""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import json
import time
from typing import Any
from urllib.parse import urlparse, urlunparse

import aiohttp
from fastapi.concurrency import run_in_threadpool

from modules.robots import robots as robot_service

ODD_DEVTOOLS_PORT = 9223
ROBOT_API_PORT = 31950
_PROBE_TIMEOUT_S = 1.6
_SHOT_TIMEOUT_S = 6.0
_DEFAULT_WIDTH = 1024.0
_DEFAULT_HEIGHT = 600.0

_session_lock = asyncio.Lock()
_sessions: dict[str, "_OddCdpSession"] = {}


def rewrite_devtools_ws_url(ws_url: str, host: str, port: int = ODD_DEVTOOLS_PORT) -> str:
    """Rewrite localhost/127.0.0.1 CDP URLs to the robot's public DevTools proxy."""
    parsed = urlparse(ws_url)
    hostname = (parsed.hostname or "").lower()
    if hostname in {"127.0.0.1", "localhost", "::1"} or not hostname:
        netloc = f"{host}:{port}"
        return urlunparse((parsed.scheme or "ws", netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    if parsed.port == 9222:
        netloc = f"{parsed.hostname}:{port}"
        return urlunparse((parsed.scheme or "ws", netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    return ws_url


def _validate_robot_ip(ip: str) -> str:
    value = (ip or "").strip()
    try:
        addr = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError(f"Invalid robot IP: {ip}") from exc
    if addr.is_unspecified or addr.is_multicast:
        raise ValueError(f"Unsupported robot IP: {ip}")
    if not (addr.is_private or addr.is_loopback):
        raise ValueError(f"Only private/LAN robot IPs are allowed: {ip}")
    return value


def _session_key(ip: str, port: int) -> str:
    return f"{ip}:{int(port)}"


async def fetch_json(url: str, timeout_s: float = _PROBE_TIMEOUT_S) -> Any:
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json(content_type=None)


async def probe_odd_devtools(ip: str, port: int = ODD_DEVTOOLS_PORT) -> dict[str, Any]:
    host = _validate_robot_ip(ip)
    origin = f"http://{host}:{port}"
    try:
        version = await fetch_json(f"{origin}/json/version")
        targets = await fetch_json(f"{origin}/json/list")
        if not isinstance(targets, list):
            targets = []
        return {
            "available": True,
            "ip": host,
            "port": port,
            "origin": origin,
            "browser": str((version or {}).get("Browser") or ""),
            "protocol_version": str((version or {}).get("Protocol-Version") or ""),
            "target_count": len(targets),
            "title": _pick_target(targets).get("title") if targets else None,
            "detail": "Developer Tools remote CDP is reachable",
        }
    except Exception as exc:  # noqa: BLE001 - surface probe failure to UI
        return {
            "available": False,
            "ip": host,
            "port": port,
            "origin": origin,
            "browser": None,
            "protocol_version": None,
            "target_count": 0,
            "title": None,
            "detail": str(exc) or "Developer Tools CDP unreachable",
        }


def _pick_target(targets: list[dict[str, Any]]) -> dict[str, Any]:
    for item in targets:
        title = str(item.get("title") or "").lower()
        if "opentrons" in title:
            return item
    for item in targets:
        if item.get("type") == "page":
            return item
    return targets[0]


async def list_odd_devices(robot_api_port: int = ROBOT_API_PORT) -> dict[str, Any]:
    scan = await run_in_threadpool(robot_service.load_robot_scan_cache, robot_api_port, None)
    online = list(scan.get("online_robots") or [])
    probes = await asyncio.gather(
        *[probe_odd_devtools(str(robot.get("ip") or "")) for robot in online if robot.get("ip")],
        return_exceptions=False,
    )
    by_ip = {item["ip"]: item for item in probes}
    devices: list[dict[str, Any]] = []
    for robot in online:
        ip = str(robot.get("ip") or "")
        if not ip:
            continue
        odd = by_ip.get(ip) or {
            "available": False,
            "ip": ip,
            "port": ODD_DEVTOOLS_PORT,
            "detail": "Not probed",
        }
        devices.append(
            {
                "ip": ip,
                "api_port": int(robot.get("port") or robot_api_port),
                "name": robot.get("name") or ip,
                "robot_model": robot.get("robot_model"),
                "robot_type": robot.get("robot_type"),
                "version": robot.get("version"),
                "service_status": robot.get("service_status"),
                "odd_devtools_port": ODD_DEVTOOLS_PORT,
                "odd_available": bool(odd.get("available")),
                "odd_title": odd.get("title"),
                "odd_browser": odd.get("browser"),
                "odd_detail": odd.get("detail"),
                "odd_origin": odd.get("origin") or f"http://{ip}:{ODD_DEVTOOLS_PORT}",
            }
        )
    devices.sort(key=lambda item: (not item["odd_available"], str(item.get("name") or item["ip"])))
    return {
        "devtools_port": ODD_DEVTOOLS_PORT,
        "robot_api_port": robot_api_port,
        "total": len(devices),
        "odd_ready_count": sum(1 for item in devices if item["odd_available"]),
        "devices": devices,
        "hint": (
            "Enable ODD Settings → Developer Tools on the Flex. "
            f"Remote display uses CDP at http://<robot-ip>:{ODD_DEVTOOLS_PORT}."
        ),
    }


class _OddCdpSession:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._http: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._lock = asyncio.Lock()
        self._next_id = 1
        self.width = _DEFAULT_WIDTH
        self.height = _DEFAULT_HEIGHT
        self.title: str | None = None
        self.last_used = time.monotonic()

    async def close(self) -> None:
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        self._ws = None
        if self._http is not None and not self._http.closed:
            await self._http.close()
        self._http = None

    async def ensure(self) -> None:
        self.last_used = time.monotonic()
        if self._ws is not None and not self._ws.closed:
            return
        await self.close()
        origin = f"http://{self.host}:{self.port}"
        targets = await fetch_json(f"{origin}/json/list", timeout_s=_SHOT_TIMEOUT_S)
        if not isinstance(targets, list) or not targets:
            raise RuntimeError("No CDP page targets on robot ODD")
        target = _pick_target(targets)
        self.title = str(target.get("title") or "") or None
        ws_url = target.get("webSocketDebuggerUrl")
        if not isinstance(ws_url, str) or not ws_url:
            raise RuntimeError("CDP target missing webSocketDebuggerUrl")
        ws_url = rewrite_devtools_ws_url(ws_url, self.host, self.port)
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=_SHOT_TIMEOUT_S)
        self._http = aiohttp.ClientSession(timeout=timeout)
        self._ws = await self._http.ws_connect(ws_url, heartbeat=20, autoping=True)
        await self.call("Page.enable")
        await self.call("Runtime.enable")
        await self.refresh_metrics()

    async def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._ws is None or self._ws.closed:
            raise RuntimeError("CDP session is not connected")
        req_id = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {"id": req_id, "method": method}
        if params is not None:
            payload["params"] = params
        await self._ws.send_json(payload)
        while True:
            message = await self._ws.receive()
            if message.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(message.data)
                if data.get("id") != req_id:
                    continue
                if data.get("error"):
                    raise RuntimeError(str(data["error"]))
                return data.get("result") or {}
            if message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
                raise RuntimeError("CDP WebSocket closed")

    async def refresh_metrics(self) -> dict[str, float]:
        try:
            metrics = await self.call("Page.getLayoutMetrics")
            visual = metrics.get("cssVisualViewport") or metrics.get("cssLayoutViewport") or {}
            width = float(visual.get("clientWidth") or visual.get("width") or 0)
            height = float(visual.get("clientHeight") or visual.get("height") or 0)
            if width > 0 and height > 0:
                self.width = width
                self.height = height
        except Exception:
            pass
        return {"width": self.width, "height": self.height}

    async def _wake_if_asleep(self, *, force: bool = False) -> None:
        """Dismiss Flex Touchscreen_SleepScreen (solid dark overlay) before capture."""
        asleep = force
        if not force:
            try:
                result = await self.call(
                    "Runtime.evaluate",
                    {
                        "expression": '!!document.querySelector("[data-testid=\\"Touchscreen_SleepScreen\\]")',
                        "returnByValue": True,
                    },
                )
                asleep = bool((result.get("result") or {}).get("value"))
            except Exception:
                asleep = True
        if not asleep:
            return
        x = max(1.0, self.width / 2.0)
        y = max(1.0, self.height / 2.0)
        await self.call(
            "Input.dispatchTouchEvent",
            {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 0}]},
        )
        await self.call(
            "Input.dispatchTouchEvent",
            {"type": "touchEnd", "touchPoints": []},
        )
        await asyncio.sleep(0.45)

    async def screenshot(self, quality: int = 55) -> bytes:
        async with self._lock:
            await self.ensure()
            await self._wake_if_asleep(force=True)
            result = await self.call(
                "Page.captureScreenshot",
                {
                    "format": "jpeg",
                    "quality": max(20, min(int(quality), 90)),
                },
            )
            data_b64 = result.get("data")
            if not data_b64:
                raise RuntimeError("Empty screenshot from ODD CDP")
            return base64.b64decode(data_b64)

    async def metrics(self) -> dict[str, Any]:
        async with self._lock:
            await self.ensure()
            size = await self.refresh_metrics()
            return {
                "ip": self.host,
                "port": self.port,
                "width": size["width"],
                "height": size["height"],
                "title": self.title,
            }

    async def dispatch_input(self, event: dict[str, Any]) -> dict[str, Any]:
        # Keep this path minimal: every extra CDP round-trip adds click lag, and
        # screenshot polling shares the same session lock.
        async with self._lock:
            await self.ensure()
            event_type = str(event.get("type") or "").strip()
            x = float(event.get("x") or 0)
            y = float(event.get("y") or 0)
            x = max(0.0, min(x, self.width - 1))
            y = max(0.0, min(y, self.height - 1))
            button = str(event.get("button") or "left")
            click_count = int(event.get("clickCount") or 1)
            delta_x = float(event.get("deltaX") or 0)
            delta_y = float(event.get("deltaY") or 0)

            if event_type in {"click", "tap"}:
                await self._mouse("mousePressed", x, y, button, click_count)
                await self._mouse("mouseReleased", x, y, button, click_count)
            elif event_type == "mousedown":
                await self._mouse("mousePressed", x, y, button, click_count)
            elif event_type == "mouseup":
                await self._mouse("mouseReleased", x, y, button, click_count)
            elif event_type == "mousemove":
                await self._mouse("mouseMoved", x, y, button, 0)
            elif event_type == "wheel":
                await self.call(
                    "Input.dispatchMouseEvent",
                    {
                        "type": "mouseWheel",
                        "x": x,
                        "y": y,
                        "deltaX": delta_x,
                        "deltaY": delta_y,
                    },
                )
            elif event_type == "swipe":
                await self._swipe(
                    x=x,
                    y=y,
                    delta_x=delta_x,
                    delta_y=delta_y,
                    steps=int(event.get("steps") or 8),
                )
            else:
                raise ValueError(f"Unsupported ODD input type: {event_type}")

            return {"ok": True, "width": self.width, "height": self.height, "x": x, "y": y}

    async def _swipe(self, x: float, y: float, delta_x: float, delta_y: float, steps: int = 8) -> None:
        step_count = max(3, min(int(steps), 16))
        start_x = max(0.0, min(x, self.width - 1))
        start_y = max(0.0, min(y, self.height - 1))
        end_x = max(0.0, min(start_x + delta_x, self.width - 1))
        end_y = max(0.0, min(start_y + delta_y, self.height - 1))
        await self.call(
            "Input.dispatchTouchEvent",
            {"type": "touchStart", "touchPoints": [{"x": start_x, "y": start_y, "id": 0}]},
        )
        for index in range(1, step_count + 1):
            ratio = index / step_count
            await self.call(
                "Input.dispatchTouchEvent",
                {
                    "type": "touchMove",
                    "touchPoints": [
                        {
                            "x": start_x + (end_x - start_x) * ratio,
                            "y": start_y + (end_y - start_y) * ratio,
                            "id": 0,
                        }
                    ],
                },
            )
        await self.call(
            "Input.dispatchTouchEvent",
            {"type": "touchEnd", "touchPoints": []},
        )

    async def _mouse(self, type_name: str, x: float, y: float, button: str, click_count: int) -> None:
        await self.call(
            "Input.dispatchMouseEvent",
            {
                "type": type_name,
                "x": x,
                "y": y,
                "button": button if type_name != "mouseMoved" else "none",
                "buttons": 1 if type_name in {"mousePressed", "mouseMoved"} and button == "left" else 0,
                "clickCount": max(1, click_count) if type_name != "mouseMoved" else 0,
            },
        )


async def _get_session(ip: str, port: int = ODD_DEVTOOLS_PORT) -> _OddCdpSession:
    host = _validate_robot_ip(ip)
    key = _session_key(host, port)
    async with _session_lock:
        session = _sessions.get(key)
        if session is None:
            session = _OddCdpSession(host, port)
            _sessions[key] = session
        # Drop stale sessions that have not been used recently.
        stale_keys = [
            item_key
            for item_key, item in _sessions.items()
            if item_key != key and time.monotonic() - item.last_used > 120
        ]
        for item_key in stale_keys:
            old = _sessions.pop(item_key, None)
            if old is not None:
                await old.close()
        return session


async def close_odd_session(ip: str, port: int = ODD_DEVTOOLS_PORT) -> None:
    """Release the shared HTTP CDP session so a screencast stream can take the debugger slot."""
    host = _validate_robot_ip(ip)
    key = _session_key(host, port)
    async with _session_lock:
        session = _sessions.pop(key, None)
    if session is not None:
        await session.close()


async def capture_odd_screenshot(ip: str, port: int = ODD_DEVTOOLS_PORT, quality: int = 55) -> bytes:
    session = await _get_session(ip, port)
    try:
        return await session.screenshot(quality=quality)
    except Exception:
        await session.close()
        return await session.screenshot(quality=quality)


async def odd_metrics(ip: str, port: int = ODD_DEVTOOLS_PORT) -> dict[str, Any]:
    session = await _get_session(ip, port)
    try:
        return await session.metrics()
    except Exception:
        await session.close()
        return await session.metrics()


async def odd_input(ip: str, port: int = ODD_DEVTOOLS_PORT, event: dict[str, Any] | None = None) -> dict[str, Any]:
    session = await _get_session(ip, port)
    try:
        return await session.dispatch_input(event or {})
    except Exception:
        await session.close()
        return await session.dispatch_input(event or {})


async def odd_session_info(ip: str, port: int = ODD_DEVTOOLS_PORT) -> dict[str, Any]:
    host = _validate_robot_ip(ip)
    origin = f"http://{host}:{port}"
    version = await fetch_json(f"{origin}/json/version", timeout_s=_SHOT_TIMEOUT_S)
    targets = await fetch_json(f"{origin}/json/list", timeout_s=_SHOT_TIMEOUT_S)
    if not isinstance(targets, list) or not targets:
        raise RuntimeError("No CDP targets")
    target = _pick_target(targets)
    ws_url = rewrite_devtools_ws_url(str(target.get("webSocketDebuggerUrl") or ""), host, port)
    ws_param = ws_url.replace("ws://", "").replace("wss://", "")
    inspector_url = f"{origin}/devtools/inspector.html?ws={ws_param}"
    # Do NOT attach a CDP debugger here — that steals the slot from live screencast
    # and leaves the remote UI black. Dimensions come from screencast metadata instead.
    return {
        "ip": host,
        "port": port,
        "origin": origin,
        "browser": version.get("Browser"),
        "protocol_version": version.get("Protocol-Version"),
        "title": target.get("title"),
        "url": target.get("url"),
        "webSocketDebuggerUrl": ws_url,
        "inspector_url": inspector_url,
        "width": _DEFAULT_WIDTH,
        "height": _DEFAULT_HEIGHT,
    }
