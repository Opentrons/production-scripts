from devices.laser_stj_10_m0 import LaserSensor
from dataclasses import dataclass
from typing import Any, Protocol, Union
from ot3_testing.leveling_test.type import Mount, TestNameLeveling
import serial
import serial.tools.list_ports
from typing import List
import time


# 定义协议接口
class ReadableSensor(Protocol):
    def read_sensor_low(self, show_distance: bool = ...) -> Any: ...


@dataclass
class Reader:
    @staticmethod
    def read_sensor(laser: ReadableSensor, delay=6) -> dict[int, float]:
        for i in range(delay):
            print(f"Waiting {i + 1}/(6) s...")
            time.sleep(1)
        result = laser.read_sensor_low(show_distance=True)  # duck typing
        return result

    @classmethod
    def get_com_list(cls) -> List[serial.tools.list_ports_common.ListPortInfo]:
        port_list = serial.tools.list_ports.comports()
        return port_list

    @classmethod
    def init_laser_stj_10m0(cls, test_name: TestNameLeveling) -> Union[dict[Mount, LaserSensor], bool]:
        """
        initial the laser stj-10m0 sensor
        :return:
        """
        port_list: list = cls.get_com_list()
        lasers = {}
        try:
            for port in port_list:
                laser = LaserSensor()
                laser.init_device(select_default=port.device)
                if test_name == TestNameLeveling.CH96_Leveling or test_name == TestNameLeveling.Gripper_Leveling:
                    lasers[Mount.LEFT] = laser
                else:
                    mount_str = laser.get_mount()
                    if mount_str == Mount.LEFT.value:
                        lasers[Mount.LEFT] = laser
                    elif mount_str == Mount.RIGHT.value:
                        lasers[Mount.RIGHT] = laser
                    else:
                        pass
            if lasers == {}:
                print("NO LASER SENSOR FOUND")
                return False
            else:
                return lasers
        except serial.SerialException as e:
            print(e)
            return NotImplemented
