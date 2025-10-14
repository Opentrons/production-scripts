"""
Define the property and method for leveling testing
"""

from abc import ABC, abstractmethod
from ot3_testing.maintenance_api.maintenance_run import MaintenanceApi
from typing import Union, Optional
from ot3_testing.leveling_test.type import SlotName, TestNameLeveling, Direction, Mount, Point
from ot3_testing.leveling_test.require_config import get_slot_config, SlotConfig
from typing import Callable, Any
from devices.laser_stj_10_m0 import LaserSensor
from ot3_testing.hardware_control.hardware_control import HardwareControl


class LevelingBase(ABC):
    def __init__(self, robot_ip_address: str, test_name: TestNameLeveling):
        self.robot_ip_address = robot_ip_address
        self.maintenance_api: Union[None, MaintenanceApi] = None
        self.slot_config: Union[None, SlotConfig] = None
        self.current_point: Union[None, Point] = None
        self.laser: Optional[LaserSensor] = None
        self.laser_result = {}
        self.__add_compensation = True
        self.__spec = 0.15
        self.__z_position = 509.0
        self.__hc = HardwareControl(robot_ip_address)
        self.__robot_serial_number = ""

    def update_slot_config(self, test_name: TestNameLeveling, mount: Mount, slot_name: SlotName, direction: Direction):
        slot_config = get_slot_config(test_name, mount, slot_name, direction)
        self.slot_config = slot_config

    @property
    def robot_sn(self) -> str:
        return self.__robot_serial_number

    @robot_sn.setter
    def robot_sn(self, val: str):
        if not isinstance(val, str):
            raise TypeError("robot sn expected to be string")
        self.__robot_serial_number = val

    @property
    def z_position(self) -> float:
        return self.__z_position

    @property
    def add_compensation(self) -> bool:
        return self.__add_compensation

    @add_compensation.setter
    def add_compensation(self, val: bool):
        if not isinstance(val, bool):
            raise TypeError("add_compensation should be bool")
        self.__add_compensation = val

    @property
    def spec(self) -> float:
        return self.__spec

    @spec.setter
    def spec(self, spec):
        self.__spec = spec

    @property
    def _reader_type(self):
        return LaserSensor

    @abstractmethod
    async def run_trials(self):
        pass

    @abstractmethod
    def build_reader(self):
        pass

    @abstractmethod
    async def run(self):
        pass

    @property
    def is_pass(self) -> bool:
        if self.laser_result != {}:
            diff = round(abs(max(list(self.laser_result.values())) - min(list(self.laser_result.values()))), 3)
            return diff <= self.spec
        else:
            raise Exception("No Laser Result Found")

    @property
    def ip_address(self) -> str:
        return self.robot_ip_address

    @abstractmethod
    async def calibration_callback(self):
        pass

    def apply_compensation(self) -> tuple[dict[str, float], float]:
        """
        apply compensation
        :return:
        """
        if self.add_compensation:
            compensation = self.slot_config.compensation
            for key, value in self.laser_result.items():
                self.laser_result[key] = value + compensation[key]
        return self.laser_result, round(
            abs(max(list(self.laser_result.values())) - min(list(self.laser_result.values()))), 3)

    def show_result(self, result: dict[str, float], difference: float, with_compensation: bool):
        """
        show a reading
        :param result:
        :param difference:
        :param with_compensation:
        :return:
        """
        with_compensation = "With Compensation" if with_compensation else ""
        print(f"----Reading Result {with_compensation}----\n"
              f"SLOT: {self.slot_config.slot_name.name}\n"
              f"Difference: {difference}")
        for key, value in result.items():
            print(f"{key.upper()}: {round(value, 3)}")
        print("\n")

    def reader_handler(self, result: dict[int, float]) -> tuple[dict[str, float], float]:
        """
        handle the reader result,
        :param result:
        :return: the result and the difference
        """
        channel = self.slot_config.channel
        for key, value in channel.items():
            self.laser_result.update({key: result[value]})
        return self.laser_result, round(
            abs(max(list(self.laser_result.values())) - min(list(self.laser_result.values()))), 3)

    async def init_slot(self, test_name: TestNameLeveling, mount: Mount, slot_name: SlotName, direction: Direction):
        if self.maintenance_api is None:
            await self.__build_api()
        self.update_slot_config(test_name, mount, slot_name, direction)

    async def __build_api(self) -> None:
        self.maintenance_api = MaintenanceApi(self.ip_address)
        await self.maintenance_api.create_run()

    async def move_up(self, step):
        if self.current_point is None:
            return NotImplemented
        new_point = self.current_point + Point(x=0, y=0, z=step)
        await self.maintenance_api.move_to(new_point._asdict(), self.slot_config.mount)
        self.current_point = new_point
        return True

    async def move_down(self, step):
        if self.current_point is None:
            return NotImplemented
        new_point = self.current_point - Point(x=0, y=0, z=step)
        await self.maintenance_api.move_to(new_point._asdict(), self.slot_config.mount)
        self.current_point = new_point
        return True

    async def move_left(self, step):
        if self.current_point is None:
            return NotImplemented
        new_point = self.current_point - Point(x=step, y=0, z=0)
        await self.maintenance_api.move_to(new_point._asdict(), self.slot_config.mount)
        self.current_point = new_point
        return True

    async def move_right(self, step):
        if self.current_point is None:
            return NotImplemented
        new_point = self.current_point + Point(x=step, y=0, z=0)
        await self.maintenance_api.move_to(new_point._asdict(), self.slot_config.mount)
        self.current_point = new_point
        return True

    async def move_forward(self, step):
        if self.current_point is None:
            return NotImplemented
        new_point = self.current_point + Point(x=0, y=step, z=0)
        await self.maintenance_api.move_to(new_point._asdict(), self.slot_config.mount)
        self.current_point = new_point
        return True

    async def move_back(self, step):
        """
        move back
        :param step:
        :return:
        """
        if self.current_point is None:
            return NotImplemented
        new_point = self.current_point - Point(x=0, y=step, z=0)
        await self.maintenance_api.move_to(new_point._asdict(), self.slot_config.mount)
        self.current_point = new_point
        return True

    async def move_to_slot(self, calibration_func_callback: Optional[Callable[..., Any]] = None) -> bool:
        """
        move to slot
        :param calibration_func_callback: calibrate the fixture to the available position
        :return: True or NotImplemented
        """
        if self.maintenance_api is None or self.slot_config is None:
            return NotImplemented
        mount: Mount = self.slot_config.mount
        point: Point = self.slot_config.point
        await self.maintenance_api.move_to(point.replace({"z": self.z_position})._asdict(), mount)
        await self.maintenance_api.move_to(point._asdict(), mount)
        self.current_point = point
        if calibration_func_callback is not None and callable(calibration_func_callback):
            try:
                await calibration_func_callback()
            except Exception as e:
                print(f"校准回调执行失败: {e}")
        return True

    async def home_z_then_move_to_slot(self):
        await self.home_z()
        await self.move_to_slot()

    async def home_z(self):
        if self.current_point is None:
            raise ValueError("Current Point Cannot be None")
        await self.maintenance_api.home_z(self.slot_config.mount, self.current_point)

    async def home(self):
        await self.__hc.home()
