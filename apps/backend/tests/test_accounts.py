from concurrent.futures import ThreadPoolExecutor
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import accounts
from modules.auth.bootstrap import ADMIN_EMAILS, seed_administrators
from modules.auth.dependencies import get_auth_service, CSRF_COOKIE_NAME
from modules.auth.routes import router
from modules.auth.service import AuthService, AuthenticationError, PASSWORD_HASH
from modules.auth.store import AuthStore


@pytest.fixture(params=['sqlite', 'mongodb'])
def service(request, tmp_path):
    if request.param == 'mongodb':
        import mongomock
        from modules.auth.mongo_store import MongoAuthStore
        store = MongoAuthStore(mongomock.MongoClient().auth_test)
    else:
        store = AuthStore(tmp_path / 'auth.sqlite3')
    svc = AuthService(store=store, jwt_secret='test-secret-' * 4, issuer='test',
                      audience='test', access_token_minutes=5, refresh_token_hours=24)
    svc.initialize()
    return svc


@pytest.fixture
def client(service, monkeypatch):
    monkeypatch.setenv('PRODUCTION_PLATFORM_SMTP_HOST', 'smtp.example.com')
    monkeypatch.setenv('PRODUCTION_PLATFORM_SMTP_FROM', 'noreply@example.com')
    app = FastAPI()
    app.include_router(router, prefix='/api')
    app.dependency_overrides[get_auth_service] = lambda: service
    return TestClient(app)


def user(service, role='admin', email='admin@example.com'):
    return service.create_user(username=email, password='correct-password-123', role=role)


def login(client, email='admin@example.com'):
    result = client.post('/api/auth/login', json={'username': email, 'password': 'correct-password-123'})
    assert result.status_code == 200
    return {'X-CSRF-Token': client.cookies.get(CSRF_COOKIE_NAME)}


def test_bootstrap_preserves_passwords_and_roles(service):
    seed_administrators(service.store)
    assert len(service.store.list_accounts()) == 5
    for email in ADMIN_EMAILS:
        assert service.authenticate(email.upper(), email.split('@')[0]).role == 'admin'
    account = service.store.get_user_by_username(ADMIN_EMAILS[0])
    service.store.update_role(account.id, 'engineer')
    previous_hash = account.password_hash
    seed_administrators(service.store)
    account = service.store.get_user_by_id(account.id)
    assert account.password_hash == previous_hash
    assert account.role == 'engineer'


def test_accounts_admin_csrf_duplicates_and_roles(service, client):
    user(service)
    assert client.get('/api/auth/accounts').status_code == 401
    headers = login(client)
    payload = {'email': 'Engineer.Name@example.com', 'role': 'engineer'}
    assert client.post('/api/auth/accounts', json=payload).status_code == 403
    created = client.post('/api/auth/accounts', json=payload, headers=headers)
    assert created.status_code == 201
    assert 'password_hash' not in created.json()
    assert service.authenticate(payload['email'].lower(), 'Engineer.Name').role == 'engineer'
    payload['email'] = payload['email'].lower()
    assert client.post('/api/auth/accounts', json=payload, headers=headers).status_code == 409
    assert client.post('/api/auth/accounts', json={'email': 'bad', 'role': 'engineer'}, headers=headers).status_code == 422
    assert client.post('/api/auth/accounts', json={'email': 'new@example.com', 'role': 'superuser'}, headers=headers).status_code == 422
    changed = client.patch('/api/auth/accounts/' + created.json()['id'], json={'role': 'guest'}, headers=headers)
    assert changed.status_code == 200
    assert changed.json()['role'] == 'guest'
    assert all('password_hash' not in item for item in client.get('/api/auth/accounts').json())


@pytest.mark.parametrize('role', ['engineer', 'operator', 'guest', 'viewer', 'device_operator'])
def test_other_roles_cannot_manage_accounts(service, client, role):
    account = user(service, role=role)
    headers = login(client)
    assert client.get('/api/auth/accounts').status_code == 403
    assert client.post('/api/auth/accounts', json={'email': 'new@example.com'}, headers=headers).status_code == 403
    assert client.patch('/api/auth/accounts/' + account.id, json={'role': 'admin'}, headers=headers).status_code == 403


def test_last_admin_and_role_revocation(service):
    account = user(service)
    with pytest.raises(ValueError, match='last administrator'):
        service.store.update_role(account.id, 'guest')
    other = user(service, 'engineer', 'other@example.com')
    session = service.issue_session(other, user_agent='', ip_address='')
    service.store.update_role(other.id, 'operator')
    with pytest.raises(AuthenticationError):
        service.verify_access_token(session.access_token)
    with pytest.raises(AuthenticationError):
        service.refresh(session.refresh_token)


def test_reset_email_roundtrip_and_replay(service, client, monkeypatch):
    account = user(service)
    session = service.issue_session(account, user_agent='', ip_address='')
    sent = []
    monkeypatch.setattr(accounts, 'send_code', lambda email, code: sent.append((email, code)))
    response = client.post('/api/auth/password-reset/request', json={'email': account.username.upper()})
    assert response.status_code == 200
    assert len(sent) == 1
    assert sent[0][1] not in response.text
    payload = {'email': account.username, 'code': sent[0][1], 'password': 'new-password-12345'}
    assert client.post('/api/auth/password-reset/confirm', json=payload).status_code == 200
    assert service.authenticate(account.username, payload['password']).id == account.id
    assert client.post('/api/auth/password-reset/confirm', json=payload).status_code == 400
    with pytest.raises(AuthenticationError):
        service.authenticate(account.username, 'correct-password-123')
    with pytest.raises(AuthenticationError):
        service.verify_access_token(session.access_token)
    with pytest.raises(AuthenticationError):
        service.refresh(session.refresh_token)


def test_reset_expiry_attempts_and_resend(service):
    account = user(service)
    now = time.time()
    password_hash = PASSWORD_HASH.hash('new-password-12345')
    service.store.reserve_reset(account.username, 'first', 'ip1', now)
    with pytest.raises(ValueError):
        service.store.reserve_reset(account.username, 'second', 'ip1', now + 1)
    for _ in range(5):
        assert not service.store.confirm_reset(account.username, 'wrong', password_hash, now + 2)
    assert not service.store.confirm_reset(account.username, 'first', password_hash, now + 3)
    service.store.reserve_reset(account.username, 'second', 'ip1', now + 61)
    assert not service.store.confirm_reset(account.username, 'first', password_hash, now + 62)
    assert not service.store.confirm_reset(account.username, 'second', password_hash, now + 662)


def test_reset_unknown_and_smtp_failure(service, client, monkeypatch):
    sent = []
    monkeypatch.setattr(accounts, 'send_code', lambda email, code: sent.append(code))
    assert client.post('/api/auth/password-reset/request', json={'email': 'missing@example.com'}).status_code == 200
    assert not sent
    account = user(service)
    def fail(email, code):
        sent.append(code)
        raise OSError('smtp failure')
    monkeypatch.setattr(accounts, 'send_code', fail)
    assert client.post('/api/auth/password-reset/request', json={'email': account.username}).status_code == 503
    assert client.post('/api/auth/password-reset/confirm', json={'email': account.username, 'code': sent[0], 'password': 'new-password-12345'}).status_code == 400
    monkeypatch.delenv('PRODUCTION_PLATFORM_SMTP_HOST')
    assert client.post('/api/auth/password-reset/request', json={'email': 'someone@example.com'}).status_code == 503


def test_reset_only_one_concurrent_confirmation_succeeds(service):
    account = user(service)
    now = time.time()
    service.store.reserve_reset(account.username, 'digest', 'ip', now)
    password_hash = PASSWORD_HASH.hash('new-password-12345')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.store.confirm_reset(account.username, 'digest', password_hash, now + 1), range(2)))
    assert sorted(results) == [False, True]
