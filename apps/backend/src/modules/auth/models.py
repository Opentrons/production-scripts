from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class AuthUserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    role: str


class AuthSessionResponse(BaseModel):
    user: AuthUserResponse
    access_expires_at: str
    session_expires_at: str


class AuthStatusResponse(BaseModel):
    authenticated: bool
    user: AuthUserResponse


class LogoutResponse(BaseModel):
    success: bool = True
