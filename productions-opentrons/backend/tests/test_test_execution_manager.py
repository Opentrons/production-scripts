from __future__ import annotations

import pytest

from test_case.execution.manager import build_remote_test_command


def test_build_remote_test_command_sets_robot_working_directory() -> None:
    assert (
        build_remote_test_command(
            "python3 -m hardware_testing.scripts.jaw_lifetime",
            "/opt/opentrons-robot-server",
        )
        == "cd /opt/opentrons-robot-server && exec python3 -m hardware_testing.scripts.jaw_lifetime"
    )


def test_build_remote_test_command_quotes_working_directory() -> None:
    assert build_remote_test_command("echo 'hello world'", "/tmp/hardware testing") == (
        "cd '/tmp/hardware testing' && exec echo 'hello world'"
    )


@pytest.mark.parametrize("command, working_directory", [("", "/tmp"), ("echo ok", "")])
def test_build_remote_test_command_rejects_missing_values(command: str, working_directory: str) -> None:
    with pytest.raises(ValueError):
        build_remote_test_command(command, working_directory)
