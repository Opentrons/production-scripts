from __future__ import annotations

import pytest

from leveling_testing.type import Mount
from opentonrs_api.maintenance_api.maintenance_run import MaintenanceApi


@pytest.mark.asyncio
async def test_home_uses_protocol_engine_home_command(monkeypatch) -> None:
    api = MaintenanceApi("192.168.6.15")
    api.run_id = "run-1"
    requests: list[tuple[str, dict]] = []

    def post(url, data):
        requests.append((url, data))
        return 201, {"data": {"id": "command-1"}}

    monkeypatch.setattr(api, "post", post)

    await api.home()

    assert requests == [
        (
            "/maintenance_runs/run-1/commands?waitUntilComplete=true",
            {"data": {"commandType": "home", "params": {}}},
        )
    ]


@pytest.mark.asyncio
async def test_home_failure_includes_robot_response(monkeypatch) -> None:
    api = MaintenanceApi("192.168.6.15")
    api.run_id = "run-1"
    monkeypatch.setattr(
        api,
        "post",
        lambda _url, _data: (422, {"errors": [{"detail": "unsupported command"}]}),
    )

    with pytest.raises(RuntimeError, match=r"Home robot failed: HTTP 422") as exc_info:
        await api.home()

    assert "unsupported command" in str(exc_info.value)


@pytest.mark.asyncio
async def test_move_failure_is_distinct_from_home_failure(monkeypatch) -> None:
    api = MaintenanceApi("192.168.6.15")
    api.run_id = "run-1"
    monkeypatch.setattr(api, "post", lambda _url, _data: (409, {"detail": "busy"}))

    with pytest.raises(RuntimeError, match=r"Move to coordinate failed: HTTP 409"):
        await api.move_to(
            {"x": 23.5, "y": 422.5, "z": 397.0},
            mount=Mount.LEFT,
        )


@pytest.mark.asyncio
async def test_delete_run_clears_run_id_after_success(monkeypatch, capsys) -> None:
    api = MaintenanceApi("192.168.6.15")
    api.run_id = "run-1"
    monkeypatch.setattr(api, "delete", lambda _url, _data: (200, {"data": {}}))

    await api.delete_run()

    assert api.run_id is None
    assert "Released the API" in capsys.readouterr().out
