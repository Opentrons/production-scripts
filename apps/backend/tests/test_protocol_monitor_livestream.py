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

    monkeypatch.setattr(
        livestream.service,
        "get_device",
        lambda _room_id, _device_id: {"ip": "192.168.6.11", "port": 31950},
    )
    monkeypatch.setattr(livestream, "OpentronsHttpClient", FakeClient)

    result = livestream.enable("room-1", "device-1")

    assert result == {"enabled": True}
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
    )

    assert 'URI="/api/protocol-monitor/rooms/room-1/devices/device-1/livestream/nested/init.mp4"' in rewritten
    assert "/livestream/nested/segment-1.ts" in rewritten
    assert "/livestream/segment-2.ts?token=abc" in rewritten


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
