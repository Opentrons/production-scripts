from __future__ import annotations

import base64
import json
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
        self._access_token = ""
        self._access_token_expires_at: datetime | None = None

    @property
    def configured(self) -> bool:
        return bool(self.cdp_url)

    def get_access_token(self, force: bool = False) -> str:
        if not self.configured:
            return ""
        future = self._executor.submit(self._get_access_token_on_worker, force)
        try:
            return future.result(timeout=self.timeout_seconds + 10)
        except DuroRemoteChromeError:
            raise
        except Exception as exc:
            raise DuroRemoteChromeError(f"Remote Chrome 获取 Duro token 失败: {exc}") from exc

    def close(self) -> None:
        if getattr(self, "_executor", None) is None:
            return
        try:
            self._executor.submit(self._reset_connection).result(timeout=self.timeout_seconds)
        finally:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None  # type: ignore[assignment]

    def _get_access_token_on_worker(self, force: bool) -> str:
        if not force and self._cached_token_is_valid():
            return self._access_token
        page = self._ensure_page()
        try:
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
            raise DuroRemoteChromeError(f"Remote Chrome 执行 Duro refresh 失败: {exc}") from exc

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
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
