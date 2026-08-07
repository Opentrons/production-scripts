import os
import subprocess
import time
from urllib.parse import urlparse

import requests

from modules.duro.browser_auth import DuroRemoteChromeTokenProvider
from modules.duro.client import DuroClient
from modules.duro.service import DuroService
from core.config import (
    DURO_AUTH_URL,
    DURO_CACHE_PATH,
    DURO_REMOTE_CHROME_AUTO_START,
    DURO_REMOTE_CHROME_APP_URL,
    DURO_REMOTE_CHROME_CDP_URL,
    DURO_REMOTE_CHROME_TIMEOUT_SECONDS,
    DURO_TOKEN_REFRESH_MARGIN_SECONDS,
    API_ROOT,
)


def ensure_duro_remote_chrome_running() -> bool:
    if not DURO_REMOTE_CHROME_CDP_URL:
        return False
    try:
        requests.get(f"{DURO_REMOTE_CHROME_CDP_URL}/json/version", timeout=2).raise_for_status()
        return True
    except requests.RequestException:
        pass
    parsed = urlparse(DURO_REMOTE_CHROME_CDP_URL)
    if not DURO_REMOTE_CHROME_AUTO_START or parsed.hostname not in {"127.0.0.1", "localhost"}:
        return False
    script_path = API_ROOT / "scripts" / "start_duro_remote_chrome.sh"
    if not script_path.exists():
        return False
    environment = os.environ.copy()
    environment["DURO_REMOTE_CHROME_PORT"] = str(parsed.port or 9222)
    subprocess.Popen(
        [str(script_path)],
        cwd=API_ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(20):
        try:
            requests.get(f"{DURO_REMOTE_CHROME_CDP_URL}/json/version", timeout=1).raise_for_status()
            return True
        except requests.RequestException:
            time.sleep(0.5)
    return False


duro_browser_token_provider = (
    DuroRemoteChromeTokenProvider(
        cdp_url=DURO_REMOTE_CHROME_CDP_URL,
        app_url=DURO_REMOTE_CHROME_APP_URL,
        auth_url=DURO_AUTH_URL,
        timeout_seconds=DURO_REMOTE_CHROME_TIMEOUT_SECONDS,
        refresh_margin_seconds=DURO_TOKEN_REFRESH_MARGIN_SECONDS,
    )
    if DURO_REMOTE_CHROME_CDP_URL
    else None
)
duro_client = DuroClient(browser_token_provider=duro_browser_token_provider)
duro_service = DuroService(duro_client, cache_path=DURO_CACHE_PATH)
