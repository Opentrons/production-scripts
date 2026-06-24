from devices.laser_stj_10_m0 import LaserSensor
from dataclasses import dataclass
from typing import Any, Protocol
from test_cli.leveling_test.type import Mount, TestNameLeveling
from test_cli.leveling_test.errors import FixtureNotFoundError, SensorReadError
from test_cli.cli import ui
from contextlib import redirect_stdout
import io
import serial
import serial.tools.list_ports
from typing import List
import time
import sys


# 定义协议接口
class ReadableSensor(Protocol):
    def read_sensor_low(self, show_distance: bool = ...) -> Any: ...


@dataclass
class Reader:
    @staticmethod
    def read_sensor(laser: ReadableSensor, delay=6) -> dict[int, float]:
        try:
            for i in range(delay):
                print(f"Waiting {i + 1}/({delay}) s...")
                time.sleep(1)
            result = laser.read_sensor_low(show_distance=True)  # duck typing
            if not result:
                raise SensorReadError("Empty sensor result")
            return result
        except SensorReadError:
            raise
        except Exception as exc:
            raise SensorReadError(f"{type(exc).__name__}: {exc}") from exc

    @classmethod
    def get_com_list(cls) -> List[serial.tools.list_ports_common.ListPortInfo]:
        """Get list of available serial ports. On macOS, only return USB devices."""
        port_list = serial.tools.list_ports.comports()
        
        # On macOS, filter to only include USB devices
        if sys.platform == 'darwin':
            filtered_ports = []
            for port in port_list:
                # Check if the device name contains 'usb' (case insensitive)
                device_name = str(port.device).lower()
                port_name = str(port.name).lower() if port.name else ''
                description = str(port.description).lower() if port.description else ''
                
                if 'usb' in device_name or 'usb' in port_name or 'usb' in description:
                    filtered_ports.append(port)
            return filtered_ports
        
        return port_list

    @classmethod
    def init_laser_stj_10m0(cls, test_name: TestNameLeveling, announce: bool = True) -> dict[Mount, LaserSensor]:
        """
        initial the laser stj-10m0 sensor
        :return:
        """
        port_list: list = cls.get_com_list()
        expected_mounts = cls.expected_mounts(test_name)
        if announce:
            ui.fixture_search([mount.value for mount in expected_mounts])
        lasers = {}
        for port in port_list:
            laser = LaserSensor()
            try:
                with redirect_stdout(io.StringIO()):
                    laser.init_device(select_default=port.device)
                with redirect_stdout(io.StringIO()):
                    mount_str = laser.get_mount(quiet=True)
                found_mount = None
                if mount_str == Mount.LEFT.value:
                    found_mount = Mount.LEFT
                elif mount_str == Mount.RIGHT.value:
                    found_mount = Mount.RIGHT

                if found_mount in expected_mounts and found_mount not in lasers:
                    lasers[found_mount] = laser
                    if announce:
                        ui.fixture_found(found_mount.value)
                else:
                    cls._close_unused_laser(laser)

                if all(mount in lasers for mount in expected_mounts):
                    break
            except ValueError:
                cls._close_unused_laser(laser)
                continue
            except serial.SerialException as exc:
                cls._close_unused_laser(laser)
                raise SensorReadError(f"{type(exc).__name__}: {exc}") from exc
        missing_mounts = [mount for mount in expected_mounts if mount not in lasers]
        if missing_mounts:
            details = "Missing mounts: " + ", ".join(mount.value for mount in missing_mounts)
            raise FixtureNotFoundError(missing_mounts[0], details=details)
        return lasers

    @staticmethod
    def expected_mounts(test_name: TestNameLeveling) -> list[Mount]:
        if test_name in (TestNameLeveling.CH96_Leveling, TestNameLeveling.Gripper_Leveling):
            return [Mount.LEFT]
        return [Mount.LEFT, Mount.RIGHT]

    @staticmethod
    def _close_unused_laser(laser: LaserSensor) -> None:
        try:
            with redirect_stdout(io.StringIO()):
                laser.close()
        except Exception:
            pass
