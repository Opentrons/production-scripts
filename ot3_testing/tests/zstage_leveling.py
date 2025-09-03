import threading
from drivers.serial_driver import SerialDriver
from ot3_testing.tests.base_init import TestBase
from ot3_testing.ot_type import Mount, Point
from devices.laser_stj_10_m0 import LaserSensor
from ot3_testing.test_config.zstage_leveling_config import ZStagePoint, CalibrateMethod, ZStageChannel
from typing import List
from drivers.play_sound import play_alarm_3
from utils import Utils
import os
import asyncio
import datetime
from ot3_testing.tests.base_init import DEBUGGING_MODE

RequestReadyFlag = False
ApplyCompensationFlag = True

TEST_SPEC = 0.3
AdjustBeforeTest = True

WAIT_TIME = 15
DEBUGGING_READING = False
TEST_NAME = "Z Stage Leveling"

class ZStageLeveling(TestBase):
    def __init__(self, slot_location, robot_ip=None):
        super(ZStageLeveling).__init__()
        self.robot_ip = robot_ip
        self.mount = Mount.LEFT
        self.laser_sensor = None
        self.slot_location: ZStagePoint = slot_location
        self.approaching = False
        self.judge_complete = False
        self.simulating = False

    def init_laser_sensor(self, send=False):
        """
        init 96ch device
        :return:
        """
        self.laser_sensor = {}
        port_list = SerialDriver.get_com_list()
        for port in port_list:
            device = port.device
            print(f"Connect Port {device}...")
            laser = LaserSensor()
            laser.init_device(select_default=device)

            result = laser.get_mount()
            if result == "left":
                self.laser_sensor.update({"left": laser})
            elif result == "right":
                self.laser_sensor.update({"right": laser})
            else:
                pass

        print(f"laser_sensor: {self.laser_sensor}")
        if len(list(self.laser_sensor.values())) == 2:
            print("Find Sensor Successful")
        else:
            raise ConnectionError("Failed to find sensors")

    async def move_to_test_point(self, p: Point):
        """
        move to the test position
        :param p:
        :return:
        """
        await self.api.move_to(self.mount, p, target="pipette", )

    async def move_step_with_test_name(self, test_name: str, direction: str, step=0.1,
                                       method=CalibrateMethod.Dichotomy, gap: float = 0):
        """
        move a step
        :param test_name:
        :param direction:
        :param step:
        :param method:
        :param gap:
        :return:
        """
        if method == CalibrateMethod.Dichotomy:
            step = step
        elif method == CalibrateMethod.Approach and not self.approaching:
            step = gap

        _point: Point = self.slot_location[self.mount][test_name]["point"]

        if "Y" in test_name and "3" not in test_name:
            if direction == "plus":  # x+
                _point = _point + Point(step, 0, 0)
            else:
                _point = _point - Point(step, 0, 0)
        elif "Y" in test_name and "3" in test_name:
            _point: Point = self.slot_location[self.mount][test_name]["point"]
            pass
        elif "X" in test_name:
            if direction == "plus":  # x+
                _point = _point - Point(0, step, 0)
            else:
                _point = _point + Point(0, step, 0)
        elif "Z" in test_name:
            if direction == "plus":  # x+
                _point = _point + Point(0, 0, step)
                print(f"Move Up: {round(step, 3)}")
            else:
                print(f"Move Down: {round(step, 3)}")
                _point = _point - Point(0, 0, step)
        if DEBUGGING_MODE:
            print("move to: ", _point)
        await self.move_to_test_point(_point)
        self.slot_location[self.mount][test_name]["point"] = _point

    async def calibrate_to_zero(self, test_name: str, spec: float, read_definition: List[str], channel_definition,
                                target_voltage=30,
                                method=CalibrateMethod.Approach):
        """
        move fixture to zero (30mm)
        :param test_name:
        :param spec:
        :param read_definition:
        :param target_voltage:
        :param channel_definition:
        :param method:
        :return:
        """
        init_step = 2
        init_gap = 0
        while True:
            # read voltage
            ret_dict, ret_success = await self.read_definition_distance(read_definition, channel_definition,
                                                                        self.laser_sensor[self.mount.value], self.mount,
                                                                        only_code=False, wait_time=8, read_times=1)
            # min_voltage = min(distance_list)
            min_distance = list(ret_dict.values())[0]  # judge the first channel
            # min_distance = await self.read_distance_mm_from_code_value(_min, get_voltage=True)
            print("Current min distance is: ", min_distance)
            if init_gap == 0:
                init_gap = (abs(min_distance - target_voltage)) / 1.1
            if abs(min_distance - target_voltage) < spec:
                break
            else:
                if min_distance > target_voltage:
                    await self.move_step_with_test_name(test_name, "mimus", step=init_step, method=method,
                                                        gap=init_gap)
                else:
                    await self.move_step_with_test_name(test_name, "plus", step=init_step, method=method,
                                                        gap=init_gap)
            init_step = init_step / 1.2
            init_gap = 0.06
            if init_step <= 0.05:
                init_step = 0.06
            if init_gap <= 0.05:
                init_gap = 0.06
        self.approaching = False

    async def run_test_slot(self, point: Point, slot_name: str, read_definition: List[str],
                            with_cal=True, project_path=None):
        """
        test slot
        :param point:
        :param slot_name:
        :param read_definition:
        :param with_cal:
        :param project_path:
        :param mount:
        :return:
        """
        if RequestReadyFlag:
            input(f">>Test {slot_name}")
        print(f"Test - {slot_name}")
        debug_front = []
        debug_rear = []
        ret_dict = {}
        for _i in range(3):
            await self.move_to_test_point(point)
            if with_cal:
                await self.calibrate_to_zero(slot_name, 0.1, read_definition, ZStageChannel,
                                             method=CalibrateMethod.Approach)
                if DEBUGGING_READING:
                    print(f"Waiting {_i}...")
                    ret_dict, ret_success = await self.read_definition_distance(read_definition, ZStageChannel,
                                                                                self.laser_sensor[self.mount.value],
                                                                                self.mount, wait_time=1)
                    debug_front.append(list(ret_dict.values())[0])
                    debug_rear.append(list(ret_dict.values())[1])
                else:
                    ret_dict, ret_success = await self.read_definition_distance(read_definition, ZStageChannel,
                                                                                self.laser_sensor[self.mount.value],
                                                                                self.mount, wait_time=WAIT_TIME)
                    read_list = list(ret_dict.values())
                    _diff = abs(max(read_list) - min(read_list))
                    if _diff <= 0.3:
                        break
                    else:
                        print(f"Test Diff = {_diff}, > 0.2, Retest to confirm !")
                        await self.api.home()
        # save debugging result
        if DEBUGGING_READING:
            if project_path is not None:
                file_path = os.path.join(project_path, 'testing_data', 'debugging_z_stage_leveling.csv')
            else:
                file_path = '../../testing_data/debugging_z_stage_leveling.csv'
            self.save_csv(file_path, [], debug_front)
            self.save_csv(file_path, [], debug_rear)
            self.save_csv(file_path, [], [])
        for key, value in ret_dict.items():
            print(f"{slot_name}-{key}: {value}")
        self.judge_test_result(list(ret_dict.values()), TEST_SPEC)
        return {slot_name: ret_dict}

    async def th_reading_c2(self):
        while True:
            ret_dict, ret_success = await self.read_definition_distance(
                ZStagePoint[Mount.RIGHT]['Z-C2']["channel_definition"],
                ZStageChannel, self.laser_sensor[self.mount.value],
                self.mount, wait_time=0, read_times=1)
            _ret_list = list(ret_dict.values())
            _difference = round(abs(max(_ret_list) - min(_ret_list)), 3)
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

    def run_th_reading_c2(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.th_reading_c2())

    async def adjust_leveling(self, slot_name: str, mount: Mount):
        """
        移动到指定slot, 调平
        """
        _definition = ZStagePoint[mount][slot_name]["channel_definition"]
        _point = ZStagePoint[mount][slot_name]["point"]
        self.mount = mount
        await self.move_to_test_point(_point)
        print(f"Test Point: {_point}")
        await self.calibrate_to_zero(slot_name, 0.1, _definition, ZStageChannel, method=CalibrateMethod.Approach)

        th = threading.Thread(target=self.run_th_reading_c2)
        th.start()
        input("")
        self.judge_complete = True
        th.join()


    async def run_z_stage_test(self, flex_name, project_path=None):
        """
        main loop
        """
        self.judge_complete = False
        if self.simulating:
            pass
        else:
            if self.robot_ip is None:
                addr = self.get_address().strip()
            else:
                addr = self.robot_ip
            self.initial_api(addr, hc=True)
            await self.api.home()
        self.init_laser_sensor(send=False)

        # adjust
        if AdjustBeforeTest:
            await self.adjust_leveling('Z-C2', Mount.RIGHT)
            input("Run Test (开始测试)？")
            # run test
        await self.api.home()

        csv_title = []
        csv_list = []
        csv_list_no_compensation = []

        now = datetime.datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S ")
        csv_list.append(flex_name)
        csv_list_no_compensation.append(time_str + flex_name + "no_compensation")
        csv_title.append(TEST_NAME)

        for mount in ["Right", "Left"]:
            self.mount = Mount.LEFT if mount == 'Left' else Mount.RIGHT
            test_result = {}
            print(f"Start {mount} side...")
            for p_key, p_value in ZStagePoint[self.mount].items():
                print(f"Test Slot: {p_key}")

            # select_defalut = input("select run slot, if run all please Enter").strip()
            select_defalut = ""
            for p_key, p_value in ZStagePoint[self.mount].items():
                if select_defalut != "" and select_defalut != p_key:
                    continue
                _point = p_value["point"]
                _compensation = p_value["compensation"]
                _channel_definition = p_value["channel_definition"]

                result = await self.run_test_slot(_point, p_key, _channel_definition, project_path=project_path)
                test_result.update(result)
            await self.api.home()
            print(test_result)
            # save
            for key, value in test_result.items():
                result = []
                distance_list = list(value.values())
                difference = round(abs(distance_list[0] - distance_list[1]), 3)
                # 无补偿添加数据
                csv_list_no_compensation.extend([round(distance_list[0], 3), round(distance_list[1], 3), difference])
                compensation = ZStagePoint[self.mount][key]["compensation"]
                if ApplyCompensationFlag:
                    compensation_idx = 0
                    for compensation_key, compensation_value in compensation.items():
                        print(
                            f"apply offset {compensation_key} -> {compensation_value}  to {distance_list[compensation_idx]}")
                        result.append(compensation_value + distance_list[compensation_idx])
                        compensation_idx += 1

                    difference = round(abs(result[0] - result[1]), 3)
                    # 添加补偿后的数据
                    csv_list.extend([round(result[0], 3), round(result[1], 3), difference])
                else:
                    csv_list = csv_list_no_compensation
                print(f"{key} --> {value} (mm) --> difference: {difference}(mm)")
                for item_key, item_value in value.items():
                    csv_title.append(self.mount.name + " " + key + " " + item_key)

                csv_title.append(key + "-Result")
            self.laser_sensor[self.mount.value].close()

        if project_path is not None:
            file_path = os.path.join(project_path, 'testing_data', 'z_stage_leveling.csv')
        else:
            file_path = '../../testing_data/z_stage_leveling.csv'
        # self.save_csv(file_path, csv_title, csv_list_no_compensation)
        self.save_csv(file_path, csv_title, csv_list)

    def save_csv(self, file_path, title, content):
        """
        save csv
        """
        is_exist = Utils.is_file_exist(file_path)
        if is_exist:
            pass
        else:
            Utils.write_to_csv(file_path, title)
        Utils.write_to_csv(file_path, content)

    async def _run(self):
        await self.run_z_stage_test('xxx')


if __name__ == '__main__':
    obj = ZStageLeveling(ZStagePoint, robot_ip="192.168.6.63")
    obj.simulating = False
    asyncio.run(obj._run())
