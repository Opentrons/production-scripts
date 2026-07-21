from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone

import pytest

from duro.browser_auth import DuroRemoteChromeError, DuroRemoteChromeTokenProvider


def make_token(expires_at: datetime) -> str:
    def encode(value: dict[str, object]) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{encode({'alg': 'none'})}.{encode({'exp': int(expires_at.timestamp())})}.signature"


class FakePage:
    def __init__(self, results: list[dict[str, object]]) -> None:
        self.results = results
        self.call_count = 0

    def evaluate(self, script: str, arguments: dict[str, str]):
        result = self.results[min(self.call_count, len(self.results) - 1)]
        self.call_count += 1
        return result


class FakeRemoteChromeProvider(DuroRemoteChromeTokenProvider):
    def __init__(self, page: FakePage) -> None:
        super().__init__(cdp_url="http://chrome:9222")
        self.fake_page = page

    def _ensure_page(self) -> FakePage:
        return self.fake_page


def test_remote_chrome_provider_caches_access_token_until_forced() -> None:
    token = make_token(datetime.now(timezone.utc) + timedelta(hours=1))
    page = FakePage([{"status": 200, "data": {"access_token": token}}])
    provider = FakeRemoteChromeProvider(page)
    try:
        first = provider.get_access_token()
        second = provider.get_access_token()
        forced = provider.get_access_token(force=True)
    finally:
        provider.close()

    assert first == token
    assert second == token
    assert forced == token
    assert page.call_count == 2


def test_remote_chrome_provider_reports_logged_out_session() -> None:
    page = FakePage([{"status": 401, "data": None}])
    provider = FakeRemoteChromeProvider(page)
    try:
        with pytest.raises(DuroRemoteChromeError, match="重新登录"):
            provider.get_access_token()
    finally:
        provider.close()
