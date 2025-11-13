from adodbapi.ado_consts import directions

from ot3_testing.leveling_test.model.base import LevelingBase
from ot3_testing.leveling_test.type import SlotName, TestNameLeveling, Mount, Direction
from ot3_testing.leveling_test.fixture.reader import Reader
from devices.laser_stj_10_m0 import LaserSensor
import asyncio
import traceback
import os
from ot3_testing.leveling_test.report.report import LevelingCSV
from typing import Union, Optional


class Gripper_Leveling(LevelingBase):
    def __init__(self, robot_ip_address: str, test_name=TestNameLeveling.Gripper_Leveling,
                 script_dir=os.path.dirname(os.path.abspath(__file__))):
        super().__init__(robot_ip_address)
        self.test_name = test_name
        self.__spec = 0.5
        self.script_dir = script_dir
        self.report: Union[LevelingCSV, None] = None
        self.laser: Optional[LaserSensor] = None
        self.__direction: Optional[Direction] = None

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
            if self.__direction == Direction.X:
                await self.move_forward(abs(step)) if step < 0 else await self.move_back(abs(step))
            elif self.__direction == Direction.Y:
                await self.move_right(abs(step)) if step < 0 else await self.move_left(abs(step))
            elif self.__direction == Direction.Z:
                cli = True
            else:
                raise ValueError("Wrong direction")
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
            await self.move_to_slot(calibration_func_callback=self.calibration_callback)
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
            self.release_laser()
        except KeyboardInterrupt("Customer exit"):
            pass
        except Exception():
            traceback.print_exc()
        finally:
            await self.home()
            await self.build_api()
            await self.maintenance_api.delete_run()
            self.release_laser()

    def build_reader(self):
        reader_type = self._reader_type
        if reader_type is LaserSensor:
            try:
                laser_dict = Reader.init_laser_stj_10m0(TestNameLeveling.Gripper_Leveling)
                self.lasers = laser_dict
                # check laser
                if self.lasers:
                    for mount in [Mount.LEFT]:
                        if mount in self.lasers:
                            pass
                        else:
                            print(f"Laser on Mount {mount.value} not found (未找到测试工装！)")
                            raise
                else:
                    print(f"Laser not found (未找到测试工装！)")
                    raise
            except Exception as e:
                print(e)
                raise


if __name__ == '__main__':
    gripper_leveling = Gripper_Leveling(robot_ip_address="192.168.6.88")
    asyncio.run(gripper_leveling.run())
    input("测试结束...")
