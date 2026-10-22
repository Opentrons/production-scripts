from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.routers import defect_search
from modules.auth.dependencies import get_auth_service, require_platform_access
from modules.auth.service import AuthService
from modules.defect_search import feedback, maintenance, normalization, repository, service


CSV = ('source,source_sheet,source_row,product,defect_description,containment_action\n'
       'synthetic,Test,1,HS,Latch Fail,复测\n')


@pytest.fixture
def knowledge(tmp_path):
    seed = tmp_path / 'seed.csv'
    seed.write_text(CSV, encoding='utf-8')
    db = tmp_path / 'knowledge.sqlite3'
    repository.ensure_database(db, seed)
    return db, seed


def observe(db, seed, user='alice', **changes):
    payload = dict(case_id=1, query='Latch Fail', action='复测', outcome='pending',
                   recurrence='unknown', note='test note', created_by=user,
                   actual_serial_number='TEST-SN')
    return feedback.save_feedback(db, seed, **(payload | changes))['feedback']


def test_feedback_history_and_sessions_are_private(knowledge):
    db, seed = knowledge
    alice = observe(db, seed)
    bob = observe(db, seed, 'bob', actual_serial_number='BOB-SN')
    assert [r['id'] for r in feedback.list_feedback(db, seed, 1, created_by='alice')] == [alice['id']]
    with pytest.raises(feedback.RepairSessionNotFoundError):
        feedback.list_feedback(db, seed, 1, created_by='alice', repair_session_id=bob['repair_session_id'])
    with pytest.raises(feedback.RepairSessionNotFoundError):
        observe(db, seed, repair_session_id=bob['repair_session_id'])
    with pytest.raises(ValueError):
        feedback.list_feedback(db, seed, 1)
    with pytest.raises(ValueError):
        observe(db, seed, repair_session_id=alice['repair_session_id'], actual_serial_number='OTHER-SN')
    observe(db, seed, repair_session_id=alice['repair_session_id'], outcome='passed')
    assert len(feedback.list_feedback(db, seed, 1, created_by='alice', repair_session_id=alice['repair_session_id'])) == 2


@pytest.fixture
def api(knowledge, tmp_path, monkeypatch):
    db, seed = knowledge
    monkeypatch.setattr(service, 'DATABASE_PATH', db)
    monkeypatch.setattr(service, 'DATA_PATH', seed)
    auth = AuthService(db_path=tmp_path / 'auth.sqlite3', jwt_secret='test-secret-' * 4,
                       issuer='test', audience='test', access_token_minutes=5, refresh_token_hours=1)
    auth.initialize()
    app = FastAPI()
    app.include_router(defect_search.router, prefix='/api', dependencies=[Depends(require_platform_access)])
    app.dependency_overrides[get_auth_service] = lambda: auth
    return TestClient(app), auth


@pytest.mark.parametrize('role', ['admin', 'operator', 'viewer', 'device_operator'])
def test_only_admin_can_maintain_knowledge(api, knowledge, role):
    client, auth = api
    db, seed = knowledge
    user = auth.create_user(username=role, password='test-password-long-enough', display_name=role, role=role)
    session = auth.issue_session(user, user_agent='pytest', ip_address='127.0.0.1')
    headers = {'Authorization': 'Bearer ' + session.access_token}
    content = CSV.replace('复测', '调整电磁铁')
    token = maintenance.preview_import(db, seed, content)['preview_token']
    before = maintenance.get_maintenance_status(db)
    requests = [
        ('GET', '/maintenance', None),
        ('POST', '/import/preview', {'csv_content': content}),
        ('POST', '/import', {'csv_content': content, 'preview_token': token}),
        ('POST', '/backup', None),
    ]
    for method, endpoint, body in requests:
        response = client.request(method, '/api/defect-search' + endpoint, json=body, headers=headers)
        assert response.status_code == (200 if role == 'admin' else 403), response.text
    after = maintenance.get_maintenance_status(db)
    if role != 'admin':
        assert after == before
    else:
        assert after['data_version'] != before['data_version']
    assert client.get('/api/defect-search/options', headers=headers).status_code == 200


def test_anonymous_cannot_read_or_maintain(api):
    client, _ = api
    for endpoint in ('/options', '/maintenance', '/feedback?case_id=1'):
        assert client.get('/api/defect-search' + endpoint).status_code == 401
    assert client.post('/api/defect-search/backup').status_code == 401


def test_empty_install_can_import_without_bundled_seed(tmp_path, monkeypatch):
    db, seed = tmp_path / 'knowledge.sqlite3', tmp_path / 'missing.csv'
    monkeypatch.setattr(service, 'DATABASE_PATH', db)
    monkeypatch.setattr(service, 'DATA_PATH', seed)
    assert service.get_options() == {'product': [], 'station': [], 'defect_code': []}
    assert service.search_cases()['total'] == 0
    preview = maintenance.preview_import(db, seed, CSV)
    assert preview['inserted'] == 1
    assert maintenance.import_csv(db, seed, CSV, preview['preview_token'])['inserted'] == 1
    result = service.search_cases(query='HS Latch Fail')
    assert result['total'] == 1
    assert result['cases'][0]['product'] == 'HS'


def test_import_updates_in_place_and_rejects_stale_preview(knowledge):
    db, seed = knowledge
    entry = observe(db, seed)
    content = CSV.replace('复测', '调整电磁铁')
    preview = maintenance.preview_import(db, seed, content)
    maintenance.import_csv(db, seed, content, preview['preview_token'])
    assert repository.load_cases(db, seed)[0]['local_id'] == '1'
    assert feedback.list_feedback(db, seed, 1, created_by='alice')[0]['id'] == entry['id']
    with pytest.raises(ValueError, match='预览已失效'):
        maintenance.import_csv(db, seed, content, preview['preview_token'])


def test_failed_import_rolls_back_original_and_derived_data(knowledge, monkeypatch):
    db, seed = knowledge
    entry = observe(db, seed)
    content = CSV.replace('复测', '调整电磁铁')
    preview = maintenance.preview_import(db, seed, content)
    original_prepare = repository._prepare

    def fail_after_derivation(connection, path):
        original_prepare(connection, path)
        raise RuntimeError('simulated failure')

    monkeypatch.setattr(repository, '_prepare', fail_after_derivation)
    with pytest.raises(RuntimeError, match='simulated failure'):
        maintenance.import_csv(db, seed, content, preview['preview_token'])
    with sqlite3.connect(db) as connection:
        assert connection.execute('SELECT action FROM temporary_action_evidence').fetchone()[0] == '复测'
        assert connection.execute('SELECT COUNT(*) FROM knowledge_changes').fetchone()[0] == 0
    assert repository.load_cases(db, seed)[0]['containment_action'] == '复测'
    assert feedback.list_feedback(db, seed, 1, created_by='alice')[0]['id'] == entry['id']


def test_v3_migration_preserves_feedback_and_creates_backup(knowledge):
    db, seed = knowledge
    entry = observe(db, seed)
    with sqlite3.connect(db) as connection:
        connection.execute('DROP INDEX idx_defect_feedback_session')
        connection.execute('ALTER TABLE defect_feedback DROP COLUMN repair_session_id')
        connection.execute('ALTER TABLE defect_feedback DROP COLUMN actual_serial_number')
        connection.execute("UPDATE knowledge_meta SET value='3' WHERE key='storage_schema_version'")
    repository.invalidate_cache(db)
    repository.ensure_database(db, seed)
    migrated = feedback.list_feedback(db, seed, 1, created_by='alice')[0]
    assert migrated['id'] == entry['id']
    assert migrated['repair_session_id'] == ''
    backups = sorted((db.parent / 'backups').glob('*before-schema-v4*.sqlite3'))
    with sqlite3.connect(backups[-1]) as connection:
        columns = {row[1] for row in connection.execute('PRAGMA table_info(defect_feedback)')}
        assert 'repair_session_id' not in columns


@pytest.mark.parametrize(('left', 'right', 'expected'), [
    ('60s漏液', '60秒漏液', True),
    ('60s漏液', '160秒漏液', False),
    ('H1漏液', 'H12漏液', False),
    ('Latch Fail', 'Fail Latch', True),
    ('speed-180/current-0.8', 'speed-0.8/current-180', False),
])
def test_symptom_matching_keeps_critical_constraints(left, right, expected):
    assert normalization.complete_symptom(left, right) is expected


def test_failed_actions_are_not_recommended(knowledge):
    db, seed = knowledge
    case = repository.load_cases(db, seed)[0]
    case['containment_action'] = '复测失败'
    assert repository.recommend(db, [case])[0]['actions'] == []
