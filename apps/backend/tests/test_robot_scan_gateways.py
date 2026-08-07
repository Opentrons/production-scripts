from __future__ import annotations

import pytest

from modules.robots import robots


def test_build_gateway_scan_targets_starts_after_gateway() -> None:
    targets, scan_range = robots.build_gateway_scan_targets("192.168.6.1")

    assert targets[0] == "192.168.6.2"
    assert targets[-1] == "192.168.6.255"
    assert len(targets) == 254
    assert scan_range == "192.168.6.2-255"


def test_build_gateway_scan_targets_rejects_last_address() -> None:
    with pytest.raises(ValueError, match="最后一个地址"):
        robots.build_gateway_scan_targets("192.168.6.255")


def test_resolve_scan_targets_uses_database_gateways(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(robots, "resolve_server_scan_ip", lambda: "192.168.6.55")
    monkeypatch.setattr(
        robots,
        "list_scan_gateways",
        lambda: {
            "gateways": [
                {"gateway": "192.168.6.1"},
                {"gateway": "192.168.7.1"},
            ]
        },
    )

    targets, scan_network, server_ip, scan_gateways = robots.resolve_scan_targets()

    assert targets[0] == "192.168.6.2"
    assert "192.168.6.255" in targets
    assert "192.168.7.2" in targets
    assert targets[-1] == "192.168.7.255"
    assert len(targets) == 508
    assert scan_network == "192.168.6.2-255, 192.168.7.2-255"
    assert server_ip == "192.168.6.55"
    assert scan_gateways == ["192.168.6.1", "192.168.7.1"]


def test_scan_gateway_lookup_falls_back_to_empty_when_mongodb_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(robots, "resolve_server_scan_ip", lambda: "192.168.8.55")
    monkeypatch.setattr(
        robots,
        "get_scan_gateway_collection",
        lambda: (_ for _ in ()).throw(RuntimeError("MongoDB connection is not available")),
    )

    assert robots.list_scan_gateways() == {"gateways": []}
    targets, scan_network, server_ip, scan_gateways = robots.resolve_scan_targets()

    assert len(targets) == 255
    assert targets[0] == "192.168.8.1"
    assert targets[-1] == "192.168.8.255"
    assert scan_network == "192.168.8.1-255"
    assert server_ip == "192.168.8.55"
    assert scan_gateways == []


def test_resolve_scan_targets_falls_back_when_gateway_resolution_breaks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(robots, "resolve_server_scan_ip", lambda: "192.168.9.20")
    monkeypatch.setattr(
        robots,
        "list_scan_gateways",
        lambda: {"gateways": [{"gateway": "192.168.9.1"}]},
    )
    monkeypatch.setattr(
        robots,
        "_resolve_configured_gateway_targets",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("gateway resolve boom")),
    )

    targets, scan_network, server_ip, scan_gateways = robots.resolve_scan_targets()

    assert targets[0] == "192.168.9.1"
    assert targets[-1] == "192.168.9.255"
    assert scan_network == "192.168.9.1-255"
    assert server_ip == "192.168.9.20"
    assert scan_gateways == []


def test_build_server_network_scan_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(robots, "resolve_server_scan_ip", lambda: "10.0.3.44")

    targets, scan_network, server_ip, scan_gateways = robots.build_server_network_scan_targets()

    assert len(targets) == 255
    assert targets[0] == "10.0.3.1"
    assert scan_network == "10.0.3.1-255"
    assert server_ip == "10.0.3.44"
    assert scan_gateways == []


def test_resolve_server_scan_ip_prefers_local_ip_over_configured_api_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(robots.setting, "API_HOST", "192.168.6.55")
    monkeypatch.setattr(robots, "get_local_ip", lambda: "192.168.31.161")
    monkeypatch.setattr(robots, "get_gateway_ip", lambda: "192.168.31.1")
    monkeypatch.setattr(robots, "list_scan_gateways", lambda: {"gateways": []})

    assert robots.resolve_server_scan_ip() == "192.168.31.161"
    targets, scan_network, server_ip, scan_gateways = robots.resolve_scan_targets()
    assert scan_network == "192.168.31.1-255"
    assert server_ip == "192.168.31.161"
    assert targets[0] == "192.168.31.1"
    assert scan_gateways == []
