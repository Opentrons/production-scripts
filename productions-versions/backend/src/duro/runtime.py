from duro.browser_auth import DuroRemoteChromeTokenProvider
from duro.client import DuroClient
from duro.service import DuroService
from settings import (
    DURO_AUTH_URL,
    DURO_REMOTE_CHROME_APP_URL,
    DURO_REMOTE_CHROME_CDP_URL,
    DURO_REMOTE_CHROME_TIMEOUT_SECONDS,
    DURO_TOKEN_REFRESH_MARGIN_SECONDS,
)


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
duro_service = DuroService(duro_client)
