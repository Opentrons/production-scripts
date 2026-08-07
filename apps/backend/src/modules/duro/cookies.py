from __future__ import annotations

import http.cookiejar
import json
import os
import time
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from typing import Any

import requests


class DuroCookieError(ValueError):
    pass


def load_cookie_jar(path: Path) -> requests.cookies.RequestsCookieJar:
    """Load a browser JSON export or Netscape cookies.txt without logging values."""

    cookie_path = Path(path)
    if not cookie_path.exists():
        return requests.cookies.RequestsCookieJar()

    raw = cookie_path.read_text(encoding="utf-8", errors="replace").lstrip()
    if raw.startswith("["):
        return _load_json_cookies(raw)
    if "=" in raw and "\t" not in raw:
        return _load_cookie_header(raw)
    return _load_netscape_cookies(cookie_path)


def cookie_metadata(path: Path) -> list[dict[str, Any]]:
    jar = load_cookie_jar(path)
    return [
        {
            "name": cookie.name,
            "domain": cookie.domain,
            "path": cookie.path,
            "secure": cookie.secure,
            "expires": cookie.expires,
        }
        for cookie in jar
    ]


def save_cookie_jar(path: Path, jar: requests.cookies.RequestsCookieJar) -> None:
    """Persist rotated cookies atomically using the supported JSON export shape."""

    cookie_path = Path(path)
    cookie_path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for cookie in jar:
        item: dict[str, Any] = {
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain or "auth.duro.app",
            "path": cookie.path or "/",
            "secure": bool(cookie.secure),
            "httpOnly": bool(cookie._rest.get("HttpOnly")),
        }
        if cookie.expires is not None:
            item["expirationDate"] = cookie.expires
        payload.append(item)

    temporary_path = cookie_path.with_name(f".{cookie_path.name}.tmp")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(temporary_path, 0o600)
    temporary_path.replace(cookie_path)
    os.chmod(cookie_path, 0o600)


def _load_json_cookies(raw: str) -> requests.cookies.RequestsCookieJar:
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DuroCookieError("Duro cookies JSON 格式错误") from exc
    if not isinstance(items, list):
        raise DuroCookieError("Duro cookies JSON 顶层必须是数组")

    jar = requests.cookies.RequestsCookieJar()
    now = time.time()
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "")
        domain = str(item.get("domain") or "").strip()
        if not name or not domain:
            continue
        expires = _integer(item.get("expirationDate"))
        if expires is not None and expires <= now:
            continue
        jar.set(
            name,
            value,
            domain=domain,
            path=str(item.get("path") or "/"),
            secure=bool(item.get("secure", False)),
            expires=expires,
        )
    return jar


def _load_netscape_cookies(path: Path) -> requests.cookies.RequestsCookieJar:
    source = http.cookiejar.MozillaCookieJar(str(path))
    try:
        source.load(ignore_discard=True, ignore_expires=False)
    except (http.cookiejar.LoadError, OSError) as exc:
        raise DuroCookieError("Duro cookies.txt 不是有效的 JSON 或 Netscape Cookie 文件") from exc

    jar = requests.cookies.RequestsCookieJar()
    for cookie in source:
        jar.set_cookie(cookie)
    return jar


def _load_cookie_header(raw: str) -> requests.cookies.RequestsCookieJar:
    value = raw.strip()
    if value.lower().startswith("cookie:"):
        value = value.split(":", 1)[1].strip()
    parsed = SimpleCookie()
    try:
        parsed.load(value)
    except CookieError as exc:
        raise DuroCookieError("Duro Cookie 请求头格式错误") from exc

    jar = requests.cookies.RequestsCookieJar()
    for name, morsel in parsed.items():
        jar.set(
            name,
            morsel.value,
            domain="auth.duro.app",
            path="/",
            secure=True,
        )
    if not jar:
        raise DuroCookieError("Duro Cookie 请求头中没有可用 Cookie")
    return jar


def _integer(value: Any) -> int | None:
    try:
        return int(float(value)) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
