"""Auth store factory: MongoDB outside simulating, SQLite inside simulating."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol

import core.config as setting
from core.persistence import get_message_database, storage_backend
from modules.auth.mongo_store import MongoAuthStore
from modules.auth.store import AuthSession, AuthStore, AuthUser


class AuthStoreProtocol(Protocol):
    def initialize(self) -> None: ...

    def create_user(
        self,
        *,
        username: str,
        display_name: str,
        role: str,
        password_hash: str,
    ) -> AuthUser: ...

    def get_user_by_username(self, username: str) -> AuthUser | None: ...

    def get_user_by_id(self, user_id: str) -> AuthUser | None: ...

    def mark_login(self, user_id: str) -> None: ...

    def create_session(
        self,
        *,
        session_id: str,
        user_id: str,
        refresh_token_hash: str,
        expires_at: Any,
        user_agent: str,
        ip_address: str,
    ) -> AuthSession: ...

    def get_session(self, session_id: str) -> AuthSession | None: ...

    def rotate_session(
        self,
        session_id: str,
        *,
        previous_refresh_token_hash: str,
        refresh_token_hash: str,
    ) -> None: ...

    def revoke_session(self, session_id: str) -> None: ...

    def delete_expired_sessions(self) -> None: ...


def resolve_auth_sqlite_path() -> Path:
    """SQLite auth path used in simulating mode (and as migration source)."""
    configured = os.getenv("PRODUCTION_PLATFORM_AUTH_DB_PATH", "").strip()
    if configured:
        return Path(configured)
    if setting.use_sqlite_persistence():
        return setting.DB_SIMULATING_DIR / "auth.sqlite3"
    return setting.AUTH_DB_PATH


def create_auth_store() -> AuthStoreProtocol:
    if storage_backend() == "sqlite":
        return AuthStore(resolve_auth_sqlite_path())
    return MongoAuthStore(get_message_database())
