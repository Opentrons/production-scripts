"""MongoDB-backed authentication store (production / non-simulating)."""

from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import Any
from uuid import uuid4

from modules.auth.store import AuthSession, AuthUser, from_timestamp, to_timestamp, utc_now


class MongoAuthStore:
    """Auth users/sessions in MongoDB ProductionsMessage collections."""

    USERS = "auth_users"
    SESSIONS = "auth_sessions"

    def __init__(self, database: Any) -> None:
        self._db = database
        self._lock = RLock()

    def _users(self):
        return self._db[self.USERS]

    def _sessions(self):
        return self._db[self.SESSIONS]

    def initialize(self) -> None:
        with self._lock:
            users = self._users()
            sessions = self._sessions()
            users.create_index("username_key", unique=True)
            sessions.create_index("user_id")
            sessions.create_index("expires_at")

    @staticmethod
    def _username_key(username: str) -> str:
        return username.strip().casefold()

    @classmethod
    def _user_from_doc(cls, document: dict[str, Any] | None) -> AuthUser | None:
        if not document:
            return None
        return AuthUser(
            id=str(document.get("_id") or document.get("id") or ""),
            username=str(document.get("username") or ""),
            display_name=str(document.get("display_name") or ""),
            role=str(document.get("role") or ""),
            password_hash=str(document.get("password_hash") or ""),
            disabled=bool(document.get("disabled")),
            token_version=int(document.get("token_version") or 1),
        )

    @classmethod
    def _session_from_doc(cls, document: dict[str, Any] | None) -> AuthSession | None:
        if not document:
            return None
        revoked = document.get("revoked_at")
        return AuthSession(
            id=str(document.get("_id") or document.get("id") or ""),
            user_id=str(document.get("user_id") or ""),
            refresh_token_hash=str(document.get("refresh_token_hash") or ""),
            expires_at=from_timestamp(str(document["expires_at"])),
            revoked_at=from_timestamp(str(revoked)) if revoked else None,
        )

    def create_user(
        self,
        *,
        username: str,
        display_name: str,
        role: str,
        password_hash: str,
    ) -> AuthUser:
        now = to_timestamp(utc_now())
        user_id = str(uuid4())
        document = {
            "_id": user_id,
            "username": username,
            "username_key": self._username_key(username),
            "display_name": display_name,
            "role": role,
            "password_hash": password_hash,
            "disabled": False,
            "token_version": 1,
            "created_at": now,
            "updated_at": now,
            "last_login_at": None,
        }
        with self._lock:
            self._users().insert_one(document)
        user = self.get_user_by_id(user_id)
        if user is None:
            raise RuntimeError("Failed to create authentication user")
        return user

    def get_user_by_username(self, username: str) -> AuthUser | None:
        with self._lock:
            document = self._users().find_one({"username_key": self._username_key(username)})
        return self._user_from_doc(document)

    def get_user_by_id(self, user_id: str) -> AuthUser | None:
        with self._lock:
            document = self._users().find_one({"_id": user_id})
        return self._user_from_doc(document)

    def mark_login(self, user_id: str) -> None:
        now = to_timestamp(utc_now())
        with self._lock:
            self._users().update_one(
                {"_id": user_id},
                {"$set": {"last_login_at": now, "updated_at": now}},
            )

    def create_session(
        self,
        *,
        session_id: str,
        user_id: str,
        refresh_token_hash: str,
        expires_at: datetime,
        user_agent: str,
        ip_address: str,
    ) -> AuthSession:
        now = to_timestamp(utc_now())
        document = {
            "_id": session_id,
            "user_id": user_id,
            "refresh_token_hash": refresh_token_hash,
            "expires_at": to_timestamp(expires_at),
            "created_at": now,
            "last_used_at": now,
            "revoked_at": None,
            "user_agent": user_agent[:512],
            "ip_address": ip_address[:128],
        }
        with self._lock:
            self._sessions().insert_one(document)
        session = self.get_session(session_id)
        if session is None:
            raise RuntimeError("Failed to create authentication session")
        return session

    def get_session(self, session_id: str) -> AuthSession | None:
        with self._lock:
            document = self._sessions().find_one({"_id": session_id})
        return self._session_from_doc(document)

    def rotate_session(
        self,
        session_id: str,
        *,
        previous_refresh_token_hash: str,
        refresh_token_hash: str,
    ) -> None:
        now = to_timestamp(utc_now())
        with self._lock:
            result = self._sessions().update_one(
                {
                    "_id": session_id,
                    "refresh_token_hash": previous_refresh_token_hash,
                    "revoked_at": None,
                },
                {"$set": {"refresh_token_hash": refresh_token_hash, "last_used_at": now}},
            )
            if getattr(result, "matched_count", 0) != 1:
                raise LookupError("Authentication session is no longer active")

    def revoke_session(self, session_id: str) -> None:
        now = to_timestamp(utc_now())
        with self._lock:
            self._sessions().update_one(
                {"_id": session_id, "revoked_at": None},
                {"$set": {"revoked_at": now}},
            )

    def delete_expired_sessions(self) -> None:
        now = to_timestamp(utc_now())
        with self._lock:
            self._sessions().delete_many({"expires_at": {"$lte": now}})

    def list_users(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._users().find({}))
