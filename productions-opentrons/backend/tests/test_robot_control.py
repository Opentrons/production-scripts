from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.models import (
    RobotJogDropTipRequest,
    RobotJogGripperRequest,
    RobotJogMoveRequest,
    RobotJogRunRequest,
    RobotResetRequest,
)
from api.services import opentrons_control
from opentrons.opentrons_api.client import OpentronsApiError, OpentronsHttpClient


def test_home_robot_targets_all_axes(monkeypatch):
    client = OpentronsHttpClient("192.168.6.123")
    captured: dict[str, object] = {}

    def fake_request(method, path, *, json_body=None, timeout=None):
        captured.update({"method": method, "path": path, "json_body": json_body, "timeout": timeout})
        return {"message": "homed"}

    monkeypatch.setattr(client, "request", fake_request)

    result = client.home_robot(target="robot")

    assert result == {"message": "homed"}
    assert captured == {
        "method": "POST",
        "path": "/robot/home",
        "json_body": {"target": "robot"},
        "timeout": None,
    }


def test_home_axes_uses_simple_home_command(monkeypatch):
    client = OpentronsHttpClient("192.168.6.123")
    captured: dict[str, object] = {}

    def fake_request(method, path, *, json_body=None, timeout=None):
        captured.update({"method": method, "path": path, "json_body": json_body, "timeout": timeout})
        return {"data": {"status": "succeeded"}}

    monkeypatch.setattr(client, "request", fake_request)

    result = client.home_axes(axes=["leftZ", "leftZ", "leftPlunger"])

    assert result["data"]["status"] == "succeeded"
    assert captured == {
        "method": "POST",
        "path": "/commands?waitUntilComplete=true&timeout=120000",
        "json_body": {
            "data": {
                "commandType": "home",
                "params": {"axes": ["leftZ", "leftPlunger"]},
            }
        },
        "timeout": 130,
    }


def test_home_axes_reports_failed_command(monkeypatch):
    client = OpentronsHttpClient("192.168.6.123")
    monkeypatch.setattr(
        client,
        "request",
        lambda *_args, **_kwargs: {"data": {"status": "failed", "error": {"detail": "motor error"}}},
    )

    with pytest.raises(OpentronsApiError, match="motor error"):
        client.home_axes(axes=["x"])


def test_reset_robot_homes_selected_axes(monkeypatch):
    captured: dict[str, object] = {}

    class FakeClient:
        def home_axes(self, *, axes):
            captured["axes"] = axes
            return {"data": {"status": "succeeded"}}

    monkeypatch.setattr(opentrons_control, "_http_client", lambda ip, port: FakeClient())

    result = opentrons_control.reset_robot(
        "192.168.6.123",
        axes=["rightZ"],
        port=31950,
    )

    assert captured["axes"] == ["rightZ"]
    assert result["data"]["status"] == "succeeded"


def test_reset_request_only_accepts_supported_motor_axes():
    request = RobotResetRequest(axes=["x", "rightPlunger"])
    assert request.axes == ["x", "rightPlunger"]

    with pytest.raises(ValidationError):
        RobotResetRequest(axes=[])
    with pytest.raises(ValidationError):
        RobotResetRequest(axes=["z"])


def test_maintenance_run_jog_client_flow(monkeypatch):
    client = OpentronsHttpClient("192.168.6.123")
    requests: list[dict[str, object]] = []

    def fake_request(method, path, *, json_body=None, timeout=None):
        requests.append({"method": method, "path": path, "json_body": json_body, "timeout": timeout})
        if path == "/maintenance_runs":
            return {"data": {"id": "run-123"}}
        if "/commands" in path:
            return {"data": {"status": "succeeded"}}
        return {"data": {}}

    monkeypatch.setattr(client, "request", fake_request)

    run_id = client.create_maintenance_run()
    result = client.move_axes_relative(run_id=run_id, axis_map={"x": 5, "y": 0})
    client.delete_maintenance_run(run_id)

    assert run_id == "run-123"
    assert result["data"]["status"] == "succeeded"
    assert requests == [
        {
            "method": "POST",
            "path": "/maintenance_runs",
            "json_body": {"data": {}},
            "timeout": None,
        },
        {
            "method": "POST",
            "path": "/maintenance_runs/run-123/commands?waitUntilComplete=true&timeout=120000",
            "json_body": {
                "data": {
                    "commandType": "robot/moveAxesRelative",
                    "params": {"axis_map": {"x": 5.0}},
                }
            },
            "timeout": 130,
        },
        {
            "method": "DELETE",
            "path": "/maintenance_runs/run-123",
            "json_body": None,
            "timeout": None,
        },
    ]


def test_maintenance_run_gripper_commands(monkeypatch):
    client = OpentronsHttpClient("192.168.6.123")
    requests: list[dict[str, object]] = []

    def fake_request(method, path, *, json_body=None, timeout=None):
        requests.append({"method": method, "path": path, "json_body": json_body, "timeout": timeout})
        return {"data": {"status": "succeeded"}}

    monkeypatch.setattr(client, "request", fake_request)

    client.close_gripper_jaw(run_id="run-123")
    client.open_gripper_jaw(run_id="run-123")

    assert requests == [
        {
            "method": "POST",
            "path": "/maintenance_runs/run-123/commands?waitUntilComplete=true&timeout=120000",
            "json_body": {"data": {"commandType": "robot/closeGripperJaw", "params": {}}},
            "timeout": 130,
        },
        {
            "method": "POST",
            "path": "/maintenance_runs/run-123/commands?waitUntilComplete=true&timeout=120000",
            "json_body": {"data": {"commandType": "robot/openGripperJaw", "params": {}}},
            "timeout": 130,
        },
    ]


def test_maintenance_run_pipette_commands(monkeypatch):
    client = OpentronsHttpClient("192.168.6.123")
    requests: list[dict[str, object]] = []

    def fake_request(method, path, *, json_body=None, timeout=None):
        requests.append({"method": method, "path": path, "json_body": json_body, "timeout": timeout})
        return {"data": {"status": "succeeded"}}

    monkeypatch.setattr(client, "request", fake_request)

    client.load_pipette(
        run_id="run-123",
        pipette_name="p1000_single_flex",
        mount="left",
        pipette_id="jog-left-pipette",
    )
    client.drop_tip_in_place(
        run_id="run-123",
        pipette_id="jog-left-pipette",
        home_after=False,
    )

    assert requests == [
        {
            "method": "POST",
            "path": "/maintenance_runs/run-123/commands?waitUntilComplete=true&timeout=120000",
            "json_body": {
                "data": {
                    "commandType": "loadPipette",
                    "params": {
                        "pipetteName": "p1000_single_flex",
                        "mount": "left",
                        "pipetteId": "jog-left-pipette",
                    },
                }
            },
            "timeout": 130,
        },
        {
            "method": "POST",
            "path": "/maintenance_runs/run-123/commands?waitUntilComplete=true&timeout=120000",
            "json_body": {
                "data": {
                    "commandType": "unsafe/dropTipInPlace",
                    "params": {
                        "pipetteId": "jog-left-pipette",
                        "homeAfter": False,
                    },
                }
            },
            "timeout": 130,
        },
    ]


def test_create_and_delete_jog_run(monkeypatch):
    calls: list[tuple[str, object]] = []

    class FakeClient:
        def get_instruments(self):
            return {"data": []}

        def create_maintenance_run(self):
            calls.append(("create", None))
            return "jog-run"

        def delete_maintenance_run(self, run_id):
            calls.append(("delete", run_id))
            return {"data": {}}

    monkeypatch.setattr(opentrons_control, "_http_client", lambda ip, port: FakeClient())

    created = opentrons_control.create_jog_run("192.168.6.123", port=31950)
    released = opentrons_control.delete_jog_run(
        "192.168.6.123",
        run_id=created["run_id"],
        port=31950,
    )

    assert created == {
        "run_id": "jog-run",
        "pipettes": {},
        "pipette_load_warning": None,
    }
    assert released == {"run_id": "jog-run", "released": True, "result": {"data": {}}}
    assert calls == [("create", None), ("delete", "jog-run")]


def test_create_jog_run_loads_attached_pipettes(monkeypatch):
    calls: list[tuple[str, object]] = []

    class FakeClient:
        def get_instruments(self):
            return {
                "data": [
                    {
                        "ok": True,
                        "instrumentType": "pipette",
                        "instrumentName": "p1000_single_flex",
                        "instrumentModel": "p1000_single_v3.0",
                        "mount": "left",
                        "state": {"tipDetected": True},
                    },
                    {
                        "ok": True,
                        "instrumentType": "gripper",
                        "mount": "extension",
                    },
                ]
            }

        def create_maintenance_run(self):
            calls.append(("create", None))
            return "jog-run"

        def load_pipette(self, *, run_id, pipette_name, mount, pipette_id):
            calls.append(
                (
                    "load",
                    {
                        "run_id": run_id,
                        "pipette_name": pipette_name,
                        "mount": mount,
                        "pipette_id": pipette_id,
                    },
                )
            )
            return {"data": {"status": "succeeded"}}

    monkeypatch.setattr(opentrons_control, "_http_client", lambda ip, port: FakeClient())

    created = opentrons_control.create_jog_run("192.168.6.123", port=31950)

    assert created == {
        "run_id": "jog-run",
        "pipettes": {
            "left": {
                "pipette_id": "jog-left-pipette",
                "name": "p1000_single_flex",
                "model": "p1000_single_v3.0",
                "tip_detected": True,
            }
        },
        "pipette_load_warning": None,
    }
    assert calls == [
        ("create", None),
        (
            "load",
            {
                "run_id": "jog-run",
                "pipette_name": "p1000_single_flex",
                "mount": "left",
                "pipette_id": "jog-left-pipette",
            },
        ),
    ]


@pytest.mark.parametrize(
    ("direction", "mount", "expected_axis_map"),
    [
        ("up", "left", {"y": 2.5}),
        ("down", "right", {"y": -2.5}),
        ("left", "left", {"x": -2.5}),
        ("right", "right", {"x": 2.5}),
        ("z_up", "left", {"leftZ": 2.5}),
        ("z_down", "right", {"rightZ": -2.5}),
        ("z_up", "gripper", {"extensionZ": 2.5}),
        ("z_down", "gripper", {"extensionZ": -2.5}),
        ("plunger_up", "left", {"leftPlunger": 2.5}),
        ("plunger_down", "right", {"rightPlunger": -2.5}),
    ],
)
def test_move_jog_robot_maps_direction_without_releasing(monkeypatch, direction, mount, expected_axis_map):
    calls: list[tuple[str, object]] = []

    class FakeClient:
        def move_axes_relative(self, *, run_id, axis_map):
            calls.append(("move", {"run_id": run_id, "axis_map": axis_map}))
            return {"data": {"status": "succeeded"}}

    monkeypatch.setattr(opentrons_control, "_http_client", lambda ip, port: FakeClient())

    result = opentrons_control.move_jog_robot(
        "192.168.6.123",
        run_id="jog-run",
        direction=direction,
        step_mm=2.5,
        mount=mount,
        port=31950,
    )

    assert result["axis_map"] == expected_axis_map
    assert result["run_id"] == "jog-run"
    assert result["mount"] == mount
    assert calls == [("move", {"run_id": "jog-run", "axis_map": expected_axis_map})]


@pytest.mark.parametrize(
    ("action", "expected_call"),
    [
        ("grip", "close"),
        ("ungrip", "open"),
    ],
)
def test_control_jog_gripper_reuses_run(monkeypatch, action, expected_call):
    calls: list[tuple[str, str]] = []

    class FakeClient:
        def close_gripper_jaw(self, *, run_id):
            calls.append(("close", run_id))
            return {"data": {"status": "succeeded"}}

        def open_gripper_jaw(self, *, run_id):
            calls.append(("open", run_id))
            return {"data": {"status": "succeeded"}}

    monkeypatch.setattr(opentrons_control, "_http_client", lambda ip, port: FakeClient())

    result = opentrons_control.control_jog_gripper(
        "192.168.6.123",
        run_id="jog-run",
        action=action,
        port=31950,
    )

    assert result["run_id"] == "jog-run"
    assert result["action"] == action
    assert calls == [(expected_call, "jog-run")]


def test_drop_jog_tip_reuses_loaded_pipette(monkeypatch):
    calls: list[dict[str, object]] = []

    class FakeClient:
        def drop_tip_in_place(self, *, run_id, pipette_id, home_after=None):
            calls.append(
                {
                    "run_id": run_id,
                    "pipette_id": pipette_id,
                    "home_after": home_after,
                }
            )
            return {"data": {"status": "succeeded"}}

    monkeypatch.setattr(opentrons_control, "_http_client", lambda ip, port: FakeClient())

    result = opentrons_control.drop_jog_tip(
        "192.168.6.123",
        run_id="jog-run",
        pipette_id="jog-right-pipette",
        port=31950,
    )

    assert result["run_id"] == "jog-run"
    assert result["pipette_id"] == "jog-right-pipette"
    assert calls == [
        {
            "run_id": "jog-run",
            "pipette_id": "jog-right-pipette",
            "home_after": None,
        }
    ]


def test_jog_request_validates_direction_and_step():
    run_request = RobotJogRunRequest()
    request = RobotJogMoveRequest(direction="right", step_mm=0.5, mount="right")
    gripper_move_request = RobotJogMoveRequest(direction="z_up", step_mm=0.5, mount="gripper")
    plunger_move_request = RobotJogMoveRequest(direction="plunger_up", step_mm=1, mount="left")
    gripper_request = RobotJogGripperRequest(action="grip")
    drop_tip_request = RobotJogDropTipRequest(pipette_id="jog-left-pipette")
    assert run_request.port == 31950
    assert request.direction == "right"
    assert request.step_mm == 0.5
    assert request.mount == "right"
    assert gripper_move_request.mount == "gripper"
    assert plunger_move_request.direction == "plunger_up"
    assert gripper_request.action == "grip"
    assert drop_tip_request.pipette_id == "jog-left-pipette"

    with pytest.raises(ValidationError):
        RobotJogMoveRequest(direction="forward", step_mm=1)
    with pytest.raises(ValidationError):
        RobotJogMoveRequest(direction="up", step_mm=0)
    with pytest.raises(ValidationError):
        RobotJogMoveRequest(direction="up", step_mm=101)
    with pytest.raises(ValidationError):
        RobotJogMoveRequest(direction="z_up", step_mm=1, mount="center")
    with pytest.raises(ValidationError):
        RobotJogGripperRequest(action="hold")
    with pytest.raises(ValidationError):
        RobotJogDropTipRequest(pipette_id="")
