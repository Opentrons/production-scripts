"""Low-latency ODD bridge: browser WebSocket <-> robot CDP screencast + input."""

from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any

import aiohttp
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from modules.agent.protocol_analysis.odd_remote import (
    ODD_DEVTOOLS_PORT,
    _pick_target,
    _validate_robot_ip,
    close_odd_session,
    fetch_json,
    rewrite_devtools_ws_url,
)

_DEFAULT_WIDTH = 1024.0
_DEFAULT_HEIGHT = 600.0


class OddCdpMux:
    """Single CDP connection with response multiplexing + screencast frames."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.width = _DEFAULT_WIDTH
        self.height = _DEFAULT_HEIGHT
        self.title: str | None = None
        self._http: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._frames: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=2)
        self._reader_task: asyncio.Task[None] | None = None
        self._closed = False
        self._send_lock = asyncio.Lock()
        self._last_wake_at = 0.0
        # Prevent the frame loop from repeatedly tapping the ODD center.
        self._wake_cooldown_s = 25.0

    async def connect(self) -> None:
        origin = f"http://{self.host}:{self.port}"
        targets = await fetch_json(f"{origin}/json/list", timeout_s=4.0)
        if not isinstance(targets, list) or not targets:
            raise RuntimeError("No CDP page targets on robot ODD")
        target = _pick_target(targets)
        self.title = str(target.get("title") or "") or None
        ws_url = target.get("webSocketDebuggerUrl")
        if not isinstance(ws_url, str) or not ws_url:
            raise RuntimeError("CDP target missing webSocketDebuggerUrl")
        ws_url = rewrite_devtools_ws_url(ws_url, self.host, self.port)
        self._http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_connect=4))
        self._ws = await self._http.ws_connect(ws_url, heartbeat=20, autoping=True)
        self._reader_task = asyncio.create_task(self._reader_loop(), name=f"odd-cdp-reader-{self.host}")
        await self.call("Page.enable")
        await self.call("Runtime.enable")
        await self._refresh_metrics()

    async def close(self) -> None:
        self._closed = True
        task = self._reader_task
        self._reader_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(RuntimeError("CDP session closed"))
        self._pending.clear()
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        self._ws = None
        if self._http is not None and not self._http.closed:
            await self._http.close()
        self._http = None

    async def _reader_loop(self) -> None:
        assert self._ws is not None
        try:
            while not self._closed:
                message = await self._ws.receive()
                if message.type == aiohttp.WSMsgType.TEXT:
                    payload = json.loads(message.data)
                    req_id = payload.get("id")
                    if req_id is not None:
                        fut = self._pending.pop(int(req_id), None)
                        if fut is not None and not fut.done():
                            if payload.get("error"):
                                fut.set_exception(RuntimeError(str(payload["error"])))
                            else:
                                fut.set_result(payload.get("result") or {})
                        continue
                    method = payload.get("method")
                    params = payload.get("params") or {}
                    if method == "Page.screencastFrame":
                        session_id = params.get("sessionId")
                        if session_id is not None:
                            # ACK promptly so Chromium keeps streaming.
                            asyncio.create_task(self._ack_frame(session_id))
                        metadata = params.get("metadata") or {}
                        if metadata.get("deviceWidth") and metadata.get("deviceHeight"):
                            self.width = float(metadata["deviceWidth"])
                            self.height = float(metadata["deviceHeight"])
                        # Keep only the newest frame to minimize lag.
                        while not self._frames.empty():
                            try:
                                self._frames.get_nowait()
                            except asyncio.QueueEmpty:
                                break
                        try:
                            self._frames.put_nowait(params)
                        except asyncio.QueueFull:
                            pass
                elif message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
                    break
        finally:
            for fut in list(self._pending.values()):
                if not fut.done():
                    fut.set_exception(RuntimeError("CDP WebSocket closed"))
            self._pending.clear()

    async def _ack_frame(self, session_id: int) -> None:
        try:
            await self.call("Page.screencastFrameAck", {"sessionId": session_id})
        except Exception:
            pass

    async def call(self, method: str, params: dict[str, Any] | None = None, timeout_s: float = 5.0) -> dict[str, Any]:
        if self._ws is None or self._ws.closed:
            raise RuntimeError("CDP session is not connected")
        req_id = self._next_id
        self._next_id += 1
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[req_id] = fut
        message: dict[str, Any] = {"id": req_id, "method": method}
        if params is not None:
            message["params"] = params
        async with self._send_lock:
            await self._ws.send_json(message)
        try:
            return await asyncio.wait_for(fut, timeout=timeout_s)
        except Exception:
            self._pending.pop(req_id, None)
            raise

    async def _refresh_metrics(self) -> None:
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

    async def start_screencast(self, quality: int = 45, max_width: int = 1024, max_height: int = 600) -> None:
        await self.call(
            "Page.startScreencast",
            {
                "format": "jpeg",
                "quality": max(20, min(int(quality), 80)),
                "maxWidth": int(max_width),
                "maxHeight": int(max_height),
                "everyNthFrame": 1,
            },
        )

    async def stop_screencast(self) -> None:
        try:
            await self.call("Page.stopScreencast")
        except Exception:
            pass

    async def next_frame(self, timeout_s: float = 2.0) -> dict[str, Any]:
        return await asyncio.wait_for(self._frames.get(), timeout=timeout_s)

    async def is_sleep_screen(self) -> bool:
        """Flex ODD paints Touchscreen_SleepScreen as a solid dark overlay when idle."""
        result = await self.call(
            "Runtime.evaluate",
            {
                "expression": '!!document.querySelector("[data-testid=\\"Touchscreen_SleepScreen\\]")',
                "returnByValue": True,
            },
            timeout_s=2.0,
        )
        value = (result.get("result") or {}).get("value")
        return bool(value)

    async def _tap_center(self) -> None:
        x = max(1.0, self.width / 2.0)
        y = max(1.0, self.height / 2.0)
        await self.call(
            "Input.dispatchTouchEvent",
            {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 0}]},
            timeout_s=2.0,
        )
        await self.call(
            "Input.dispatchTouchEvent",
            {"type": "touchEnd", "touchPoints": []},
            timeout_s=2.0,
        )

    async def wake_display(self, *, force: bool = False, ignore_cooldown: bool = False) -> bool:
        """Tap the center of the ODD to dismiss sleep. Returns True if a wake tap was sent.

        force=True is for the initial connect path only. The streaming loop must use
        force=False so we never spam taps on a dark-but-awake UI (tiny JPEGs look like sleep).
        """
        now = time.monotonic()
        if not ignore_cooldown and (now - self._last_wake_at) < self._wake_cooldown_s:
            return False
        asleep = True if force else False
        if not force:
            try:
                asleep = await self.is_sleep_screen()
            except Exception:
                # Do not tap when detection fails — that caused endless mid-screen clicks.
                return False
        if not asleep:
            return False
        self._last_wake_at = now
        await self._tap_center()
        await asyncio.sleep(0.45)
        # Second tap only if the sleep overlay is still present (some builds need two).
        try:
            if await self.is_sleep_screen():
                await self._tap_center()
                await asyncio.sleep(0.35)
        except Exception:
            pass
        return True

    async def capture_jpeg(self, quality: int = 45) -> bytes:
        result = await self.call(
            "Page.captureScreenshot",
            {
                "format": "jpeg",
                "quality": max(20, min(int(quality), 80)),
            },
            timeout_s=4.0,
        )
        data_b64 = result.get("data")
        if not isinstance(data_b64, str) or not data_b64:
            raise RuntimeError("Empty screenshot from ODD CDP")
        return base64.b64decode(data_b64)

    async def dispatch_input(self, event: dict[str, Any]) -> dict[str, Any]:
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
        """One-shot touch swipe — better for ODD lists than laggy drag streams."""
        step_count = max(3, min(int(steps), 16))
        start_x = max(0.0, min(x, self.width - 1))
        start_y = max(0.0, min(y, self.height - 1))
        end_x = max(0.0, min(start_x + delta_x, self.width - 1))
        end_y = max(0.0, min(start_y + delta_y, self.height - 1))
        await self.call(
            "Input.dispatchTouchEvent",
            {"type": "touchStart", "touchPoints": [{"x": start_x, "y": start_y, "id": 0}]},
            timeout_s=2.0,
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
                timeout_s=2.0,
            )
        await self.call(
            "Input.dispatchTouchEvent",
            {"type": "touchEnd", "touchPoints": []},
            timeout_s=2.0,
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
            timeout_s=2.0,
        )


async def run_odd_stream(websocket: WebSocket, ip: str, port: int = ODD_DEVTOOLS_PORT, quality: int = 45) -> None:
    host = _validate_robot_ip(ip)
    # Chromium allows one active debugger client; drop the HTTP screenshot session first.
    await close_odd_session(host, port)
    mux = OddCdpMux(host, port)
    forward_task: asyncio.Task[None] | None = None
    try:
        await mux.connect()
        # One wake on connect only — SleepScreen is a solid #16212d that looks black.
        await mux.wake_display(force=True, ignore_cooldown=True)
        await mux.start_screencast(quality=quality)
        await websocket.send_json(
            {
                "type": "ready",
                "ip": host,
                "port": port,
                "width": mux.width,
                "height": mux.height,
                "title": mux.title,
            }
        )

        async def _send_jpeg(jpeg: bytes) -> None:
            if websocket.client_state != WebSocketState.CONNECTED:
                return
            header = (
                b"OJPG"
                + int(mux.width).to_bytes(2, "big")
                + int(mux.height).to_bytes(2, "big")
            )
            await websocket.send_bytes(header + jpeg)

        # Push one screenshot immediately so UI is not stuck waiting for a dirty screencast.
        try:
            await _send_jpeg(await mux.capture_jpeg(quality=quality))
        except Exception:
            pass

        async def forward_frames() -> None:
            idle_checks = 0
            while True:
                try:
                    frame = await mux.next_frame(timeout_s=1.25)
                except asyncio.TimeoutError:
                    # Electron ODD often emits screencast only on dirty frames.
                    # Fall back to screenshots so a static UI still updates.
                    idle_checks += 1
                    # Rare sleep-screen recovery only (DOM-confirmed + cooldown). Never force-tap
                    # on tiny JPEGs — dark awake screens also compress small and caused click loops.
                    if idle_checks % 8 == 1:
                        try:
                            await mux.wake_display(force=False)
                        except Exception:
                            pass
                    try:
                        jpeg = await mux.capture_jpeg(quality=quality)
                    except Exception:
                        continue
                    await _send_jpeg(jpeg)
                    continue
                idle_checks = 0
                data_b64 = frame.get("data")
                if not data_b64:
                    continue
                try:
                    jpeg = base64.b64decode(data_b64)
                except Exception:
                    continue
                await _send_jpeg(jpeg)

        forward_task = asyncio.create_task(forward_frames(), name=f"odd-frame-forward-{host}")

        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            text = message.get("text")
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            msg_type = str(payload.get("type") or "")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "ts": time.time()})
            elif msg_type == "input":
                try:
                    event = dict(payload)
                    # Client envelope uses type=input; actual CDP event is eventType.
                    event["type"] = str(payload.get("eventType") or payload.get("event") or "click")
                    result = await mux.dispatch_input(event)
                    await websocket.send_json({"type": "input_ok", **result})
                except Exception as exc:  # noqa: BLE001
                    await websocket.send_json({"type": "input_error", "message": str(exc)})
            elif msg_type == "set_quality":
                q = int(payload.get("quality") or quality)
                await mux.stop_screencast()
                await mux.start_screencast(quality=q)
                await websocket.send_json({"type": "quality_ok", "quality": q})
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_json({"type": "error", "message": str(exc)})
            except Exception:
                pass
        raise
    finally:
        if forward_task is not None:
            forward_task.cancel()
            try:
                await forward_task
            except asyncio.CancelledError:
                pass
        await mux.close()
