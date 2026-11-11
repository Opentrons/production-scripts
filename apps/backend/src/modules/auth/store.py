from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def from_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


@dataclass(frozen=True)
class AuthUser:
    id: str
    username: str
    display_name: str
    role: str
    password_hash: str
    disabled: bool
    token_version: int


@dataclass(frozen=True)
class AuthSession:
    id: str
    user_id: str
    refresh_token_hash: str
    expires_at: datetime
    revoked_at: datetime | None


class AuthStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = RLock()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS auth_reset_rates (
                    key TEXT PRIMARY KEY, times TEXT NOT NULL, expires REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_password_resets (
                    email TEXT PRIMARY KEY, digest TEXT NOT NULL, expires REAL NOT NULL,
                    attempts INTEGER NOT NULL, token_version INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    disabled INTEGER NOT NULL DEFAULT 0,
                    token_version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login_at TEXT
                );

                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    refresh_token_hash TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT NOT NULL,
                    revoked_at TEXT,
                    user_agent TEXT NOT NULL DEFAULT '',
                    ip_address TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(user_id) REFERENCES auth_users(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id
                    ON auth_sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at
                    ON auth_sessions(expires_at);
                """
            )

    @staticmethod
    def _user(row: sqlite3.Row | None) -> AuthUser | None:
        if row is None:
            return None
        return AuthUser(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            role=row["role"],
            password_hash=row["password_hash"],
            disabled=bool(row["disabled"]),
            token_version=int(row["token_version"]),
        )

    @staticmethod
    def _session(row: sqlite3.Row | None) -> AuthSession | None:
        if row is None:
            return None
        return AuthSession(
            id=row["id"],
            user_id=row["user_id"],
            refresh_token_hash=row["refresh_token_hash"],
            expires_at=from_timestamp(row["expires_at"]),
            revoked_at=from_timestamp(row["revoked_at"]) if row["revoked_at"] else None,
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
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO auth_users (
                    id, username, display_name, role, password_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, username, display_name, role, password_hash, now, now),
            )
        user = self.get_user_by_id(user_id)
        if user is None:
            raise RuntimeError("Failed to create authentication user")
        return user

    def get_user_by_username(self, username: str) -> AuthUser | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM auth_users WHERE username = ? COLLATE NOCASE",
                (username,),
            ).fetchone()
        return self._user(row)

    def get_user_by_id(self, user_id: str) -> AuthUser | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM auth_users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return self._user(row)

    def mark_login(self, user_id: str) -> None:
        now = to_timestamp(utc_now())
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE auth_users SET last_login_at = ?, updated_at = ? WHERE id = ?",
                (now, now, user_id),
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
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO auth_sessions (
                    id, user_id, refresh_token_hash, expires_at, created_at,
                    last_used_at, user_agent, ip_address
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    user_id,
                    refresh_token_hash,
                    to_timestamp(expires_at),
                    now,
                    now,
                    user_agent[:512],
                    ip_address[:128],
                ),
            )
        session = self.get_session(session_id)
        if session is None:
            raise RuntimeError("Failed to create authentication session")
        return session

    def get_session(self, session_id: str) -> AuthSession | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM auth_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return self._session(row)

    def rotate_session(
        self,
        session_id: str,
        *,
        previous_refresh_token_hash: str,
        refresh_token_hash: str,
    ) -> None:
        now = to_timestamp(utc_now())
        with self._lock, self._connect() as connection:
            result = connection.execute(
                """
                UPDATE auth_sessions
                SET refresh_token_hash = ?, last_used_at = ?
                WHERE id = ? AND refresh_token_hash = ? AND revoked_at IS NULL
                """,
                (refresh_token_hash, now, session_id, previous_refresh_token_hash),
            )
            if result.rowcount != 1:
                raise LookupError("Authentication session is no longer active")

    def revoke_session(self, session_id: str) -> None:
        now = to_timestamp(utc_now())
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (now, session_id),
            )

    def delete_expired_sessions(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "DELETE FROM auth_sessions WHERE expires_at <= ?",
                (to_timestamp(utc_now()),),
            )

    def list_accounts(self) -> list[AuthUser]:
        with self._lock, self._connect() as connection:
            return [self._user(row) for row in connection.execute('SELECT * FROM auth_users ORDER BY username')]

    def update_role(self, user_id: str, role: str) -> AuthUser:
        with self._lock, self._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT * FROM auth_users WHERE id = ?', (user_id,)).fetchone()
            if row is None:
                raise LookupError('Account not found')
            count = connection.execute("SELECT COUNT(*) FROM auth_users WHERE role = 'admin' AND disabled = 0").fetchone()[0]
            if row['role'] == 'admin' and role != 'admin' and count <= 1:
                raise ValueError('Cannot remove the last administrator')
            if row['role'] != role:
                connection.execute('UPDATE auth_users SET role = ?, token_version = token_version + 1, updated_at = ? WHERE id = ?',
                                   (role, to_timestamp(utc_now()), user_id))
        return self.get_user_by_id(user_id)

    def reserve_reset(self, email: str, digest: str, ip: str, now: float) -> AuthUser | None:
        import json
        with self._lock, self._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('DELETE FROM auth_reset_rates WHERE expires <= ?', (now,))
            for key, maximum in ((f'email:{email}', 5), (f'ip:{ip}', 20)):
                row = connection.execute('SELECT times FROM auth_reset_rates WHERE key = ?', (key,)).fetchone()
                times = [t for t in json.loads(row[0]) if now - t < 3600] if row else []
                if len(times) >= maximum or (key.startswith('email:') and times and now - times[-1] < 60):
                    raise ValueError('Please wait before requesting another code')
                connection.execute('INSERT OR REPLACE INTO auth_reset_rates VALUES (?, ?, ?)',
                                   (key, json.dumps(times + [now]), now + 3600))
            connection.execute('DELETE FROM auth_password_resets WHERE expires <= ?', (now,))
            user = self._user(connection.execute('SELECT * FROM auth_users WHERE username = ? COLLATE NOCASE AND disabled = 0', (email,)).fetchone())
            if user:
                connection.execute('INSERT OR REPLACE INTO auth_password_resets VALUES (?, ?, ?, ?, ?)',
                                   (email, digest, now + 600, 0, user.token_version))
            return user

    def cancel_reset(self, email: str, digest: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute('DELETE FROM auth_password_resets WHERE email = ? AND digest = ?', (email, digest))

    def confirm_reset(self, email: str, digest: str, password_hash: str, now: float) -> bool:
        import hmac
        with self._lock, self._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            reset = connection.execute('SELECT * FROM auth_password_resets WHERE email = ? AND expires > ? AND attempts < 5', (email, now)).fetchone()
            if reset is None:
                return False
            connection.execute('UPDATE auth_password_resets SET attempts = attempts + 1 WHERE email = ?', (email,))
            if not hmac.compare_digest(reset['digest'], digest):
                return False
            result = connection.execute('UPDATE auth_users SET password_hash = ?, token_version = token_version + 1, updated_at = ? WHERE username = ? COLLATE NOCASE AND disabled = 0 AND token_version = ?',
                                        (password_hash, to_timestamp(utc_now()), email, reset['token_version']))
            connection.execute('DELETE FROM auth_password_resets WHERE email = ?', (email,))
            return result.rowcount == 1
