from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.system_images import router
from modules.robots import system_images as service
from modules.robots import upload_ot3_system as uploader


class DeferredExecutor:
    def __init__(self):
        self.jobs = []

    def submit(self, function, *args):
        self.jobs.append((function, args))

    def run(self):
        for function, args in self.jobs:
            function(*args)
        self.jobs.clear()


def archive_bytes(version='8.5.0') -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name in ('systemfs.xz', 'systemfs.xz.sha256', 'systemfs.xz.hash.sig'):
            archive.writestr(name, b'test')
        archive.writestr('VERSION.json', json.dumps({
            'robot_type': 'OT-3 Standard', 'openembedded_version': 'v0.8.7',
            'opentrons_api_version': version,
        }))
    return stream.getvalue()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    images = tmp_path / 'images'
    images.mkdir()
    (images / 'ot3-system-8.5.0.zip').write_bytes(archive_bytes())
    monkeypatch.setenv('PRODUCTION_PLATFORM_OT3_SYSTEM_DIR', str(images))
    monkeypatch.setenv('PRODUCTION_PLATFORM_OT3_TASK_DIR', str(tmp_path / 'tasks'))
    monkeypatch.setattr(service, '_TASKS', {})
    monkeypatch.setattr(service, '_LOADED', False)
    executor = DeferredExecutor()
    monkeypatch.setattr(service, '_UPDATES', executor)
    monkeypatch.setattr(service, '_DOWNLOADS', executor)
    return images, executor


def test_library_ignores_partial_and_symlinks_and_sorts_versions(setup):
    images, _ = setup
    for name in ['ot3-system-9.1.0.zip', 'ot3-system-9.1.0-alpha.9.zip', '.download.part']:
        (images / name).write_bytes(archive_bytes())
    (images / 'ot3-system-99.0.0.zip').symlink_to(images / 'ot3-system-8.5.0.zip')
    assert [image['version'] for image in service.list_images()['images']] == ['9.1.0', '9.1.0-alpha.9', '8.5.0']
    for name in ['../ot3-system-8.5.0.zip', 'ot3-system-99.0.0.zip']:
        with pytest.raises(ValueError):
            service.resolve_image(name)


def test_batch_deduplicates_and_rejects_busy_or_invalid_targets_atomically(setup):
    tasks = service.create_install_tasks(['192.168.6.1', '192.168.6.1', '192.168.6.2'], 'ot3-system-8.5.0.zip')
    assert len(tasks) == 2
    for ips in [['192.168.6.2', '192.168.6.3'], ['192.168.6.3', 'bad-host']]:
        with pytest.raises(ValueError):
            service.create_install_tasks(ips, 'ot3-system-8.5.0.zip')
    assert len(service.list_tasks()) == 2


@pytest.mark.parametrize('failure', [None, 'model', 'write', 'version', 'boot'])
def test_full_install_flow_and_failures(setup, monkeypatch, failure):
    _, executor = setup
    calls = []

    class Client:
        def __init__(self, endpoint, on_progress):
            self.progress = on_progress
        def health(self):
            return {'robotModel': 'OT-2' if failure == 'model' else 'OT-3 Standard', 'bootId': 'old'}
        def begin(self):
            calls.append('begin')
            return {'token': 'session'}
        def upload(self, token, path):
            assert token == 'session'
            calls.append('upload')
            self.progress(10, 10, 100)
        def status(self, token):
            calls.append('status')
            return {'stage': 'error' if failure == 'write' else 'done'}
        def commit(self, token):
            calls.append('commit')
        def restart(self):
            calls.append('restart')
        def wait_for_boot(self, timeout, interval, previous):
            assert previous == 'old'
            calls.append('boot')
            if failure == 'boot':
                raise uploader.RobotUpdateError('reboot timeout')
            return {'systemVersion': 'bad' if failure == 'version' else 'v0.8.7', 'apiServerVersion': '8.5.0'}

    monkeypatch.setattr(service, 'RobotUpdateClient', Client)
    service.create_install_tasks(['192.168.6.1'], 'ot3-system-8.5.0.zip')
    executor.run()
    task = service.list_tasks()[0]
    assert task['status'] == ('failed' if failure else 'success')
    if failure == 'model':
        assert calls == []
    elif failure == 'write':
        assert 'commit' not in calls and 'restart' not in calls
    else:
        assert calls == ['begin', 'upload', 'status', 'commit', 'restart', 'boot']


def test_one_failed_device_does_not_stop_batch(setup, monkeypatch):
    _, executor = setup
    class Client:
        def __init__(self, endpoint, on_progress):
            self.ip = endpoint.host
        def health(self):
            raise RuntimeError(f'unavailable: {self.ip}')
    monkeypatch.setattr(service, 'RobotUpdateClient', Client)
    service.create_install_tasks(['192.168.6.1', '192.168.6.2'], 'ot3-system-8.5.0.zip')
    executor.run()
    tasks = service.list_tasks()
    assert all(t['status'] == 'failed' and t['ip'] in t['message'] for t in tasks)


@pytest.mark.parametrize('payload', [archive_bytes('9.1.2'), archive_bytes(), b'<html>not a zip</html>'])
def test_download_validation_atomic_publish_and_cleanup(setup, monkeypatch, payload):
    images, executor = setup
    class Response:
        headers = {'Content-Length': str(len(payload))}
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def raise_for_status(self): pass
        def iter_content(self, _):
            assert not (images / 'ot3-system-9.1.2.zip').exists()
            yield payload
    monkeypatch.setattr(service.requests, 'get', lambda *a, **k: Response())
    service.create_download_task('https://example.test/ot3-system-9.1.2.zip?signature=secret')
    with pytest.raises(ValueError, match='正在下载'):
        service.create_download_task('https://example.test/ot3-system-9.1.2.zip')
    executor.run()
    valid = b'9.1.2' in payload
    assert (images / 'ot3-system-9.1.2.zip').exists() == valid
    assert service.list_tasks()[0]['status'] == ('success' if valid else 'failed')
    assert not list(images.glob('*.part'))
    assert 'signature' not in json.dumps(service.list_tasks())


@pytest.mark.parametrize('url', ['file:///tmp/ot3-system-1.0.0.zip', 'https://user:pass@example.test/ot3-system-1.0.0.zip', 'https://example.test/%2Ftmp%2Fot3-system-1.0.0.zip', 'https://example.test/image.zip'])
def test_invalid_download_urls_rejected(setup, url):
    with pytest.raises(ValueError):
        service.create_download_task(url)


def test_download_does_not_overwrite_existing_image(setup):
    with pytest.raises(ValueError, match='已存在'):
        service.create_download_task('https://example.test/ot3-system-8.5.0.zip')


def test_journal_restores_interrupted_jobs_without_rerunning(setup, monkeypatch):
    _, executor = setup
    task = service.create_install_tasks(['192.168.6.1'], 'ot3-system-8.5.0.zip')[0]
    monkeypatch.setattr(service, '_TASKS', {})
    monkeypatch.setattr(service, '_LOADED', False)
    recovered = service.list_tasks()[0]
    assert recovered['id'] == task['id']
    assert recovered['status'] == 'failed'
    assert recovered['stage'] == 'interrupted'
    assert len(executor.jobs) == 1


def test_routes_validate_and_return_background_jobs(setup):
    app = FastAPI()
    app.include_router(router, prefix='/api')
    client = TestClient(app)
    assert client.get('/api/robots/system-images').status_code == 200
    assert client.post('/api/robots/system-images/install', json={'ips': [], 'image': 'x'}).status_code == 422
    assert client.post('/api/robots/system-images/install', json={'ips': ['192.168.6.1'], 'image': 'ot3-system-1.0.0.zip'}).status_code == 404
    response = client.post('/api/robots/system-images/install', json={'ips': ['192.168.6.1'], 'image': 'ot3-system-8.5.0.zip'})
    assert response.status_code == 202
    assert response.json()['tasks'][0]['status'] == 'queued'
    assert client.get('/api/robots/system-images/tasks').json()['tasks']


def test_wait_boot_rejects_old_boot_even_if_healthy(monkeypatch):
    client = uploader.RobotUpdateClient(uploader.Endpoint('http', '127.0.0.1', 31950))
    states = iter([{'bootId': 'old'}, {'bootId': 'old'}, {'bootId': 'new'}])
    monkeypatch.setattr(client, 'health', lambda: next(states))
    monkeypatch.setattr(uploader.time, 'sleep', lambda _: None)
    assert client.wait_for_boot(10, 0, 'old')['bootId'] == 'new'


def test_wait_boot_timeout_even_when_old_server_stays_online(monkeypatch):
    client = uploader.RobotUpdateClient(uploader.Endpoint('http', '127.0.0.1', 31950))
    clock = iter([0, 1, 11])
    monkeypatch.setattr(uploader.time, 'monotonic', lambda: next(clock))
    monkeypatch.setattr(uploader.time, 'sleep', lambda _: None)
    monkeypatch.setattr(client, 'health', lambda: {'bootId': 'old'})
    with pytest.raises(uploader.RobotUpdateError, match='reboot'):
        client.wait_for_boot(10, 0, 'old')


def test_real_http_upload_and_reboot_protocol(setup, monkeypatch):
    """Exercise the copied streaming client against a local fake robot."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    images, executor = setup
    calls = []
    uploaded = []
    restarted = False

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, status, data):
            encoded = json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            calls.append(('GET', self.path))
            if self.path == '/server/update/health':
                self.respond(200, {'robotModel': 'OT-3 Standard', 'bootId': 'new' if restarted else 'old',
                                   'systemVersion': 'v0.8.7', 'apiServerVersion': '8.5.0'})
            elif self.path == '/server/update/session/status':
                self.respond(200, {'stage': 'done'})
            else:
                self.respond(404, {})

        def do_POST(self):
            nonlocal restarted
            calls.append(('POST', self.path))
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            if self.path == '/server/update/begin':
                self.respond(201, {'token': 'session'})
            elif self.path == '/server/update/session/file':
                from email.parser import BytesParser
                from email.policy import default
                multipart = BytesParser(policy=default).parsebytes(
                    f"Content-Type: {self.headers['Content-Type']}\r\n\r\n".encode() + body
                )
                part = list(multipart.iter_parts())[0]
                assert part.get_param('name', header='content-disposition') == 'system-update.zip'
                uploaded.append(part.get_payload(decode=True))
                self.respond(201, {'stage': 'writing'})
            elif self.path == '/server/update/session/commit':
                self.respond(200, {'stage': 'done'})
            elif self.path == '/server/restart':
                restarted = True
                self.respond(200, {'message': 'restarting'})
            else:
                self.respond(404, {})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        service.create_install_tasks(['127.0.0.1'], 'ot3-system-8.5.0.zip', server.server_port)
        executor.run()
        assert service.list_tasks()[0]['status'] == 'success'
        assert uploaded == [(images / 'ot3-system-8.5.0.zip').read_bytes()]
        assert calls == [
            ('GET', '/server/update/health'), ('POST', '/server/update/begin'),
            ('POST', '/server/update/session/file'), ('GET', '/server/update/session/status'),
            ('POST', '/server/update/session/commit'), ('POST', '/server/restart'),
            ('GET', '/server/update/health'),
        ]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
