"""
Define the property and method for leveling testing
"""
import os
import time
from abc import ABC, abstractmethod
from test_cli.core.maintenance_api.maintenance_run import MaintenanceApi
from typing import Union, Optional
from test_cli.leveling_test.type import SlotName, TestNameLeveling, Direction, Mount, Point
from test_cli.leveling_test.config import get_slot_config, SlotConfig
from typing import Callable, Any
from devices.laser_stj_10_m0 import LaserSensor
from test_cli.core.hardware_control.hardware_control import HardwareControl
from test_cli.leveling_test.report.report import LevelingCSV
from test_cli.leveling_test.simulation import SimulatedHardwareControl, SimulatedMaintenanceApi
from test_cli.leveling_test.errors import FixtureNotFoundError, SensorReadError
from test_cli.leveling_test.retry import retry_hardware_action, SENSOR_EXCEPTIONS
from test_cli.leveling_test.fixture.reader import Reader
from test_cli.cli import ui


class LevelingBase(ABC):
    def __init__(self, robot_ip_address: str, simulate: bool = False):
        self.robot_ip_address = robot_ip_address
        self.simulate = simulate
        self.maintenance_api: Optional[MaintenanceApi] = None
        self.slot_config: Optional[SlotConfig] = None
        self.current_point: Optional[Point] = None
        self.laser: Optional[LaserSensor] = None
        self.lasers: dict[Mount, Optional[LaserSensor]] = {Mount.RIGHT: None, Mount.LEFT: None}
        self.laser_result = {}
        self.__add_compensation = True
        self.__spec = 0.15
        self.__z_position = 505.0
        self.__hc = SimulatedHardwareControl() if simulate else HardwareControl(robot_ip_address)
        self.__robot_serial_number = ""
        self.__operator_name = ""
        self.report: Union[LevelingCSV, None] = None
        self._reconnecting_reader = False

    def update_slot_config(self, test_name: TestNameLeveling, mount: Mount, slot_name: SlotName, direction: Direction):
        slot_config = get_slot_config(test_name, mount, slot_name, direction)
        self.slot_config = slot_config

    def build_report(self, csv_name:str, script_dir:str, test_name:TestNameLeveling):
        self.report = LevelingCSV(
            csv_name,
            os.path.join(script_dir, 'testing_data'),
            test_name,
            self.robot_sn,
            self.operator_name,
        )

    def release_laser(self):
        try:
            for key, item in self.lasers.items():
                if item is None:
                    continue
                ui.info(ui.bilingual(f"Release {key.value}", f"释放 {key.value}"))
                item.close()
                self.lasers[key] = None
        except Exception as e:
            raise e

    @property
    def robot_sn(self) -> str:
        return self.__robot_serial_number

    @robot_sn.setter
    def robot_sn(self, val: str):
        if not isinstance(val, str):
            raise TypeError("robot sn expected to be string")
        self.__robot_serial_number = val

    @property
    def operator_name(self) -> str:
        return self.__operator_name

    @operator_name.setter
    def operator_name(self, val: str):
        if not isinstance(val, str):
            raise TypeError("operator name expected to be string")
        self.__operator_name = val

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
    def expected_mounts(self) -> list[Mount]:
        return [Mount.LEFT, Mount.RIGHT]

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

    def require_laser(self, mount: Mount | None = None) -> LaserSensor:
        laser = self.laser if mount is None else self.lasers.get(mount)
        if laser is None:
            raise FixtureNotFoundError(mount)
        return laser

    def require_lasers(self, mounts: list[Mount]) -> None:
        for mount in mounts:
            if self.lasers.get(mount) is None:
                raise FixtureNotFoundError(mount)

    def read_default_distance(self) -> float:
        if self.slot_config is None:
            raise ValueError("Slot config is not initialized")
        result = self.read_sensor()
        channel = self.slot_config.channel
        if not channel:
            raise SensorReadError(
                f"No channel definition for {self.slot_config.mount.value} {self.slot_config.slot_name.name}",
                recoverable=False,
            )
        default_channel = list(channel.values())[0]
        try:
            return result[default_channel]
        except KeyError as exc:
            raise SensorReadError(f"Missing sensor channel: {default_channel}", recoverable=False) from exc

    def mark_calibration_success(self) -> None:
        ui.success(ui.bilingual("Calibration successful", "校准完成"))

    def show_out_of_spec(self, difference: float, attempt_index: int, max_attempts: int) -> None:
        slot = self.slot_config.slot_name.name if self.slot_config else None
        ui.spec_exceeded(difference, self.spec, attempt_index + 1, max_attempts, slot=slot)

    def read_sensor(self, delay: int = 6) -> dict[int, float]:
        notified = False
        while True:
            try:
                return Reader.read_sensor(self.require_laser(), delay=delay)
            except SensorReadError as exc:
                if self.simulate or not exc.recoverable:
                    raise
                if not notified:
                    ui.hardware_disconnected("read laser sensor", exc)
                    notified = True
                self.reconnect_reader()
                time.sleep(3)
            except SENSOR_EXCEPTIONS as exc:
                if self.simulate:
                    raise
                if not notified:
                    ui.hardware_disconnected("read laser sensor", exc)
                    notified = True
                self.reconnect_reader()
                time.sleep(3)

    def reconnect_reader(self) -> None:
        try:
            self.release_laser()
        except Exception:
            pass
        self._reconnecting_reader = True
        try:
            self.build_reader()
        finally:
            self._reconnecting_reader = False
        if self.slot_config is not None:
            self.laser = self.lasers.get(self.slot_config.mount)
        if all(self.lasers.get(mount) is not None for mount in self.expected_mounts):
            ui.hardware_reconnected()

    async def run_leveling_trials(self, spec: float, max_attempts: int = 3) -> None:
        self.spec = spec
        for i in range(max_attempts):
            await self.move_to_slot(self.calibration_callback)
            result = self.read_sensor()
            result, difference = self.reader_handler(result)
            self.show_result(result, difference, with_compensation=False)
            result, difference = self.apply_compensation()
            self.show_result(result, difference, with_compensation=True)

            csv_result = result.copy()
            if self.is_pass:
                csv_result.update({"result": difference})
                self.report.write_new_results(csv_result, passed=True)
                await self.home_z()
                return

            self.show_out_of_spec(difference, i, max_attempts)
            if i == max_attempts - 1:
                csv_result.update({"result": difference})
                self.report.write_new_results(csv_result, passed=False)
            await self.home_z()

    def apply_compensation(self) -> tuple[dict[str, float], float]:
        """
        apply compensation
        :return:
        """
        if self.add_compensation:
            compensation = self.slot_config.compensation
            for key, value in self.laser_result.items():
                # Handle key mapping: e.g., "below_rear" -> "rear", "left_rear" -> "rear"
                comp_key = key
                if key not in compensation:
                    # Try to find matching compensation key
                    for comp_k in compensation.keys():
                        if comp_k in key or key.endswith(comp_k) or key.startswith(comp_k):
                            comp_key = comp_k
                            break
                    else:
                        # If no match found, try common patterns
                        if "rear" in key and "rear" in compensation:
                            comp_key = "rear"
                        elif "front" in key and "front" in compensation:
                            comp_key = "front"
                        elif "left" in key and "left" in compensation:
                            comp_key = "left"
                        elif "right" in key and "right" in compensation:
                            comp_key = "right"
                self.laser_result[key] = value + compensation.get(comp_key, 0)
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
        rows = [("Slot", self.slot_config.slot_name.name), ("Difference", str(difference))]
        rows.extend((key.upper(), str(round(value, 3))) for key, value in result.items())
        ui.section(f"Reading Result {with_compensation}".strip())
        ui.run_summary(rows)

    def reader_handler(self, result: dict[int, float]) -> tuple[dict[str, float], float]:
        """
        handle the reader result,
        :param result:
        :return: the result and the difference
        """
        channel = self.slot_config.channel
        if not channel:
            raise ValueError(
                f"No channel definition for {self.slot_config.mount.value} "
                f"{self.slot_config.slot_name.name}"
            )
        self.laser_result.clear()
        for key, value in channel.items():
            try:
                self.laser_result.update({key: result[value]})
            except KeyError as exc:
                raise SensorReadError(f"Missing sensor channel: {value}", recoverable=False) from exc
        return self.laser_result, round(
            abs(max(list(self.laser_result.values())) - min(list(self.laser_result.values()))), 3)

    async def init_slot(self, test_name: TestNameLeveling, mount: Mount, slot_name: SlotName, direction: Direction):
        if self.maintenance_api is None:
            await self.__build_api()
        self.update_slot_config(test_name, mount, slot_name, direction)

    async def __build_api(self) -> None:
        api_cls = SimulatedMaintenanceApi if self.simulate else MaintenanceApi
        self.maintenance_api = api_cls(self.ip_address)
        await self._hardware("create maintenance run", self.maintenance_api.create_run)

    async def build_api(self) -> None:
        await self.__build_api()

    async def _hardware(self, action: str, func):
        return await retry_hardware_action(action, func, simulate=self.simulate)

    async def cleanup(self) -> None:
        try:
            await self.home()
        except Exception as exc:
            ui.warning(ui.bilingual(f"Home during cleanup failed: {exc}", "清理阶段 home 失败"))
        if self.maintenance_api is not None and self.maintenance_api.run_id is not None:
            try:
                await self.maintenance_api.delete_run()
            except Exception as exc:
                ui.warning(ui.bilingual(f"Maintenance run cleanup failed: {exc}", "清理 maintenance run 失败"))
        try:
            self.release_laser()
        except Exception as exc:
            ui.warning(ui.bilingual(f"Laser cleanup failed: {exc}", "清理激光传感器失败"))

    async def move_up(self, step):
        if self.current_point is None:
            return NotImplemented
        new_point = self.current_point + Point(x=0, y=0, z=step)
        await self._hardware(
            f"move up {step}",
            lambda: self.maintenance_api.move_to(new_point._asdict(), self.slot_config.mount),
        )
        if self.simulate and self.laser is not None:
            self.laser.nudge_towards_target(step)
        self.current_point = new_point
        return True

    async def move_down(self, step):
        if self.current_point is None:
            return NotImplemented
        new_point = self.current_point - Point(x=0, y=0, z=step)
        await self._hardware(
            f"move down {step}",
            lambda: self.maintenance_api.move_to(new_point._asdict(), self.slot_config.mount),
        )
        if self.simulate and self.laser is not None:
            self.laser.nudge_towards_target(step)
        self.current_point = new_point
        return True

    async def move_left(self, step):
        if self.current_point is None:
            return NotImplemented
        new_point = self.current_point - Point(x=step, y=0, z=0)
        await self._hardware(
            f"move left {step}",
            lambda: self.maintenance_api.move_to(new_point._asdict(), self.slot_config.mount),
        )
        if self.simulate and self.laser is not None:
            self.laser.nudge_towards_target(step)
        self.current_point = new_point
        return True

    async def move_right(self, step):
        if self.current_point is None:
            return NotImplemented
        new_point = self.current_point + Point(x=step, y=0, z=0)
        await self._hardware(
            f"move right {step}",
            lambda: self.maintenance_api.move_to(new_point._asdict(), self.slot_config.mount),
        )
        if self.simulate and self.laser is not None:
            self.laser.nudge_towards_target(step)
        self.current_point = new_point
        return True

    async def move_forward(self, step):
        if self.current_point is None:
            return NotImplemented
        new_point = self.current_point + Point(x=0, y=step, z=0)
        await self._hardware(
            f"move forward {step}",
            lambda: self.maintenance_api.move_to(new_point._asdict(), self.slot_config.mount),
        )
        if self.simulate and self.laser is not None:
            self.laser.nudge_towards_target(step)
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
        await self._hardware(
            f"move back {step}",
            lambda: self.maintenance_api.move_to(new_point._asdict(), self.slot_config.mount),
        )
        if self.simulate and self.laser is not None:
            self.laser.nudge_towards_target(step)
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
        await self._hardware(
            f"move {mount.value} to {self.slot_config.slot_name.name} safe Z",
            lambda: self.maintenance_api.move_to(point.replace({"z": self.z_position})._asdict(), mount),
        )
        await self._hardware(
            f"move {mount.value} to {self.slot_config.slot_name.name}",
            lambda: self.maintenance_api.move_to(point._asdict(), mount),
        )
        self.current_point = point
        if calibration_func_callback is not None and callable(calibration_func_callback):
            await calibration_func_callback()
        return True

    async def home_z_then_move_to_slot(self):
        await self.home_z()
        await self.move_to_slot()

    async def home_z(self):
        if self.current_point is None:
            raise ValueError("Current Point Cannot be None")
        await self._hardware(
            f"home {self.slot_config.mount.value} z",
            lambda: self.maintenance_api.home_z(self.slot_config.mount, self.current_point),
        )

    async def home(self):
        await self._hardware("home robot", self.__hc.home)
