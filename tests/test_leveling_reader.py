from __future__ import annotations

from types import SimpleNamespace

from test_cli.leveling_test.fixture import reader
from test_cli.leveling_test.type import Mount, TestNameLeveling as LevelingTestName


def test_leveling_fixtures_use_default_port_order_without_get_mount(monkeypatch) -> None:
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
        LevelingTestName.Gripper_Leveling,
        announce=False,
    )

    assert initialized_ports == ["COM96"]
    assert isinstance(lasers[Mount.LEFT], FakeLaser)


def test_dual_mount_leveling_uses_ports_in_default_mount_order(monkeypatch) -> None:
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
        classmethod(lambda cls: [SimpleNamespace(device="COM_LEFT"), SimpleNamespace(device="COM_RIGHT")]),
    )
    monkeypatch.setattr(reader, "LaserSensor", FakeLaser)

    lasers = reader.Reader.init_laser_stj_10m0(LevelingTestName.Z_Leveling, announce=False)

    assert initialized_ports == ["COM_LEFT", "COM_RIGHT"]
    assert isinstance(lasers[Mount.LEFT], FakeLaser)
    assert isinstance(lasers[Mount.RIGHT], FakeLaser)
