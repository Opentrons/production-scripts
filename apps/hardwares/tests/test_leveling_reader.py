from __future__ import annotations

from types import SimpleNamespace

import pytest

from leveling_testing.fixture import reader
from leveling_testing.type import Mount, TestNameLeveling as LevelingTestName


@pytest.mark.parametrize(
    "test_name",
    [LevelingTestName.CH96_Leveling, LevelingTestName.Gripper_Leveling],
)
def test_single_mount_leveling_uses_default_port_without_get_mount(
    monkeypatch,
    test_name: LevelingTestName,
) -> None:
    initialized_ports: list[str] = []

    class FakeLaser:
        def init_device(self, select_default: str = "") -> None:
            initialized_ports.append(select_default)

        def get_mount(self, quiet: bool = False) -> str:
            raise AssertionError("Leveling fixtures must not call GetMount")

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        reader.Reader,
        "get_com_list",
        classmethod(lambda cls: [SimpleNamespace(device="COM96")]),
    )
    monkeypatch.setattr(reader, "LaserSensor", FakeLaser)

    lasers = reader.Reader.init_laser_stj_10m0(
        test_name,
        announce=False,
    )

    assert initialized_ports == ["COM96"]
    assert isinstance(lasers[Mount.LEFT], FakeLaser)


@pytest.mark.parametrize(
    "test_name",
    [LevelingTestName.Z_Leveling, LevelingTestName.CH8_Leveling],
)
def test_dual_mount_leveling_probes_mount_instead_of_using_port_order(
    monkeypatch,
    test_name: LevelingTestName,
) -> None:
    initialized_ports: list[str] = []

    class FakeLaser:
        def __init__(self) -> None:
            self.port = ""

        def init_device(self, select_default: str = "") -> None:
            self.port = select_default
            initialized_ports.append(select_default)

        def get_mount(self, quiet: bool = False) -> str:
            return "right" if self.port == "COM_RIGHT" else "left"

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        reader.Reader,
        "get_com_list",
        classmethod(lambda cls: [SimpleNamespace(device="COM_RIGHT"), SimpleNamespace(device="COM_LEFT")]),
    )
    monkeypatch.setattr(reader, "LaserSensor", FakeLaser)

    lasers = reader.Reader.init_laser_stj_10m0(test_name, announce=False)

    assert initialized_ports == ["COM_RIGHT", "COM_LEFT"]
    assert isinstance(lasers[Mount.LEFT], FakeLaser)
    assert isinstance(lasers[Mount.RIGHT], FakeLaser)
    assert lasers[Mount.LEFT].port == "COM_LEFT"
    assert lasers[Mount.RIGHT].port == "COM_RIGHT"
