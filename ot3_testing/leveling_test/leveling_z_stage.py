from ot3_testing.leveling_test.model.base import LevelingBase
from ot3_testing.leveling_test.type import SlotName, TestNameLeveling, Mount, Direction
from ot3_testing.leveling_test.fixture.reader import Reader
from devices.laser_stj_10_m0 import LaserSensor
from drivers.play_sound import play_alarm_3
import asyncio
import threading
import traceback
import os
from ot3_testing.leveling_test.csv.report import LevelingCSV


class Z_Leveling(LevelingBase):
    def __init__(self, robot_ip_address: str, test_name= TestNameLeveling.Z_Leveling):
        super().__init__(robot_ip_address, test_name)
        self.test_name = test_name
        self.judge_complete = False
        self.___spec = 0.15
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.report = LevelingCSV("Z_Leveling_Test.csv",
                                  os.path.join(script_dir, 'testing_data'),
                                  self.test_name, self.robot_sn)

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
                await self.move_down(abs(step))
            else:
                await self.move_up(abs(step))
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

    async def judge_z_stage(self):
        """
        move to C2, and require rotate the screw to let the z stage leveling
        :return:
        """
        await self.init_slot(self.test_name, Mount.RIGHT, SlotName.C2, Direction.Z)
        # build reader
        if not self.build_reader():
            raise Exception("Build Reader Failed")
        await self.move_to_slot(calibration_func_callback=self.calibration_callback)

        def read_result():
            result = Reader.read_sensor(self.laser)
            _, diff = self.reader_handler(result)
            _, diff = self.apply_compensation()
            return _, diff

        def th_keep_reading():
            while True:
                _, _difference = read_result()
                difference = int(-_difference * 1500 + 1500)
                if difference < 200:
                    difference = 200
                if difference > 1500:
                    difference = 1500
                fre = 100 if _difference > 0.03 else 1000
                print(f"Diff: {_difference} (调节螺丝旋钮-> Diff = 0.03mm 后回车继续)")
                play_alarm_3(difference, fre)
                if self.judge_complete:
                    break

        th = threading.Thread(target=th_keep_reading)
        th.start()
        input("")
        self.judge_complete = True
        th.join()

    async def run(self):
        try:
            #  定义初始化参数
            self.add_compensation = True
            slot_list = {
                Mount.LEFT: [SlotName.C2],
                Mount.RIGHT: [SlotName.A1, SlotName.A2, SlotName.A3,
                              SlotName.B1, SlotName.B2, SlotName.B3,
                              SlotName.C1, SlotName.C2, SlotName.C3,
                              SlotName.D1, SlotName.D2, SlotName.D3]
            }
            self.report.create_csv_path()
            await self.home()
            # 调节C2里面Z轴平行
            await self.judge_z_stage()
            await self.home_z()
            # 遍历所有slot
            for mount in [Mount.RIGHT, Mount.LEFT]:
                # build reader
                if mount == self.slot_config.mount and self.laser is not None:
                    pass
                else:
                    if not self.build_reader():
                        raise Exception("Build Reader Failed")
                _slot_list = slot_list[mount]
                for slot_name in _slot_list:
                    # build api and init slot config
                    await self.init_slot(self.test_name, mount, slot_name, Direction.Z)
                    # home
                    await self.home_z()
                    # run tria
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
    z_leveling = Z_Leveling(robot_ip_address="192.168.6.15")
    asyncio.run(z_leveling.run())
    input("测试结束...")
