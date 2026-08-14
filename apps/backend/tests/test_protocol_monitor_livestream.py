from __future__ import annotations

import requests

from modules.protocol_monitor import livestream


def _response(content_type: str = "application/vnd.apple.mpegurl") -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response.headers["Content-Type"] = content_type
    response._content = b""
    return response


def test_enable_preserves_error_recovery_setting(monkeypatch) -> None:
    calls: list[tuple[str, str, dict | None]] = []

    class FakeClient:
        def __init__(self, ip: str, port: int, timeout: int) -> None:
            assert (ip, port, timeout) == ("192.168.6.11", 31950, 8)

        @staticmethod
        def unwrap_data(payload):
            return payload

        def request(self, method: str, path: str, json_body=None):
            calls.append((method, path, json_body))
            if method == "GET":
                return {"errorRecoveryCameraEnabled": True}
            return {"cameraEnabled": True, "liveStreamEnabled": True}

        @staticmethod
        def list_runs():
            return [{"id": "run-1", "current": True, "status": "running"}]

    monkeypatch.setattr(
        livestream.service,
        "get_device",
        lambda _room_id, _device_id: {"ip": "192.168.6.11", "port": 31950},
    )
    monkeypatch.setattr(livestream, "OpentronsHttpClient", FakeClient)

    result = livestream.enable("room-1", "device-1")

    assert result == {"enabled": True, "idle_override": False, "lease_id": None}
    assert calls == [
        ("GET", "/camera", None),
        (
            "POST",
            "/camera",
            {
                "data": {
                    "cameraEnabled": True,
                    "liveStreamEnabled": True,
                    "errorRecoveryCameraEnabled": True,
                }
            },
        ),
    ]


def test_enable_idle_device_starts_runtime_stream_over_ssh(monkeypatch) -> None:
    ssh_calls: list[tuple[str, int]] = []

    class FakeClient:
        def __init__(self, ip: str, port: int, timeout: int) -> None:
            assert (ip, port, timeout) == ("192.168.6.13", 31950, 8)

        @staticmethod
        def unwrap_data(payload):
            return payload

        @staticmethod
        def request(method: str, path: str, json_body=None):
            if method == "GET":
                return {"errorRecoveryCameraEnabled": False}
            return {"cameraEnabled": True, "liveStreamEnabled": True}

        @staticmethod
        def list_runs():
            return [{"id": "run-1", "current": True, "status": "succeeded"}]

    class FakeSshClient:
        TIMEOUT = 30

        def __init__(self, ip: str) -> None:
            assert ip == "192.168.6.13"

        def exec_command(self, command: str, *, timeout: int):
            ssh_calls.append((command, timeout))
            return 0, "", ""

    monkeypatch.setattr(
        livestream.service,
        "get_device",
        lambda _room_id, _device_id: {"ip": "192.168.6.13", "port": 31950},
    )
    monkeypatch.setattr(livestream, "OpentronsHttpClient", FakeClient)
    monkeypatch.setattr(livestream, "OpentronsSshClient", FakeSshClient)

    result = livestream.enable("room-1", "device-1")

    lease_id = result["lease_id"]
    assert result["enabled"] is True
    assert result["idle_override"] is True
    assert isinstance(lease_id, str)

    release_result = livestream.release("room-1", "device-1", lease_id)

    assert release_result == {"released": True, "stopped": True}
    assert len(ssh_calls) == 2
    start_command, start_timeout = ssh_calls[0]
    stop_command, stop_timeout = ssh_calls[1]
    assert livestream._LIVE_STREAM_ENV_PATH in start_command
    assert "STATUS=ON" in start_command
    assert "systemctl restart opentrons-live-stream" in start_command
    assert "STATUS=OFF" in stop_command
    assert start_timeout == stop_timeout == livestream._IDLE_STREAM_SSH_TIMEOUT_SECONDS


def test_enable_idle_device_reports_ssh_failure(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, ip: str, port: int, timeout: int) -> None:
            pass

        @staticmethod
        def unwrap_data(payload):
            return payload

        @staticmethod
        def request(method: str, path: str, json_body=None):
            return {"errorRecoveryCameraEnabled": False}

        @staticmethod
        def list_runs():
            return []

    class FakeSshClient:
        TIMEOUT = 30

        def __init__(self, ip: str) -> None:
            pass

        @staticmethod
        def exec_command(command: str, *, timeout: int):
            return 1, "", "permission denied"

    monkeypatch.setattr(
        livestream.service,
        "get_device",
        lambda _room_id, _device_id: {"ip": "192.168.6.14", "port": 31950},
    )
    monkeypatch.setattr(livestream, "OpentronsHttpClient", FakeClient)
    monkeypatch.setattr(livestream, "OpentronsSshClient", FakeSshClient)

    try:
        livestream.enable("room-1", "device-1")
    except livestream.LivestreamUpstreamError as exc:
        assert "permission denied" in str(exc)
    else:
        raise AssertionError("SSH failure should be reported")


def test_release_does_not_stop_stream_when_run_started(monkeypatch) -> None:
    status = {"value": "succeeded"}
    ssh_commands: list[str] = []

    class FakeClient:
        def __init__(self, ip: str, port: int, timeout: int) -> None:
            pass

        @staticmethod
        def unwrap_data(payload):
            return payload

        @staticmethod
        def request(method: str, path: str, json_body=None):
            return {"errorRecoveryCameraEnabled": False}

        @staticmethod
        def list_runs():
            return [{"id": "run-1", "current": True, "status": status["value"]}]

    class FakeSshClient:
        TIMEOUT = 30

        def __init__(self, ip: str) -> None:
            pass

        @staticmethod
        def exec_command(command: str, *, timeout: int):
            ssh_commands.append(command)
            return 0, "", ""

    monkeypatch.setattr(
        livestream.service,
        "get_device",
        lambda _room_id, _device_id: {"ip": "192.168.6.15", "port": 31950},
    )
    monkeypatch.setattr(livestream, "OpentronsHttpClient", FakeClient)
    monkeypatch.setattr(livestream, "OpentronsSshClient", FakeSshClient)

    enabled = livestream.enable("room-2", "device-2")
    status["value"] = "running"
    released = livestream.release("room-2", "device-2", str(enabled["lease_id"]))

    assert released == {"released": True, "stopped": False}
    assert len(ssh_commands) == 1
    assert "STATUS=ON" in ssh_commands[0]


def test_shutdown_restores_stream_if_run_starts_during_close(monkeypatch) -> None:
    statuses = iter(["succeeded", "running"])
    ssh_statuses: list[bool] = []
    restored: list[object] = []

    class FakeClient:
        @staticmethod
        def list_runs():
            return [{"id": "run-1", "current": True, "status": next(statuses)}]

    client = FakeClient()
    monkeypatch.setattr(livestream, "_client_for_device", lambda _device: client)
    monkeypatch.setattr(
        livestream,
        "_set_idle_stream_status_over_ssh",
        lambda _device_ip, *, enabled: ssh_statuses.append(enabled),
    )
    monkeypatch.setattr(
        livestream,
        "_configure_camera_enabled",
        lambda configured_client: restored.append(configured_client),
    )

    stopped = livestream._disable_idle_stream_if_unused(
        ("room-race", "device-race"),
        "192.168.6.17",
    )

    assert stopped is False
    assert ssh_statuses == [False]
    assert restored == [client]


def test_release_keeps_stream_until_last_viewer_leaves(monkeypatch) -> None:
    key = ("room-shared", "device-shared")
    stopped: list[tuple[str, str]] = []
    first = livestream._register_idle_stream_lease(key, "192.168.6.18")
    second = livestream._register_idle_stream_lease(key, "192.168.6.18")
    monkeypatch.setattr(
        livestream,
        "_disable_idle_stream_if_unused",
        lambda stopped_key, _device_ip, _device_port: stopped.append(stopped_key) or True,
    )

    first_result = livestream.release(*key, first)
    second_result = livestream.release(*key, second)

    assert first_result == {"released": True, "stopped": False}
    assert second_result == {"released": True, "stopped": True}
    assert stopped == [key]


def test_expired_idle_stream_lease_triggers_shutdown(monkeypatch) -> None:
    key = ("room-expired", "device-expired")
    stopped: list[tuple[tuple[str, str], str]] = []
    lease_id = livestream._register_idle_stream_lease(key, "192.168.6.16")
    with livestream._LEASE_LOCK:
        state = livestream._IDLE_STREAM_LEASES[key]
        assert state.timer is not None
        state.timer.cancel()
        state.timer = None
        state.leases[lease_id] = 0

    monkeypatch.setattr(livestream, "monotonic", lambda: 1000.0)
    monkeypatch.setattr(
        livestream,
        "_disable_idle_stream_if_unused",
        lambda expired_key, device_ip, device_port: stopped.append((expired_key, device_ip)) or True,
    )

    livestream._expire_idle_stream_leases(key)

    assert stopped == [(key, "192.168.6.16")]
    assert key not in livestream._IDLE_STREAM_LEASES


def test_open_asset_uses_registered_device_and_fixed_hls_root(monkeypatch) -> None:
    captured: dict = {}

    def fake_get(url, *, headers, stream, timeout):
        captured.update(url=url, headers=headers, stream=stream, timeout=timeout)
        return _response("video/mp2t")

    monkeypatch.setattr(
        livestream.service,
        "get_device",
        lambda _room_id, _device_id: {"ip": "192.168.6.12", "port": 31950},
    )
    monkeypatch.setattr(livestream.requests, "get", fake_get)

    asset = livestream.open_asset(
        "room-1",
        "device-1",
        "segments/stream 01.ts",
        range_header="bytes=0-100",
    )

    assert captured == {
        "url": "http://192.168.6.12:31950/hls/segments/stream%2001.ts",
        "headers": {"Range": "bytes=0-100"},
        "stream": True,
        "timeout": (4, 20),
    }
    assert asset.device_ip == "192.168.6.12"


def test_open_asset_rejects_parent_path(monkeypatch) -> None:
    monkeypatch.setattr(
        livestream.service,
        "get_device",
        lambda _room_id, _device_id: {"ip": "192.168.6.12", "port": 31950},
    )

    try:
        livestream.open_asset("room-1", "device-1", "../health")
    except ValueError as exc:
        assert str(exc) == "直播资源路径无效"
    else:
        raise AssertionError("parent path should be rejected")


def test_rewrite_playlist_routes_segments_and_uri_attributes_through_proxy() -> None:
    asset = livestream.LivestreamAsset(
        response=_response(),
        device_ip="192.168.6.12",
        device_port=31950,
        asset_path="nested/stream.m3u8",
    )
    content = "\n".join(
        [
            "#EXTM3U",
            '#EXT-X-MAP:URI="init.mp4"',
            "#EXTINF:2.0,",
            "segment-1.ts",
            "#EXTINF:2.0,",
            "/hls/segment-2.ts?token=abc",
        ]
    )

    rewritten = livestream.rewrite_playlist(
        content,
        asset,
        "/api/protocol-monitor/rooms/room-1/devices/device-1/livestream",
        "lease-1",
    )

    assert 'URI="/api/protocol-monitor/rooms/room-1/devices/device-1/livestream/nested/init.mp4?lease_id=lease-1"' in rewritten
    assert "/livestream/nested/segment-1.ts?lease_id=lease-1" in rewritten
    assert "/livestream/segment-2.ts?token=abc&lease_id=lease-1" in rewritten


def test_rewrite_playlist_rejects_external_resource() -> None:
    asset = livestream.LivestreamAsset(
        response=_response(),
        device_ip="192.168.6.12",
        device_port=31950,
        asset_path="stream.m3u8",
    )

    try:
        livestream.rewrite_playlist(
            "#EXTM3U\nhttp://example.com/segment.ts\n",
            asset,
            "/api/livestream",
        )
    except livestream.LivestreamUpstreamError as exc:
        assert "不受信任" in str(exc)
    else:
        raise AssertionError("external playlist resource should be rejected")
