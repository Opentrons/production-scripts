from __future__ import annotations

import pytest

from api.services import robots


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
