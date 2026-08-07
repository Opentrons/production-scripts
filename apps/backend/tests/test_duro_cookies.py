from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from modules.duro.cookies import cookie_metadata, load_cookie_jar, save_cookie_jar


def test_loads_browser_json_cookie_export_without_expired_entries(tmp_path: Path) -> None:
    path = tmp_path / "cookies.txt"
    path.write_text(
        json.dumps(
            [
                {
                    "name": "auth_session",
                    "value": "secret-value",
                    "domain": "auth.duro.app",
                    "path": "/",
                    "secure": True,
                    "expirationDate": (
                        datetime.now(timezone.utc) + timedelta(hours=1)
                    ).timestamp(),
                },
                {
                    "name": "expired",
                    "value": "old-value",
                    "domain": "auth.duro.app",
                    "path": "/",
                    "expirationDate": (
                        datetime.now(timezone.utc) - timedelta(hours=1)
                    ).timestamp(),
                },
            ]
        ),
        encoding="utf-8",
    )

    jar = load_cookie_jar(path)
    metadata = cookie_metadata(path)

    assert jar.get("auth_session", domain="auth.duro.app", path="/") == "secret-value"
    assert jar.get("expired", domain="auth.duro.app", path="/") is None
    assert metadata[0]["name"] == "auth_session"
    assert "value" not in metadata[0]


def test_loads_netscape_cookie_export(tmp_path: Path) -> None:
    path = tmp_path / "cookies.txt"
    expires = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
    path.write_text(
        "# Netscape HTTP Cookie File\n"
        f"auth.duro.app\tFALSE\t/\tTRUE\t{expires}\tauth_session\tsecret-value\n",
        encoding="utf-8",
    )

    jar = load_cookie_jar(path)

    assert jar.get("auth_session", domain="auth.duro.app", path="/") == "secret-value"


def test_loads_raw_cookie_request_header(tmp_path: Path) -> None:
    path = tmp_path / "cookies.txt"
    path.write_text(
        "refresh_token=refresh-value; fs_uid=analytics-value",
        encoding="utf-8",
    )

    jar = load_cookie_jar(path)

    assert jar.get("refresh_token", domain="auth.duro.app", path="/") == "refresh-value"
    assert jar.get("fs_uid", domain="auth.duro.app", path="/") == "analytics-value"


def test_persists_rotated_cookie_jar_as_private_json(tmp_path: Path) -> None:
    path = tmp_path / "cookies.txt"
    jar = load_cookie_jar(tmp_path / "missing")
    jar.set("refresh_token", "new-value", domain="auth.duro.app", path="/", secure=True)

    save_cookie_jar(path, jar)
    reloaded = load_cookie_jar(path)

    assert reloaded.get("refresh_token", domain="auth.duro.app", path="/") == "new-value"
    assert path.stat().st_mode & 0o777 == 0o600
