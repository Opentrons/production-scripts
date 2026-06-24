from test_cli.leveling_test.model.base import LevelingBase
from test_cli.leveling_test.type import SlotName, TestNameLeveling, Mount, Direction
from test_cli.leveling_test.fixture.reader import Reader
from devices.laser_stj_10_m0 import LaserSensor
import asyncio
import os
from test_cli.leveling_test.report.report import LevelingCSV
from typing import Union, Optional
from test_cli.leveling_test.simulation import SimulatedLaserSensor
from test_cli.cli import ui


class Gripper_Leveling(LevelingBase):
    def __init__(self, robot_ip_address: str, test_name=TestNameLeveling.Gripper_Leveling,
                 script_dir=os.path.dirname(os.path.abspath(__file__)), simulate: bool = False):
        super().__init__(robot_ip_address, simulate=simulate)
        self.test_name = test_name
        self.__spec = 0.5
        self.script_dir = script_dir
        self.report: Union[LevelingCSV, None] = None
        self.laser: Optional[LaserSensor] = None
        self.__direction: Optional[Direction] = None

    def __str__(self):
        return self.test_name.name.upper()

    @property
    def expected_mounts(self) -> list[Mount]:
        return [Mount.LEFT]

    async def calibration_callback(self) -> None:
        """
        calibrate the fixture, make the distance close 30mm
        :return:
        """
        self.require_laser()
        default_distance = self.read_default_distance()
        cli = False
        while True:
            step = default_distance - 30
            ui.calibration(default_distance, step)
            if cli:
                break
            if self.__direction == Direction.X:
                await self.move_forward(abs(step)) if step < 0 else await self.move_back(abs(step))
            elif self.__direction == Direction.Y:
                await self.move_right(abs(step)) if step < 0 else await self.move_left(abs(step))
            elif self.__direction == Direction.Z:
                cli = True
            else:
                raise ValueError("Wrong direction")
            default_distance = self.read_default_distance()
            if abs(default_distance - 30) < 0.1:
                cli = True
        self.mark_calibration_success()

    async def run_trials(self) -> None:
        """
        run a trial
        :return:
        """
        await self.run_leveling_trials(self.__spec)

    async def run(self):
        try:
            #  定义初始化参数
            self.add_compensation = True
            self.build_report("Gripper_Leveling_Test.csv", self.script_dir, self.test_name)

            slot_list = {Mount.LEFT: {
                Direction.X: [SlotName.C2],
                Direction.Y: [SlotName.C2],
                Direction.Z: [SlotName.C2]
            }}
            self.report.update_create_time()
            self.report.create_csv_path()
            await self.home()
            # 初始化laser
            self.build_reader()
            self.report.init_title()
            # 遍历所有slot
            for mount in [Mount.LEFT]:
                _slot_list = slot_list[mount]
                self.laser = self.lasers[mount]
                for direction, slot_name_list in _slot_list.items():
                    # build api and init slot config
                    self.__direction = direction
                    for slot_name in slot_name_list:
                        await self.init_slot(self.test_name, mount, slot_name, direction)
                        # run trial
                        await self.run_trials()
                    await self.home()
            self.report.finish_test()
            self.release_laser()
        except KeyboardInterrupt:
            ui.warning(ui.bilingual("User cancelled the test", "用户中断测试"))
            raise
        except Exception:
            raise
        finally:
            await self.cleanup()

    def build_reader(self):
        if self.simulate:
            self.lasers = {Mount.LEFT: SimulatedLaserSensor("gripper-left")}
            return
        reader_type = self._reader_type
        if reader_type is LaserSensor:
            self.lasers = Reader.init_laser_stj_10m0(
                TestNameLeveling.Gripper_Leveling,
                announce=not self._reconnecting_reader,
            )
            self.require_lasers([Mount.LEFT])


if __name__ == '__main__':
    try:
        gripper_leveling = Gripper_Leveling(robot_ip_address="192.168.6.88")
        asyncio.run(gripper_leveling.run())
        input("测试结束...")
    except Exception as e:
        ui.exception_report(e, debug=True)
