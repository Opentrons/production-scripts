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
            self._db['auth_password_resets'].create_index('expires_at', expireAfterSeconds=0)
            self._db['auth_reset_rates'].create_index('expires_at', expireAfterSeconds=0)

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

    def list_accounts(self) -> list[AuthUser]:
        return [self._user_from_doc(row) for row in self._users().find({}).sort('username', 1)]

    def update_role(self, user_id: str, role: str) -> AuthUser:
        from pymongo import ReturnDocument
        from pymongo.errors import DuplicateKeyError
        from datetime import timedelta
        locks = self._db['auth_locks']
        owner = str(uuid4())
        try:
            locks.find_one_and_update(
                {'_id': 'roles', 'expires_at': {'$lte': utc_now()}},
                {'$set': {'owner': owner, 'expires_at': utc_now() + timedelta(seconds=30)}},
                upsert=True, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError as exc:
            raise ValueError('Another role change is in progress; please retry') from exc
        try:
            user = self.get_user_by_id(user_id)
            if user is None:
                raise LookupError('Account not found')
            if user.role == 'admin' and role != 'admin' and self._users().count_documents({'role': 'admin', 'disabled': False}) <= 1:
                raise ValueError('Cannot remove the last administrator')
            if user.role != role:
                self._users().update_one({'_id': user_id}, {'$set': {'role': role, 'updated_at': to_timestamp(utc_now())}, '$inc': {'token_version': 1}})
            return self.get_user_by_id(user_id)
        finally:
            locks.delete_one({'_id': 'roles', 'owner': owner})

    def reserve_reset(self, email: str, digest: str, ip: str, now: float) -> AuthUser | None:
        from pymongo.errors import DuplicateKeyError
        # Fixed hourly windows and an independent email cooldown. Atomic updates
        # enforce limits across all API workers; no in-memory security state.
        rates = self._db['auth_reset_rates']
        for key, maximum in ((f'email:{email}', 5), (f'ip:{ip}', 20)):
            identifier = f'{key}:{int(now // 3600)}'
            rates.update_one({'_id': identifier}, {'$setOnInsert': {'count': 0, 'expires_at': datetime.fromtimestamp(now + 7200, tz=utc_now().tzinfo)}}, upsert=True)
            result = rates.update_one({'_id': identifier, 'count': {'$lt': maximum}}, {'$inc': {'count': 1}})
            if result.modified_count != 1:
                raise ValueError('Please wait before requesting another code')
        try:
            rates.update_one({'_id': f'cooldown:{email}', 'until': {'$lte': now}},
                {'$set': {'until': now + 60, 'expires_at': datetime.fromtimestamp(now + 3600, tz=utc_now().tzinfo)}}, upsert=True)
        except DuplicateKeyError as exc:
            raise ValueError('Please wait before requesting another code') from exc
        user = self.get_user_by_username(email)
        if user and not user.disabled:
            self._db['auth_password_resets'].replace_one({'_id': email}, {
                '_id': email, 'digest': digest, 'expires': now + 600, 'attempts': 0,
                'token_version': user.token_version,
                'expires_at': datetime.fromtimestamp(now + 600, tz=utc_now().tzinfo)}, upsert=True)
            return user
        return None

    def cancel_reset(self, email: str, digest: str) -> None:
        self._db['auth_password_resets'].delete_one({'_id': email, 'digest': digest})

    def confirm_reset(self, email: str, digest: str, password_hash: str, now: float) -> bool:
        import hmac
        resets = self._db['auth_password_resets']
        reset = resets.find_one_and_update({'_id': email, 'expires': {'$gt': now}, 'attempts': {'$lt': 5}}, {'$inc': {'attempts': 1}})
        if not reset or not hmac.compare_digest(reset['digest'], digest):
            return False
        # Only one competing confirmation can consume a code.
        claimed = resets.delete_one({'_id': email, 'digest': digest})
        if claimed.deleted_count != 1:
            return False
        result = self._users().update_one({'username_key': self._username_key(email), 'disabled': False,
            'token_version': reset['token_version']}, {'$set': {'password_hash': password_hash,
            'updated_at': to_timestamp(utc_now())}, '$inc': {'token_version': 1}})
        return result.modified_count == 1
