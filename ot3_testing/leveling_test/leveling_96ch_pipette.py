from ot3_testing.leveling_test.model.base import LevelingBase
from ot3_testing.leveling_test.type import SlotName, TestNameLeveling, Mount, Direction
from ot3_testing.leveling_test.fixture.reader import Reader
from devices.laser_stj_10_m0 import LaserSensor
import asyncio
import traceback
import os
from ot3_testing.leveling_test.csv.report import LevelingCSV


class CH96_Leveling(LevelingBase):
    def __init__(self, robot_ip_address: str, test_name= TestNameLeveling.CH96_Leveling):
        super().__init__(robot_ip_address, test_name)
        self.test_name = test_name
        self.judge_complete = False
        self.__spec_xy = 0.25
        self.__spec_z = 0.35
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.report = LevelingCSV("CH96_Leveling_Test.csv",
                                  os.path.join(script_dir, 'testing_data'),
                                  self.test_name, self.robot_sn)
        self.__direction = Direction.X

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
            if self.__direction == Direction.Y:
                await self.move_left(abs(step)) if step >0 else await self.move_right(abs(step))
            elif self.__direction == Direction.X:
                await self.move_forward(abs(step)) if step > 0 else await self.move_back(abs(step))
            elif self.__direction == Direction.Z:
                await self.move_down(abs(step)) if step > 0 else await self.move_up(abs(step))
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
            if self.is_pass:
                result.update({"result": difference})
                self.report.write_new_results(result)
                break
            else:
                if i < 2:
                    print(f"The test result out of the spec, {self.spec}, try to retest {i + 1} times")
                    await self.home_z()
                else:
                    result.update({"result": difference})
                    self.report.write_new_results(result)

    async def run(self):
        try:
            #  定义初始化参数
            self.add_compensation = True
            slot_list = {
               Mount.LEFT: {
                   Direction.Y: [SlotName.A2, SlotName.C1, SlotName.C3],
                   Direction.X: [SlotName.A2, SlotName.C1, SlotName.C3],
                   Direction.Z: [SlotName.A2, SlotName.D1, SlotName.D3, SlotName.C2]
               }

            }
            self.report.create_csv_path()
            await self.home()
            # 遍历所有slot
            for mount in [Mount.RIGHT, Mount.LEFT]:
                # build reader
                if mount == self.slot_config.mount and self.laser is not None:
                    pass
                else:
                    if not self.build_reader():
                        raise Exception("Build Reader Failed")
                direction_setting = slot_list[mount]
                for direction, slot_name_list in direction_setting:
                    self.__direction = direction
                    if self.__direction in [Direction.X, Direction.Y]:
                        self.spec = self.__spec_xy
                    else:
                        self.spec = self.__spec_z
                    for slot_name in slot_name_list:
                        # build api and init slot config
                        await self.init_slot(self.test_name, mount, slot_name, self.__direction)
                        # home
                        await self.home_z()
                        # run trial
                        self.report.init_title()
                        await self.run_trials()
        except KeyboardInterrupt("Customer exit"):
            pass
        except Exception():
            traceback.print_exc()
        finally:
            await self.home()
            await self.maintenance_api.delete_run()

    def build_reader(self):
        reader_type = self._reader_type
        if reader_type is LaserSensor:
            if self.laser is not None:
                self.laser.close()
            self.laser = Reader.init_laser_stj_10m0(self.slot_config.mount)
            if self.laser is not None or NotImplemented:
                return True
        return False

if __name__ == '__main__':
    ch96_leveling = CH96_Leveling(robot_ip_address="192.168.6.15")
    asyncio.run(ch96_leveling.run())
    input("测试结束...")
