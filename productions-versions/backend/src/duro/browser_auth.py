from __future__ import annotations

import asyncio
import base64
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any


class DuroRemoteChromeError(RuntimeError):
    pass


class DuroRemoteChromeTokenProvider:
    """Obtain Duro access tokens inside a logged-in Chrome over CDP.

    Playwright's sync API is thread-affine.  A single-worker executor keeps the
    CDP connection and all page operations on one dedicated thread while the
    FastAPI sync routes may run on different worker threads.
    """

    def __init__(
        self,
        cdp_url: str,
        app_url: str = "https://mfg.duro.app/dashboard",
        auth_url: str = "https://auth.duro.app",
        timeout_seconds: int = 30,
        refresh_margin_seconds: int = 60,
    ) -> None:
        self.cdp_url = cdp_url.rstrip("/")
        self.app_url = app_url
        self.auth_url = auth_url.rstrip("/")
        self.timeout_seconds = max(1, timeout_seconds)
        self.refresh_margin_seconds = max(0, refresh_margin_seconds)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="duro-remote-chrome")
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Any = None
        self._prefer_low_level_cdp = False
        self._connected = False
        self._access_token = ""
        self._access_token_expires_at: datetime | None = None
        self._last_error = ""
        self._last_success_at: datetime | None = None
        self._auto_refresh_thread: threading.Thread | None = None
        self._auto_refresh_stop = threading.Event()

    @property
    def configured(self) -> bool:
        return bool(self.cdp_url)

    def get_access_token(self, force: bool = False) -> str:
        if not self.configured:
            return ""
        future = self._executor.submit(self._get_access_token_on_worker, force)
        try:
            token = future.result(timeout=self.timeout_seconds + 10)
            self._last_error = ""
            self._last_success_at = datetime.now(timezone.utc)
            return token
        except DuroRemoteChromeError:
            self._last_error = str(future.exception()) if future.done() and future.exception() else "Remote Chrome 刷新失败"
            raise
        except Exception as exc:
            self._last_error = str(exc)
            raise DuroRemoteChromeError(f"Remote Chrome 获取 Duro token 失败: {exc}") from exc

    def start_auto_refresh(self, interval_seconds: int = 30) -> None:
        if self._auto_refresh_thread and self._auto_refresh_thread.is_alive():
            return
        self._auto_refresh_stop.clear()
        self._auto_refresh_thread = threading.Thread(
            target=self._auto_refresh_loop,
            args=(max(5, interval_seconds),),
            name="duro-token-auto-refresh",
            daemon=True,
        )
        self._auto_refresh_thread.start()

    def stop_auto_refresh(self) -> None:
        self._auto_refresh_stop.set()
        if self._auto_refresh_thread and self._auto_refresh_thread.is_alive():
            self._auto_refresh_thread.join(timeout=2)
        self._auto_refresh_thread = None

    def status(self) -> dict[str, Any]:
        expires_at = self._access_token_expires_at or (
            self._token_expiry(self._access_token) if self._access_token else None
        )
        return {
            "connected": self._connected,
            "token_valid": bool(self._access_token) and (
                expires_at is None or expires_at > datetime.now(timezone.utc)
            ),
            "token_expires_at": expires_at,
            "last_success_at": self._last_success_at,
            "last_error": self._last_error,
            "auto_refresh_active": bool(
                self._auto_refresh_thread and self._auto_refresh_thread.is_alive()
            ),
        }

    def close(self) -> None:
        if getattr(self, "_executor", None) is None:
            return
        try:
            self.stop_auto_refresh()
            self._executor.submit(self._reset_connection).result(timeout=self.timeout_seconds)
        finally:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None  # type: ignore[assignment]

    def _auto_refresh_loop(self, interval_seconds: int) -> None:
        while not self._auto_refresh_stop.is_set():
            try:
                self.get_access_token()
            except DuroRemoteChromeError:
                pass
            self._auto_refresh_stop.wait(interval_seconds)

    def _get_access_token_on_worker(self, force: bool) -> str:
        if not force and self._cached_token_is_valid():
            return self._access_token
        if self._prefer_low_level_cdp:
            result = self._evaluate_refresh_via_cdp()
        else:
            try:
                page = self._ensure_page()
                result = page.evaluate(
                    """
                    async ({ authUrl }) => {
                      const response = await fetch(`${authUrl}/api/v1/refresh_token`, {
                        method: 'GET',
                        credentials: 'include',
                        headers: { accept: '*/*' },
                      });
                      const text = await response.text();
                      let data = null;
                      if (text) {
                        try { data = JSON.parse(text); } catch (_) { data = null; }
                      }
                      return { status: response.status, data };
                    }
                    """,
                    {"authUrl": self.auth_url},
                )
            except Exception as exc:
                self._reset_connection()
                self._prefer_low_level_cdp = True
                try:
                    result = self._evaluate_refresh_via_cdp()
                except DuroRemoteChromeError as cdp_exc:
                    raise cdp_exc from exc

        if not isinstance(result, dict):
            raise DuroRemoteChromeError("Remote Chrome 返回了无效的 Duro refresh 结果")
        status = int(result.get("status") or 0)
        data = result.get("data")
        if status in {401, 403}:
            raise DuroRemoteChromeError(
                "Remote Chrome 的 Duro 登录会话已失效，请在专用 Chrome 窗口重新登录"
            )
        if status < 200 or status >= 300:
            raise DuroRemoteChromeError(f"Remote Chrome 刷新 Duro token 失败: HTTP {status}")
        if not isinstance(data, dict):
            raise DuroRemoteChromeError("Duro refresh 响应缺少 JSON 数据")

        token = str(data.get("access_token") or "").strip()
        if not token:
            raise DuroRemoteChromeError("Duro refresh 响应缺少 access_token")
        self._access_token = token
        self._access_token_expires_at = self._response_expiry(data, token)
        return token

    def _evaluate_refresh_via_cdp(self) -> dict[str, Any]:
        """Run the refresh call through the page target's raw CDP session.

        Chrome can expose a valid page through Target.getTargets while
        Playwright's high-level Page object is temporarily blank or detached.
        Attaching to the target directly avoids navigating the user's tab and
        keeps token refresh working across those Chrome/Playwright mismatches.
        """

        try:
            return asyncio.run(self._evaluate_refresh_via_cdp_async())
        except DuroRemoteChromeError:
            raise
        except Exception as exc:
            self._connected = False
            raise DuroRemoteChromeError(
                f"Remote Chrome 底层 CDP refresh 失败: {exc}"
            ) from exc

    async def _evaluate_refresh_via_cdp_async(self) -> dict[str, Any]:
        from playwright.async_api import async_playwright

        playwright: Any = None
        browser: Any = None
        session: Any = None
        attached_session_id = ""
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.connect_over_cdp(
                self.cdp_url,
                timeout=self.timeout_seconds * 1000,
            )
            session = await browser.new_browser_cdp_session()
            target_infos = (await session.send("Target.getTargets")).get("targetInfos", [])
            target = next(
                (
                    item
                    for item in target_infos
                    if item.get("type") == "page"
                    and "mfg.duro.app" in str(item.get("url") or "")
                ),
                None,
            )
            if target is None:
                raise DuroRemoteChromeError(
                    "Remote Chrome 中没有已打开的 Duro 页面，请先打开并登录 Duro"
                )

            attached = await session.send(
                "Target.attachToTarget",
                {"targetId": target["targetId"], "flatten": False},
            )
            attached_session_id = str(attached.get("sessionId") or "")
            if not attached_session_id:
                raise DuroRemoteChromeError("Remote Chrome 无法附加到 Duro 页面")

            command_id = 1
            loop = asyncio.get_running_loop()
            response_future: asyncio.Future[dict[str, Any]] = loop.create_future()

            def handle_target_message(event: dict[str, Any]) -> None:
                if event.get("sessionId") != attached_session_id:
                    return
                try:
                    message = json.loads(str(event.get("message") or "{}"))
                except json.JSONDecodeError:
                    return
                if message.get("id") == command_id and not response_future.done():
                    response_future.set_result(message)

            session.on("Target.receivedMessageFromTarget", handle_target_message)
            auth_url = json.dumps(self.auth_url)
            expression = f"""
                (async () => {{
                  const authUrl = {auth_url};
                  const response = await fetch(`${{authUrl}}/api/v1/refresh_token`, {{
                    method: 'GET',
                    credentials: 'include',
                    headers: {{ accept: '*/*' }},
                  }});
                  const text = await response.text();
                  let data = null;
                  if (text) {{
                    try {{ data = JSON.parse(text); }} catch (_) {{ data = null; }}
                  }}
                  return {{ status: response.status, data }};
                }})()
            """
            await session.send(
                "Target.sendMessageToTarget",
                {
                    "sessionId": attached_session_id,
                    "message": json.dumps(
                        {
                            "id": command_id,
                            "method": "Runtime.evaluate",
                            "params": {
                                "expression": expression,
                                "awaitPromise": True,
                                "returnByValue": True,
                            },
                        }
                    ),
                },
            )
            response = await asyncio.wait_for(
                response_future,
                timeout=self.timeout_seconds,
            )
            if response.get("error"):
                raise DuroRemoteChromeError(
                    f"Remote Chrome CDP 执行失败: {response['error']}"
                )
            evaluation = response.get("result") or {}
            if evaluation.get("exceptionDetails"):
                raise DuroRemoteChromeError(
                    f"Remote Chrome CDP 页面执行失败: {evaluation['exceptionDetails']}"
                )
            remote_result = evaluation.get("result") or {}
            value = remote_result.get("value")
            if not isinstance(value, dict):
                raise DuroRemoteChromeError("Remote Chrome CDP 返回了无效的 refresh 结果")
            self._connected = True
            return value
        except DuroRemoteChromeError:
            self._connected = False
            raise
        except Exception as exc:
            self._connected = False
            raise DuroRemoteChromeError(
                f"Remote Chrome 底层 CDP refresh 失败: {exc}"
            ) from exc
        finally:
            if session is not None and attached_session_id:
                try:
                    await session.send(
                        "Target.detachFromTarget",
                        {"sessionId": attached_session_id},
                    )
                except Exception:
                    pass
            if session is not None:
                try:
                    await session.detach()
                except Exception:
                    pass
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    pass
            if playwright is not None:
                try:
                    await playwright.stop()
                except Exception:
                    pass

    def _ensure_page(self) -> Any:
        if self._page is not None and not self._page.is_closed():
            return self._page

        try:
            from playwright.sync_api import sync_playwright

            if self._playwright is None:
                self._playwright = sync_playwright().start()
            if self._browser is None or not self._browser.is_connected():
                self._browser = self._playwright.chromium.connect_over_cdp(
                    self.cdp_url,
                    timeout=self.timeout_seconds * 1000,
                )
            contexts = self._browser.contexts
            context = contexts[0] if contexts else self._browser.new_context()
            page = next(
                (
                    candidate
                    for candidate in context.pages
                    if "mfg.duro.app" in candidate.url and not candidate.is_closed()
                ),
                None,
            )
            if page is None:
                page = next((candidate for candidate in context.pages if not candidate.is_closed()), None)
            if page is None:
                page = context.new_page()
            if "mfg.duro.app" not in page.url:
                page.goto(
                    self.app_url,
                    wait_until="domcontentloaded",
                    timeout=self.timeout_seconds * 1000,
                )
            self._page = page
            self._connected = True
            return page
        except DuroRemoteChromeError:
            raise
        except Exception as exc:
            self._reset_connection()
            raise DuroRemoteChromeError(
                f"无法连接 Remote Chrome {self.cdp_url}: {exc}"
            ) from exc

    def _cached_token_is_valid(self) -> bool:
        if not self._access_token:
            return False
        expires_at = self._access_token_expires_at or self._token_expiry(self._access_token)
        if expires_at is None:
            return True
        return expires_at > datetime.now(timezone.utc) + timedelta(
            seconds=self.refresh_margin_seconds
        )

    def _response_expiry(self, body: dict[str, Any], token: str) -> datetime | None:
        value = body.get("expires_at_seconds")
        try:
            seconds = int(value)
        except (TypeError, ValueError):
            return self._token_expiry(token)
        now = datetime.now(timezone.utc)
        if seconds > int(now.timestamp()):
            return datetime.fromtimestamp(seconds, timezone.utc)
        return now + timedelta(seconds=max(0, seconds))

    @staticmethod
    def _token_expiry(token: str) -> datetime | None:
        try:
            payload_segment = token.split(".")[1]
            padding = "=" * (-len(payload_segment) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_segment + padding))
            expires_at = payload.get("exp")
            return datetime.fromtimestamp(int(expires_at), timezone.utc) if expires_at else None
        except (IndexError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def _reset_connection(self) -> None:
        self._page = None
        self._browser = None
        self._connected = False
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
