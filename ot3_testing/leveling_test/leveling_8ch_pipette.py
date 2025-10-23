from ot3_testing.leveling_test.model.base import LevelingBase
from ot3_testing.leveling_test.type import SlotName, TestNameLeveling, Mount, Direction
from ot3_testing.leveling_test.fixture.reader import Reader
from devices.laser_stj_10_m0 import LaserSensor
import asyncio
import traceback
import os
from ot3_testing.leveling_test.csv.report import LevelingCSV
from typing import Union


class CH8_Leveling(LevelingBase):
    def __init__(self, robot_ip_address: str, test_name=TestNameLeveling.CH8_Leveling):
        super().__init__(robot_ip_address)
        self.test_name = test_name
        self.judge_complete = False
        self.__spec = 0.25
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.report: Union[LevelingCSV, None] = None

    def __str__(self):
        return self.test_name.name.upper()

    async def calibration_callback(self) -> None:
        """
        calibrate the fixture, make the distance close 30mm
        :return:
        """
        if self.laser is None:
            raise Exception("No Laser Found")

        def read_default_channel() -> float:
            result = Reader.read_sensor(self.laser)
            channel = self.slot_config.channel
            default_channel = list(channel.values())[0]
            distance = result[default_channel]
            return distance

        default_distance = read_default_channel()
        cli = False
        while True:
            step = default_distance - 30
            print("===Calibration===\n"
                  f"DefaultDistance: {default_distance}\n"
                  f"Step: {round(step, 3)}\n")
            if cli:
                break
            if step > 0:
                await self.move_left(abs(step))
            else:
                await self.move_right(abs(step))
            default_distance = read_default_channel()
            if abs(default_distance - 30) < 0.1:
                cli = True
        print("Calibration Successful !")

    async def run_trials(self) -> None:
        """
        run a trial
        :return:
        """
        for i in range(3):
            # step1: move to slot
            await self.move_to_slot(self.calibration_callback)
            # step2: read result
            result = Reader.read_sensor(self.laser)
            # step3: show result
            result, difference = self.reader_handler(result)
            self.show_result(result, difference, with_compensation=False)
            result, difference = self.apply_compensation()
            self.show_result(result, difference, with_compensation=True)
            # step4: set spec
            self.spec = self.__spec
            csv_result = result.copy()
            if self.is_pass:
                csv_result.update({"result": difference})
                self.report.write_new_results(csv_result)
                # home
                await self.home_z()
                break
            else:
                if i < 2:
                    print(f"The test result out of the spec, {self.spec}, try to retest {i + 1} times")
                else:
                    csv_result.update({"result": difference})
                    self.report.write_new_results(csv_result)
                await self.home_z()

    async def run(self):
        try:
            #  定义初始化参数
            self.add_compensation = True
            self.build_report("CH8_Leveling_Test.csv", self.script_dir, self.test_name)

            slot_list = {
                Mount.LEFT: [SlotName.C1],
                Mount.RIGHT: [SlotName.A2, SlotName.C1, SlotName.C3]
            }
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
            self.release_laser()
        except KeyboardInterrupt("Customer exit"):
            pass
        except Exception():
            traceback.print_exc()
        finally:
            await self.home()
            await self.maintenance_api.delete_run()
            self.release_laser()

    def build_reader(self):
        for mount in [Mount.RIGHT, Mount.LEFT]:
            reader_type = self._reader_type
            if reader_type is LaserSensor:
                self.laser = Reader.init_laser_stj_10m0(mount)
                if self.laser is not None or NotImplemented:
                    self.lasers[mount] = self.laser


if __name__ == '__main__':
    ch8_leveling = CH8_Leveling(robot_ip_address="192.168.6.15")
    asyncio.run(ch8_leveling.run())
    input("测试结束...")
