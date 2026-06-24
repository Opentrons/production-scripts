from test_cli.leveling_test.model.base import LevelingBase
from test_cli.leveling_test.type import SlotName, TestNameLeveling, Mount, Direction
from test_cli.leveling_test.fixture.reader import Reader
from devices.laser_stj_10_m0 import LaserSensor
import asyncio
import os
from test_cli.leveling_test.report.report import LevelingCSV
from typing import Union
from test_cli.leveling_test.simulation import SimulatedLaserSensor
from test_cli.cli import ui


class CH8_Leveling(LevelingBase):
    def __init__(self, robot_ip_address: str, test_name=TestNameLeveling.CH8_Leveling,
                 script_dir=os.path.dirname(os.path.abspath(__file__)), simulate: bool = False):
        super().__init__(robot_ip_address, simulate=simulate)
        self.test_name = test_name
        self.judge_complete = False
        self.__spec = 0.25
        self.script_dir = script_dir
        self.report: Union[LevelingCSV, None] = None

    def __str__(self):
        return self.test_name.name.upper()

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
            if step > 0:
                await self.move_left(abs(step))
            else:
                await self.move_right(abs(step))
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
            self.build_report("CH8_Leveling_Test.csv", self.script_dir, self.test_name)

            slot_list = {
                Mount.LEFT: [SlotName.C1],
                Mount.RIGHT: [SlotName.A2, SlotName.C1, SlotName.C3]
            }
            self.report.update_create_time()
            self.report.create_csv_path()
            await self.home()
            # 初始化laser
            self.build_reader()
            self.report.init_title()
            # 遍历所有slot
            for mount in [Mount.RIGHT, Mount.LEFT]:
                _slot_list = slot_list[mount]
                self.laser = self.lasers[mount]
                for slot_name in _slot_list:
                    # build api and init slot config
                    await self.init_slot(self.test_name, mount, slot_name, Direction.Y)
                    # run trial
                    await self.run_trials()
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
            self.lasers = {
                Mount.LEFT: SimulatedLaserSensor("ch8-left"),
                Mount.RIGHT: SimulatedLaserSensor("ch8-right"),
            }
            return
        reader_type = self._reader_type
        if reader_type is LaserSensor:
            self.lasers = Reader.init_laser_stj_10m0(
                TestNameLeveling.CH8_Leveling,
                announce=not self._reconnecting_reader,
            )
            self.require_lasers([Mount.LEFT, Mount.RIGHT])


if __name__ == '__main__':
    try:
        ch8_leveling = CH8_Leveling(robot_ip_address="192.168.6.15")
        asyncio.run(ch8_leveling.run())
        input("测试结束...")
    except Exception as e:
        ui.exception_report(e, debug=True)
