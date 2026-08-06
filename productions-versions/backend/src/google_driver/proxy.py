from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import requests
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from settings import GHELPER_DIR, GOOGLE_API_TIMEOUT_SECONDS


GOOGLE_PROXY_TEST_URL = "https://www.googleapis.com/discovery/v1/apis/drive/v3/rest"


def _load_module(path: Path, module_name: str):
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_skill_config_module():
    return _load_module(GHELPER_DIR / "skill_config.py", "productions_versions_ghelper_skill_config")


def get_proxy_url() -> str | None:
    module = load_skill_config_module()
    config_path = GHELPER_DIR / "skill_config.json"
    if module is None or not hasattr(module, "get_proxy_url"):
        return None
    return module.get_proxy_url(config_path=config_path)


def proxy_mapping(proxy_url: str | None) -> dict[str, str] | None:
    if not proxy_url:
        return None
    return {"http": proxy_url, "https": proxy_url}


def proxy_is_available(proxy_url: str | None) -> bool:
    if not proxy_url:
        return False
    try:
        response = requests.get(
            GOOGLE_PROXY_TEST_URL,
            proxies=proxy_mapping(proxy_url),
            timeout=10,
        )
        response.raise_for_status()
        return True
    except Exception:
        return False


def refresh_best_proxy() -> str | None:
    node_test = _load_module(GHELPER_DIR / "node_test.py", "productions_versions_ghelper_node_test")
    if node_test is None or not hasattr(node_test, "get_best_proxy_and_update_config"):
        return None
    try:
        _, proxy_url = node_test.get_best_proxy_and_update_config(
            max_threads=25,
            update_subscription=True,
            test_url=GOOGLE_PROXY_TEST_URL,
        )
        return proxy_url or get_proxy_url()
    except Exception:
        return None


def select_proxy_url() -> str | None:
    proxy_url = get_proxy_url()
    if proxy_is_available(proxy_url):
        return proxy_url
    refreshed = refresh_best_proxy()
    if proxy_is_available(refreshed):
        return refreshed
    return None


def build_auth_request(proxy_url: str | None = None) -> Request:
    module = load_skill_config_module()
    if proxy_url and module is not None and hasattr(module, "build_google_auth_request"):
        return module.build_google_auth_request(proxy_url=proxy_url)
    return Request()


def apply_oauth_proxy(flow: Any, proxy_url: str | None = None) -> None:
    module = load_skill_config_module()
    if proxy_url and module is not None and hasattr(module, "apply_oauth_flow_proxy"):
        module.apply_oauth_flow_proxy(flow, proxy_url=proxy_url)


def build_google_service(service_name: str, version: str, credentials: Any, proxy_url: str | None = None):
    module = load_skill_config_module()
    if proxy_url and module is not None and hasattr(module, "build_google_service"):
        service = module.build_google_service(
            service_name,
            version,
            credentials,
            proxy_url=proxy_url,
        )
    else:
        service = build(service_name, version, credentials=credentials, cache_discovery=False)
    if hasattr(service, "_http"):
        service._http.timeout = GOOGLE_API_TIMEOUT_SECONDS
    return service
