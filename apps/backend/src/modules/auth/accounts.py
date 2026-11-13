"""Administrator accounts and single-use email password recovery."""

import hashlib
import hmac
import os
import re
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Literal
from sqlite3 import IntegrityError

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from pymongo.errors import DuplicateKeyError

from modules.auth.dependencies import get_auth_service, require_auth_context
from modules.auth.models import AuthUserResponse
from modules.auth.service import AuthService, PASSWORD_HASH

router = APIRouter()
Role = Literal['admin', 'engineer', 'operator', 'guest']
ACCOUNT_EMAIL_SENDER = 'software.sz@opentrons.com'


class EmailRequest(BaseModel):
    email: str = Field(max_length=254)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value):
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}", value):
            raise ValueError('A valid email address is required')
        return value


class CreateAccount(EmailRequest):
    role: Role = 'operator'


class ChangeRole(BaseModel):
    role: Role


class ResetPassword(EmailRequest):
    code: str = Field(pattern=r'^\d{6}$')
    password: str = Field(min_length=12, max_length=256)


def administrator(context=Depends(require_auth_context)):
    if context.user.role != 'admin':
        raise HTTPException(403, 'Administrator access required')
    return context


def public_user(user):
    return AuthUserResponse(**{k: getattr(user, k) for k in ('id', 'username', 'display_name', 'role')})


@router.get('/accounts', dependencies=[Depends(administrator)])
def accounts(service: AuthService = Depends(get_auth_service)):
    return [public_user(u) for u in service.store.list_accounts()]


@router.post('/accounts', dependencies=[Depends(administrator)], status_code=201)
def create_account(payload: CreateAccount, service: AuthService = Depends(get_auth_service)):
    try:
        return public_user(service.store.create_user(username=payload.email,
            display_name=payload.email.split('@')[0], role=payload.role,
            password_hash=PASSWORD_HASH.hash(payload.email.split('@')[0])))
    except (ValueError, IntegrityError, DuplicateKeyError) as exc:
        raise HTTPException(409, "Account already exists") from exc


@router.patch('/accounts/{user_id}', dependencies=[Depends(administrator)])
def change_role(user_id: str, payload: ChangeRole, service: AuthService = Depends(get_auth_service)):
    try:
        return public_user(service.store.update_role(user_id, payload.role))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


def smtp_config():
    host = os.getenv('PRODUCTION_PLATFORM_SMTP_HOST', '')
    sender = os.getenv('PRODUCTION_PLATFORM_SMTP_FROM', '').strip() or ACCOUNT_EMAIL_SENDER
    if sender.casefold() != ACCOUNT_EMAIL_SENDER:
        raise HTTPException(503, 'Account email sender must be software.sz@opentrons.com')
    if not host:
        raise HTTPException(503, 'Password recovery email is not configured')
    return host, ACCOUNT_EMAIL_SENDER


def email_provider():
    provider = os.getenv('PRODUCTION_PLATFORM_AUTH_EMAIL_PROVIDER', 'smtp').strip().lower()
    if provider == 'smtp':
        smtp_config()
    elif provider == 'gmail':
        token_path = os.getenv('PRODUCTION_PLATFORM_AUTH_GMAIL_TOKEN_PATH', '').strip()
        if not token_path or not Path(token_path).expanduser().is_file():
            raise HTTPException(503, 'Password recovery Gmail authorization is not configured')
    else:
        raise HTTPException(503, 'Unsupported password recovery email provider')
    return provider


def gmail_sender():
    from modules.bridge_tokens.emailer import BridgeEmailSender, BridgeEmailSettings
    return BridgeEmailSender(BridgeEmailSettings(
        provider='gmail',
        # Gmail uses the identity of the explicitly configured OAuth grant.
        # Never label another mailbox's token as the software.sz SMTP sender.
        from_address='',
        gmail_token_path=Path(os.environ['PRODUCTION_PLATFORM_AUTH_GMAIL_TOKEN_PATH']).expanduser(),
        smtp_host='', smtp_port=587, smtp_username='', smtp_password='',
        smtp_use_ssl=False, smtp_starttls=True,
    ))


def send_code(email, code):
    subject = 'Productions password reset code'
    body = (f'Your password reset code is {code}. It expires in 10 minutes.\n'
            'If you did not request this, ignore this email.')
    if email_provider() == 'gmail':
        gmail_sender().send(email, subject, body)
        return
    host, sender = smtp_config()
    message = EmailMessage()
    message['From'], message['To'] = sender, email
    message['Subject'] = subject
    message.set_content(body)
    port = int(os.getenv('PRODUCTION_PLATFORM_SMTP_PORT', '587'))
    transport = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
    tls_options = {'context': ssl.create_default_context()} if port == 465 else {}
    with transport(host, port, timeout=15, **tls_options) as smtp:
        if port != 465:
            smtp.starttls(context=ssl.create_default_context())
        username = os.getenv('PRODUCTION_PLATFORM_SMTP_USERNAME', '')
        if username:
            smtp.login(username, os.environ['PRODUCTION_PLATFORM_SMTP_PASSWORD'])
        smtp.send_message(message)


def code_hash(service, email, code):
    return hmac.new(service._require_secret().encode(), f'{email}:{code}'.encode(), hashlib.sha256).hexdigest()


@router.post('/password-reset/request')
def request_code(payload: EmailRequest, request: Request, service: AuthService = Depends(get_auth_service)):
    from modules.auth.routes import _client_ip
    email_provider()
    email = payload.email.casefold()
    code = f'{secrets.randbelow(1000000):06d}'
    digest = code_hash(service, email, code)
    now = time.time()
    try:
        user = service.store.reserve_reset(email, digest, _client_ip(request), now)
    except ValueError as exc:
        raise HTTPException(429, str(exc)) from exc
    if user:
        try:
            send_code(user.username, code)
        except Exception as exc:
            service.store.cancel_reset(email, digest)
            raise HTTPException(503, 'Unable to send recovery email') from exc
    return {'message': 'If this account exists, a verification code has been sent.'}


@router.post('/password-reset/confirm')
def reset_password(payload: ResetPassword, service: AuthService = Depends(get_auth_service)):
    email = payload.email.casefold()
    digest = code_hash(service, email, payload.code)
    valid = service.store.confirm_reset(email, digest, service.hash_password(payload.password), time.time())
    if not valid:
        raise HTTPException(400, 'Invalid or expired verification code')
    return {'success': True}
