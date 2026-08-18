from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Mapping

from fastapi import HTTPException


DEFAULT_LOCALE = "zh-CN"
SUPPORTED_LOCALES = ("zh-CN", "en-US")

_request_locale: ContextVar[str] = ContextVar("request_locale", default=DEFAULT_LOCALE)


MESSAGES: dict[str, dict[str, str]] = {
    "zh-CN": {
        "auth.authentication_required": "请先登录",
        "auth.csrf_validation_failed": "安全校验失败，请刷新页面后重试",
        "auth.permission_denied": "当前账号无设备控制权限",
        "auth.refresh_token_required": "登录会话已失效，请重新登录",
        "auth.too_many_attempts": "登录尝试过多，请稍后再试",
        "auth.invalid_credentials": "账号或密码错误",
        "auth.configuration_error": "登录服务尚未完成安全配置",
        "integration.authentication_required": "集成接口访问令牌无效或缺失",
        "integration.configuration_error": "集成接口访问令牌尚未正确配置",
        "integration.invalid_cursor": "游标无效或与当前筛选条件不匹配",
        "errors.not_found": "请求的资源不存在",
        "errors.bad_request": "请求参数不正确",
        "errors.service_unavailable": "服务暂时不可用",
        "errors.internal": "服务器处理请求失败",
    },
    "en-US": {
        "auth.authentication_required": "Authentication required",
        "auth.csrf_validation_failed": "Security validation failed. Refresh the page and try again.",
        "auth.permission_denied": "This account cannot use device controls.",
        "auth.refresh_token_required": "Your session has expired. Sign in again.",
        "auth.too_many_attempts": "Too many sign-in attempts. Try again later.",
        "auth.invalid_credentials": "Incorrect account or password",
        "auth.configuration_error": "The sign-in service has not been securely configured.",
        "integration.authentication_required": "The integration access token is missing or invalid.",
        "integration.configuration_error": "The integration access token is not configured correctly.",
        "integration.invalid_cursor": "The cursor is invalid or does not match the current filters.",
        "errors.not_found": "The requested resource was not found.",
        "errors.bad_request": "The request is invalid.",
        "errors.service_unavailable": "The service is temporarily unavailable.",
        "errors.internal": "The server could not complete the request.",
    },
}


def normalize_locale(value: str | None) -> str:
    if not value:
        return DEFAULT_LOCALE
    for entry in value.split(","):
        language = entry.split(";", 1)[0].strip().lower().replace("_", "-")
        if language.startswith("zh"):
            return "zh-CN"
        if language.startswith("en"):
            return "en-US"
    return DEFAULT_LOCALE


def set_request_locale(value: str | None):
    return _request_locale.set(normalize_locale(value))


def reset_request_locale(token) -> None:
    _request_locale.reset(token)


def get_request_locale() -> str:
    return _request_locale.get()


def translate(code: str, params: Mapping[str, Any] | None = None, *, locale: str | None = None) -> str:
    selected = normalize_locale(locale) if locale else get_request_locale()
    template = MESSAGES.get(selected, {}).get(code) or MESSAGES[DEFAULT_LOCALE].get(code) or code
    try:
        return template.format(**dict(params or {}))
    except (KeyError, ValueError):
        return template


def api_error(
    status_code: int,
    code: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    locale: str | None = None,
) -> HTTPException:
    values = dict(params or {})
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": translate(code, values, locale=locale),
            "params": values,
        },
        headers=headers,
    )
