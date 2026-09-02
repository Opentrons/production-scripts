from __future__ import annotations

import base64
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials

from core.google.proxy_manager import google_proxy_manager
from core.google.proxy import build_auth_request


GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


class BridgeEmailError(RuntimeError):
    pass


@dataclass(frozen=True)
class BridgeEmailSettings:
    provider: str
    from_address: str
    gmail_token_path: Path
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_use_ssl: bool
    smtp_starttls: bool


class BridgeEmailSender:
    def __init__(self, settings: BridgeEmailSettings) -> None:
        self.settings = settings

    def update_settings(self, settings: BridgeEmailSettings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        if self.settings.provider == "gmail":
            return self.settings.gmail_token_path.is_file()
        return bool(self.settings.smtp_host and self.settings.from_address)

    def send(self, to_address: str, subject: str, body: str) -> None:
        if not to_address:
            raise BridgeEmailError("Email recipient is missing")
        if self.settings.provider == "gmail":
            self._send_gmail(to_address, subject, body)
            return
        self._send_smtp(to_address, subject, body)

    def _message(self, to_address: str, subject: str, body: str) -> EmailMessage:
        message = EmailMessage()
        if self.settings.from_address:
            message["From"] = self.settings.from_address
        message["To"] = to_address
        message["Subject"] = subject
        message.set_content(body)
        return message

    def _send_gmail(self, to_address: str, subject: str, body: str) -> None:
        token_path = self.settings.gmail_token_path
        if not token_path.is_file():
            raise BridgeEmailError("Gmail OAuth token file is not configured")
        try:
            credentials = Credentials.from_authorized_user_file(token_path, [GMAIL_SEND_SCOPE])
            proxy_url, _ = google_proxy_manager.current()
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(build_auth_request(proxy_url))
                token_path.write_text(credentials.to_json(), encoding="utf-8")
            if not credentials.valid:
                raise BridgeEmailError("Gmail OAuth credentials are invalid")
            message = self._message(to_address, subject, body)
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
            session = AuthorizedSession(credentials)
            if proxy_url:
                session.proxies.update({"http": proxy_url, "https": proxy_url})
            response = session.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                json={"raw": raw},
                timeout=60,
            )
        except BridgeEmailError:
            raise
        except Exception as exc:
            raise BridgeEmailError("Gmail delivery failed") from exc
        if response.status_code >= 400:
            raise BridgeEmailError(f"Gmail delivery returned HTTP {response.status_code}")

    def _send_smtp(self, to_address: str, subject: str, body: str) -> None:
        if not self.settings.smtp_host:
            raise BridgeEmailError("SMTP is not configured")
        message = self._message(to_address, subject, body)
        try:
            if self.settings.smtp_use_ssl:
                with smtplib.SMTP_SSL(
                    self.settings.smtp_host,
                    self.settings.smtp_port,
                    timeout=30,
                    context=ssl.create_default_context(),
                ) as server:
                    if self.settings.smtp_username:
                        server.login(self.settings.smtp_username, self.settings.smtp_password)
                    server.send_message(message)
                return
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=30) as server:
                if self.settings.smtp_starttls:
                    server.starttls(context=ssl.create_default_context())
                if self.settings.smtp_username:
                    server.login(self.settings.smtp_username, self.settings.smtp_password)
                server.send_message(message)
        except Exception as exc:
            raise BridgeEmailError("SMTP delivery failed") from exc
