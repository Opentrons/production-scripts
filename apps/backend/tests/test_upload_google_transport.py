from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from google.oauth2.credentials import Credentials
import pytest
import requests


@pytest.mark.parametrize("proxy_url", ["http://proxy.invalid:8080", ""])
@pytest.mark.parametrize("unauthorized_once", [False, True])
def test_automatic_token_refresh_uses_same_proxy_as_upload(monkeypatch, proxy_url, unauthorized_once):
    path = Path(__file__).resolve().parents[1] / "ghelper-test" / "skill_config.py"
    spec = importlib.util.spec_from_file_location("upload_google_transport", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    token_url = "https://oauth2.googleapis.com/token"
    api_url = "https://sheets.googleapis.com/v4/spreadsheets/test"
    calls = []
    api_calls = 0

    def request(session, method, url, **kwargs):
        nonlocal api_calls
        calls.append((url, dict(session.proxies), kwargs.get("timeout")))
        response = requests.Response()
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        if url == token_url:
            response._content = json.dumps({"access_token": "refreshed", "expires_in": 3600}).encode()
        else:
            assert url == api_url
            api_calls += 1
            if unauthorized_once and api_calls == 1:
                response.status_code = 401
            response._content = b'{"ok": true}'
        return response

    monkeypatch.setattr(requests.Session, "request", request)
    credentials = Credentials(
        token=None, refresh_token="test-refresh", token_uri=token_url,
        client_id="test-client", client_secret="test-secret",
    )
    transport = module.RequestsGoogleApiHttp(credentials, proxy_url=proxy_url, timeout=7)
    response, content = transport.request(api_url)

    assert response.status == 200
    assert json.loads(content) == {"ok": True}
    expected_urls = [token_url, api_url] * (2 if unauthorized_once else 1)
    assert [url for url, _, _ in calls] == expected_urls
    expected_proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else {}
    assert all(proxies == expected_proxies for _, proxies, _ in calls)
    assert all(timeout == 7 for _, _, timeout in calls)
