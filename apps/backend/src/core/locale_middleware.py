from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from core.i18n import get_request_locale, reset_request_locale, set_request_locale


class LocaleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = set_request_locale(request.headers.get("Accept-Language"))
        try:
            response = await call_next(request)
            response.headers["Content-Language"] = get_request_locale()
            return response
        finally:
            reset_request_locale(token)
