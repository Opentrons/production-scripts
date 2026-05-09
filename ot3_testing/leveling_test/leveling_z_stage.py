from ot3_testing.leveling_test.model.base import LevelingBase
from ot3_testing.leveling_test.type import SlotName, TestNameLeveling, Mount, Direction
from ot3_testing.leveling_test.fixture.reader import Reader
from devices.laser_stj_10_m0 import LaserSensor
from drivers.play_sound import play_alarm_3
import asyncio
import threading
import traceback
import os
import sys


class Z_Leveling(LevelingBase):
    def __init__(self, robot_ip_address: str, test_name=TestNameLeveling.Z_Leveling,
                 script_dir=os.path.dirname(os.path.abspath(__file__))):
        super().__init__(robot_ip_address)
        self.test_name = test_name
        self.judge_complete = False
        self.__spec = 0.25
        self.script_dir = script_dir

    def __str__(self):
        return self.test_name.name.upper()

    async def calibration_callback(self) -> None:
        """
        calibrate the fixture, make the distance close 30mm
        :return:
        """
        if self.laser is None:
            raise Exception("No Laser Found")

        try:
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
        except Exception as e:
            print(f"校准失败: {e}")
            raise

    async def run_trials(self) -> None:
        """
        run a trial
        :return:
        """
        try:
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
        except Exception as e:
            print(f"测试运行失败: {e}")
            raise

    async def judge_z_stage(self):
        """
        move to C2, and require rotate the screw to let the z stage leveling
        :return:
        """
        try:
            await self.init_slot(self.test_name, Mount.RIGHT, SlotName.C2, Direction.Z)
            # build reader
            self.laser = self.lasers[Mount.RIGHT]
            await self.move_to_slot(calibration_func_callback=self.calibration_callback)

            def read_result():
                result = Reader.read_sensor(self.laser, delay=0)
                _, diff = self.reader_handler(result)
                _, diff = self.apply_compensation()
                return _, diff

            def th_keep_reading():
                try:
                    while True:
                        _, _difference = read_result()
                        difference = int(-_difference * 1500 + 1500)
                        if difference < 200:
                            difference = 200
                        if difference > 1500:
                            difference = 1500
                        fre = 100 if _difference > 0.03 else 1000
                        print(f"Diff: {_difference} (调节螺丝旋钮-> Diff = 0.03mm 后回车继续)")
                        if sys.platform != 'darwin':
                            play_alarm_3(difference, fre)
                        if self.judge_complete:
                            break
                except Exception as e:
                    print(f"传感器读取异常: {e}")

            th = threading.Thread(target=th_keep_reading)
            th.start()
            input("")
            self.judge_complete = True
            th.join()
        except Exception as e:
            print(f"Z轴判断失败: {e}")
            raise

    async def run(self):
        try:
            #  定义初始化参数
            self.add_compensation = True
            self.build_report("Z_Leveling_Test.csv", self.script_dir, self.test_name)
            slot_list = {
                Mount.LEFT: [SlotName.C2],
                Mount.RIGHT: [SlotName.A1, SlotName.A2, SlotName.A3,
                              SlotName.B1, SlotName.B2, SlotName.B3,
                              SlotName.C1, SlotName.C2, SlotName.C3,
                              SlotName.D1, SlotName.D2, SlotName.D3]
            }
            self.report.update_create_time()
            self.report.create_csv_path()
            await self.home()
            # 初始化laser
            print("Initialing the serial devices")
            self.build_reader()
            # 调节C2里面Z轴平行
            await self.judge_z_stage()
            await self.home()
            self.report.init_title()
            # 遍历所有slot
            for mount in [Mount.RIGHT, Mount.LEFT]:
                _slot_list = slot_list[mount]
                self.laser = self.lasers[mount]
                for slot_name in _slot_list:
                    # build api and init slot config
                    await self.init_slot(self.test_name, mount, slot_name, Direction.Z)
                    # run tria
                    await self.run_trials()
                await self.home()
            self.release_laser()
        except KeyboardInterrupt:
            print("\n用户中断测试")
            raise
        except ConnectionError as e:
            print(f"连接错误: {e}")
            raise
        except TimeoutError as e:
            print(f"超时错误: {e}")
            raise
        except Exception as e:
            print(f"测试运行异常: {e}")
            traceback.print_exc()
            raise
        finally:
            try:
                await self.home()
                await self.build_api()
                await self.maintenance_api.delete_run()
            except Exception as e:
                print(f"清理资源时发生异常: {e}")

    def build_reader(self):
        reader_type = self._reader_type
        if reader_type is LaserSensor:
            try:
                laser_dict = Reader.init_laser_stj_10m0(TestNameLeveling.Z_Leveling)
                self.lasers = laser_dict
                # check laser
                if self.lasers:
                    for mount in [Mount.LEFT, Mount.RIGHT]:
                        if mount in self.lasers:
                            pass
                        else:
                            print(f"Laser on Mount {mount.value} not found (未找到测试工装！)")
                            raise ValueError(f"Laser on Mount {mount.value} not found")
                else:
                    print(f"Laser not found (未找到测试工装！)")
                    raise ValueError("Laser not found")
            except ValueError:
                raise
            except Exception as e:
                print(f"激光传感器初始化失败: {e}")
                raise


if __name__ == '__main__':
    try:
        z_leveling = Z_Leveling(robot_ip_address="192.168.6.15")
        asyncio.run(z_leveling.run())
        input("测试结束...")
    except Exception as e:
        print(f"测试失败: {e}")
        traceback.print_exc()
