from test_cli.leveling_test.model.base import LevelingBase
from test_cli.leveling_test.fixture.reader import Reader
from test_cli.leveling_test.type import SlotName, TestNameLeveling, Mount, Direction
from devices.laser_stj_10_m0 import LaserSensor
from drivers.play_sound import play_alarm_3
from test_cli.leveling_test.simulation import SimulatedLaserSensor
from test_cli.cli import ui
import asyncio
import threading
import os
import sys


class Z_Leveling(LevelingBase):
    def __init__(self, robot_ip_address: str, test_name=TestNameLeveling.Z_Leveling,
                 script_dir=os.path.dirname(os.path.abspath(__file__)), simulate: bool = False):
        super().__init__(robot_ip_address, simulate=simulate)
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
        self.require_laser()
        default_distance = self.read_default_distance()
        cli = False
        while True:
            step = default_distance - 30
            ui.calibration(default_distance, step)
            if cli:
                break
            if step > 0:
                await self.move_down(abs(step))
            else:
                await self.move_up(abs(step))
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

    async def judge_z_stage(self):
        """
        move to C2, and require rotate the screw to let the z stage leveling
        :return:
        """
        try:
            if self.simulate:
                ui.warning(ui.bilingual("Running simulated Z-stage screw adjustment", "正在运行模拟 Z 轴螺丝调节"))
                await self.init_slot(self.test_name, Mount.RIGHT, SlotName.C2, Direction.Z)
                self.laser = self.lasers[Mount.RIGHT]
                await self.move_to_slot(calibration_func_callback=self.calibration_callback)
                result = self.read_sensor(delay=1)
                _, diff = self.reader_handler(result)
                _, diff = self.apply_compensation()
                ui.info(ui.bilingual(f"Diff: {diff}; simulated screw adjustment complete", "模拟螺丝调节完成"))
                return
            await self.init_slot(self.test_name, Mount.RIGHT, SlotName.C2, Direction.Z)
            # build reader
            self.laser = self.lasers[Mount.RIGHT]
            await self.move_to_slot(calibration_func_callback=self.calibration_callback)

            def read_result():
                result = self.read_sensor(delay=0)
                _, diff = self.reader_handler(result)
                _, diff = self.apply_compensation()
                return _, diff

            sound_enabled = True

            def th_keep_reading():
                nonlocal sound_enabled
                try:
                    while True:
                        _, _difference = read_result()
                        difference = int(-_difference * 1500 + 1500)
                        if difference < 200:
                            difference = 200
                        if difference > 1500:
                            difference = 1500
                        fre = 100 if _difference > 0.03 else 1000
                        ui.info(
                            ui.bilingual(
                                f"Diff: {_difference}; adjust the screw until Diff = 0.03mm, then press Enter",
                                "调节螺丝旋钮，直到 Diff = 0.03mm 后回车继续",
                            )
                        )
                        if sys.platform != 'darwin' and sound_enabled:
                            try:
                                play_alarm_3(difference, fre)
                            except Exception as exc:
                                sound_enabled = False
                                ui.warning(
                                    ui.bilingual(
                                        f"Sound disabled: {exc}",
                                        "声音播放失败，已关闭声音提示，测试继续",
                                    )
                                )
                        if self.judge_complete:
                            break
                except Exception as e:
                    ui.exception_report(e)

            th = threading.Thread(target=th_keep_reading)
            th.start()
            input("")
            self.judge_complete = True
            th.join()
        except Exception:
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
            ui.info(ui.bilingual("Initializing serial devices", "正在初始化串口设备"))
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
            self.report.finish_test()
            self.release_laser()
        except KeyboardInterrupt:
            ui.warning(ui.bilingual("User cancelled the test", "用户中断测试"))
            raise
        except Exception as e:
            ui.exception_report(e)
            raise
        finally:
            await self.cleanup()

    def build_reader(self):
        if self.simulate:
            self.lasers = {
                Mount.LEFT: SimulatedLaserSensor("z-left"),
                Mount.RIGHT: SimulatedLaserSensor("z-right"),
            }
            return
        reader_type = self._reader_type
        if reader_type is LaserSensor:
            self.lasers = Reader.init_laser_stj_10m0(
                TestNameLeveling.Z_Leveling,
                announce=not self._reconnecting_reader,
            )
            self.require_lasers([Mount.LEFT, Mount.RIGHT])


if __name__ == '__main__':
    try:
        z_leveling = Z_Leveling(robot_ip_address="192.168.6.15")
        asyncio.run(z_leveling.run())
        input("测试结束...")
    except Exception as e:
        ui.exception_report(e, debug=True)
