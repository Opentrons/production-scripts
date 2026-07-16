"""Shared local configuration for the performance score skill."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SKILL_CONFIG_PATH = SCRIPT_DIR / "skill_config.json"


def load_skill_config(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path or DEFAULT_SKILL_CONFIG_PATH)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as config_file:
        data = json.load(config_file)
    if not isinstance(data, dict):
        raise ValueError(f"Skill config must contain a JSON object: {path}")
    return data


def get_proxy_url(
    config_path: str | Path | None = None,
    explicit_proxy: str | None = None,
) -> str | None:
    if explicit_proxy is not None:
        proxy = explicit_proxy.strip()
    else:
        proxy = str(load_skill_config(config_path).get("proxy", "")).strip()
    return proxy or None


def requests_proxies(
    config_path: str | Path | None = None,
    explicit_proxy: str | None = None,
) -> dict[str, str] | None:
    proxy = get_proxy_url(config_path, explicit_proxy)
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def build_google_auth_request(proxy_url: str | None = None):
    import requests
    from google.auth.transport.requests import Request

    session = requests.Session()
    proxies = requests_proxies(explicit_proxy=proxy_url)
    if proxies:
        session.proxies.update(proxies)
    return Request(session=session)


def apply_oauth_flow_proxy(flow, proxy_url: str | None = None) -> None:
    proxies = requests_proxies(explicit_proxy=proxy_url)
    if proxies and hasattr(flow, "oauth2session"):
        flow.oauth2session.proxies.update(proxies)


class RequestsGoogleApiResponse:
    """Adapter for googleapiclient when using requests-backed HTTP."""

    def __init__(self, response):
        self._response = response
        self.status = response.status_code
        self.reason = response.reason

    def __contains__(self, key: str) -> bool:
        return key in {"status", "reason"} or key in self._response.headers

    def __getitem__(self, key: str) -> str:
        if key == "status":
            return str(self.status)
        if key == "reason":
            return self.reason
        return self._response.headers[key]

    def get(self, key: str, default: Any = None) -> Any:
        if key == "status":
            return str(self.status)
        if key == "reason":
            return self.reason
        return self._response.headers.get(key, default)

    def info(self):
        return self

    def items(self):
        return self._response.headers.items()


class RequestsGoogleApiHttp:
    """requests-backed HTTP adapter so Google APIs can use HTTPS proxies."""

    def __init__(self, credentials, proxy_url: str | None = None, timeout: int = 60):
        from google.auth.transport.requests import AuthorizedSession

        self.session = AuthorizedSession(credentials)
        proxies = requests_proxies(explicit_proxy=proxy_url)
        if proxies:
            self.session.proxies.update(proxies)
        self.timeout = timeout

    def request(
        self,
        uri: str,
        method: str = "GET",
        body: bytes | str | None = None,
        headers: dict[str, str] | None = None,
        redirections: int = 5,
        connection_type=None,
        **kwargs,
    ):
        response = self.session.request(
            method=method,
            url=uri,
            data=body,
            headers=headers or {},
            timeout=self.timeout,
            allow_redirects=redirections > 0,
        )
        return RequestsGoogleApiResponse(response), response.content


def build_google_service(
    service_name: str,
    version: str,
    credentials,
    *,
    proxy_url: str | None = None,
):
    from googleapiclient.discovery import build

    if not proxy_url:
        return build(service_name, version, credentials=credentials)

    return build(
        service_name,
        version,
        http=RequestsGoogleApiHttp(credentials, proxy_url=proxy_url),
    )
