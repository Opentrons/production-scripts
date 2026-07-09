from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
GHELPER_DIR = Path(PROJECT_ROOT) / "ghelper-test"
GHELPER_CONFIG_PATH = str(GHELPER_DIR / "skill_config.json")
GHELPER_SKILL_CONFIG_PATH = GHELPER_DIR / "skill_config.py"


def _env_flag(name: str, default: bool = True) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}


USE_PROXY = _env_flag("DATA_HANDLER_USE_PROXY", True)
_PROXY_UNSET = object()


def load_skill_config_module():
    if not GHELPER_SKILL_CONFIG_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location(
        "data_handler_ghelper_skill_config",
        GHELPER_SKILL_CONFIG_PATH,
    )
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_ghelper_config(config_path: str | Path = GHELPER_CONFIG_PATH) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as config_file:
        data = json.load(config_file)
    return data if isinstance(data, dict) else {}


def get_proxy_url(config_path: str | Path = GHELPER_CONFIG_PATH) -> str | None:
    if not USE_PROXY:
        return None

    module = load_skill_config_module()
    if module is not None and hasattr(module, "get_proxy_url"):
        return module.get_proxy_url(config_path=config_path)

    proxy = str(load_ghelper_config(config_path).get("proxy", "")).strip()
    return proxy or None


def proxies_from_url(proxy_url: str | None) -> dict[str, str] | None:
    if not proxy_url:
        return None
    return {"http": proxy_url, "https": proxy_url}


def get_proxies(config_path: str | Path = GHELPER_CONFIG_PATH) -> dict[str, str] | None:
    return proxies_from_url(get_proxy_url(config_path))


def build_google_auth_request(proxy_url: str | None | object = _PROXY_UNSET):
    import requests
    from google.auth.transport.requests import Request

    session = requests.Session()
    proxies = get_proxies() if proxy_url is _PROXY_UNSET else proxies_from_url(proxy_url)
    if proxies:
        session.proxies.update(proxies)
    return Request(session=session)


def get_proxy_label(config_path: str | Path = GHELPER_CONFIG_PATH) -> str:
    config = load_ghelper_config(config_path)
    node_name = str(config.get("proxy_node", "")).strip()
    proxy_url = str(config.get("proxy", "")).strip()
    if node_name:
        return node_name
    if not proxy_url:
        return "no proxy"
    try:
        parts = urlsplit(proxy_url)
        if parts.hostname:
            return urlunsplit((parts.scheme, parts.hostname, "", "", ""))
    except Exception:
        pass
    return "configured proxy"


def reload_proxy_config() -> tuple[str | None, dict[str, str] | None]:
    global skill_config, PROXY_URL, PROXIES
    skill_config = load_skill_config_module()
    PROXY_URL = get_proxy_url()
    PROXIES = proxies_from_url(PROXY_URL)
    return PROXY_URL, PROXIES


skill_config = load_skill_config_module()
PROXY_URL = get_proxy_url()
PROXIES = proxies_from_url(PROXY_URL)

BASE_DIR = os.path.dirname(sys.argv[0])
DOWNLOAD_DIR = os.path.join(BASE_DIR, "download")
