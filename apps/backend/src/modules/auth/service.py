from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from modules.auth.store import AuthSession, AuthStore, AuthUser, utc_now


JWT_ALGORITHM = "HS256"
PASSWORD_HASH = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = PASSWORD_HASH.hash("production-platform-invalid-password")
VALID_ROLES = {"admin", "operator", "viewer"}


class AuthenticationError(Exception):
    pass


class AuthenticationConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class IssuedSession:
    user: AuthUser
    access_token: str
    refresh_token: str
    csrf_token: str
    access_expires_at: datetime
    session_expires_at: datetime


class AuthService:
    def __init__(
        self,
        *,
        db_path: Path,
        jwt_secret: str,
        issuer: str,
        audience: str,
        access_token_minutes: int,
        refresh_token_hours: int,
    ) -> None:
        self.store = AuthStore(db_path)
        self.jwt_secret = jwt_secret
        self.issuer = issuer
        self.audience = audience
        self.access_token_minutes = access_token_minutes
        self.refresh_token_hours = refresh_token_hours

    def initialize(self) -> None:
        self.store.initialize()
        self.store.delete_expired_sessions()

    def _require_secret(self) -> str:
        if len(self.jwt_secret) < 32:
            raise AuthenticationConfigurationError(
                "PRODUCTION_PLATFORM_AUTH_JWT_SECRET must contain at least 32 characters"
            )
        return self.jwt_secret

    @staticmethod
    def hash_password(password: str) -> str:
        if len(password) < 12:
            raise ValueError("Password must contain at least 12 characters")
        return PASSWORD_HASH.hash(password)

    def create_user(
        self,
        *,
        username: str,
        password: str,
        display_name: str = "",
        role: str = "operator",
    ) -> AuthUser:
        normalized_username = username.strip()
        if len(normalized_username) < 3 or len(normalized_username) > 64:
            raise ValueError("Username must contain between 3 and 64 characters")
        normalized_role = role.strip().lower()
        if normalized_role not in VALID_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(sorted(VALID_ROLES))}")
        self.store.initialize()
        return self.store.create_user(
            username=normalized_username,
            display_name=display_name.strip() or normalized_username,
            role=normalized_role,
            password_hash=self.hash_password(password),
        )

    def authenticate(self, username: str, password: str) -> AuthUser:
        self.store.initialize()
        user = self.store.get_user_by_username(username.strip())
        password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
        try:
            password_valid = PASSWORD_HASH.verify(password, password_hash)
        except Exception:
            password_valid = False
        if user is None or not password_valid or user.disabled:
            raise AuthenticationError("Invalid username or password")
        return user

    def _encode(self, claims: dict[str, Any]) -> str:
        return jwt.encode(claims, self._require_secret(), algorithm=JWT_ALGORITHM)

    def _decode(self, token: str, token_type: str) -> dict[str, Any]:
        try:
            claims = jwt.decode(
                token,
                self._require_secret(),
                algorithms=[JWT_ALGORITHM],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["sub", "sid", "jti", "iat", "nbf", "exp", "iss", "aud", "type"]},
            )
        except (InvalidTokenError, AuthenticationConfigurationError) as exc:
            if isinstance(exc, AuthenticationConfigurationError):
                raise
            raise AuthenticationError("Invalid or expired authentication token") from exc
        if claims.get("type") != token_type:
            raise AuthenticationError("Invalid authentication token type")
        return claims

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _access_token(
        self,
        *,
        user: AuthUser,
        session_id: str,
        csrf_token: str,
        now: datetime,
    ) -> tuple[str, datetime]:
        expires_at = now + timedelta(minutes=self.access_token_minutes)
        return self._encode(
            {
                "sub": user.id,
                "sid": session_id,
                "jti": str(uuid4()),
                "username": user.username,
                "role": user.role,
                "token_version": user.token_version,
                "csrf": csrf_token,
                "type": "access",
                "iat": now,
                "nbf": now,
                "exp": expires_at,
                "iss": self.issuer,
                "aud": self.audience,
            }
        ), expires_at

    def _refresh_token(
        self,
        *,
        user: AuthUser,
        session_id: str,
        now: datetime,
        expires_at: datetime,
    ) -> str:
        return self._encode(
            {
                "sub": user.id,
                "sid": session_id,
                "jti": str(uuid4()),
                "token_version": user.token_version,
                "type": "refresh",
                "iat": now,
                "nbf": now,
                "exp": expires_at,
                "iss": self.issuer,
                "aud": self.audience,
            }
        )

    def issue_session(self, user: AuthUser, *, user_agent: str, ip_address: str) -> IssuedSession:
        now = utc_now()
        session_expires_at = now + timedelta(hours=self.refresh_token_hours)
        session_id = str(uuid4())
        csrf_token = secrets.token_urlsafe(32)
        refresh_token = self._refresh_token(
            user=user,
            session_id=session_id,
            now=now,
            expires_at=session_expires_at,
        )
        access_token, access_expires_at = self._access_token(
            user=user,
            session_id=session_id,
            csrf_token=csrf_token,
            now=now,
        )
        self.store.create_session(
            session_id=session_id,
            user_id=user.id,
            refresh_token_hash=self._token_hash(refresh_token),
            expires_at=session_expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.store.mark_login(user.id)
        return IssuedSession(
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
            access_expires_at=access_expires_at,
            session_expires_at=session_expires_at,
        )

    def login(self, username: str, password: str, *, user_agent: str, ip_address: str) -> IssuedSession:
        return self.issue_session(
            self.authenticate(username, password),
            user_agent=user_agent,
            ip_address=ip_address,
        )

    @staticmethod
    def _active_session(session: AuthSession | None) -> AuthSession:
        if session is None or session.revoked_at is not None or session.expires_at <= utc_now():
            raise AuthenticationError("Authentication session is no longer active")
        return session

    def verify_access_token(self, token: str) -> tuple[AuthUser, dict[str, Any]]:
        claims = self._decode(token, "access")
        session = self._active_session(self.store.get_session(str(claims["sid"])))
        user = self.store.get_user_by_id(str(claims["sub"]))
        if (
            user is None
            or user.disabled
            or session.user_id != user.id
            or int(claims.get("token_version", 0)) != user.token_version
        ):
            raise AuthenticationError("Authentication user is no longer active")
        return user, claims

    def refresh(self, refresh_token: str) -> IssuedSession:
        claims = self._decode(refresh_token, "refresh")
        session_id = str(claims["sid"])
        session = self._active_session(self.store.get_session(session_id))
        if not secrets.compare_digest(session.refresh_token_hash, self._token_hash(refresh_token)):
            self.store.revoke_session(session_id)
            raise AuthenticationError("Refresh token has already been used")
        user = self.store.get_user_by_id(str(claims["sub"]))
        if (
            user is None
            or user.disabled
            or session.user_id != user.id
            or int(claims.get("token_version", 0)) != user.token_version
        ):
            self.store.revoke_session(session_id)
            raise AuthenticationError("Authentication user is no longer active")

        now = utc_now()
        csrf_token = secrets.token_urlsafe(32)
        next_refresh_token = self._refresh_token(
            user=user,
            session_id=session_id,
            now=now,
            expires_at=session.expires_at,
        )
        access_token, access_expires_at = self._access_token(
            user=user,
            session_id=session_id,
            csrf_token=csrf_token,
            now=now,
        )
        try:
            self.store.rotate_session(
                session_id,
                previous_refresh_token_hash=self._token_hash(refresh_token),
                refresh_token_hash=self._token_hash(next_refresh_token),
            )
        except LookupError as exc:
            self.store.revoke_session(session_id)
            raise AuthenticationError("Refresh token has already been used") from exc
        return IssuedSession(
            user=user,
            access_token=access_token,
            refresh_token=next_refresh_token,
            csrf_token=csrf_token,
            access_expires_at=access_expires_at,
            session_expires_at=session.expires_at,
        )

    def revoke_refresh_token(self, refresh_token: str) -> None:
        try:
            claims = self._decode(refresh_token, "refresh")
        except (AuthenticationError, AuthenticationConfigurationError):
            return
        self.store.revoke_session(str(claims["sid"]))


def isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()
