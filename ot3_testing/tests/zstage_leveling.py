import threading

from ot3_testing.tests.base_init import TestBase
from ot3_testing.ot_type import Mount, Point
from devices.amsamotion_sensor import LaserSensor
from ot3_testing.test_config.zstage_leveling_config import ZStagePoint, CalibrateMethod, ZStageChannel
from typing import List
from drivers.play_sound import play_alarm_3
from utils import Utils
import os
import asyncio
import datetime

RequestReadyFlag = False
ApplyCompensationFlag = True

TEST_SPEC = 0.3


class ZStageLeveling(TestBase):
    def __init__(self, slot_location, robot_ip=None):
        super(ZStageLeveling).__init__()
        self.robot_ip = robot_ip
        self.mount = Mount.LEFT
        self.laser_sensor = None
        self.slot_location: ZStagePoint = slot_location
        self.approaching = False
        self.judge_complete = False

    def init_laser_sensor(self, send=False):
        """
        init 96ch device
        :return:
        """
        self.laser_sensor = LaserSensor(send=send)
        self.laser_sensor.init_device()

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
        elif method == CalibrateMethod.Approach and self.approaching:
            step = 0.06
        elif method == CalibrateMethod.Approach and not self.approaching:
            step = gap * 2
            self.approaching = True

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
            else:
                _point = _point - Point(0, 0, step)

        print("move to: ", _point)
        await self.move_to_test_point(_point)
        self.slot_location[self.mount][test_name]["point"] = _point

    async def calibrate_to_zero(self, test_name: str, spec: float, read_definition: List[str], channel_definition,
                                target_voltage=2.5,
                                method=CalibrateMethod.Dichotomy):
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
        while True:
            # read voltage
            ret_dict = await self.read_definition_distance(read_definition, channel_definition, self.laser_sensor,
                                                           self.mount, only_code=True)
            # min_voltage = min(distance_list)
            _min = list(ret_dict.values())[0]  # judge the first channel
            min_voltage = await self.read_distance_mm_from_code_value(_min, get_voltage=True)
            print("current min voltage is: ", min_voltage)
            if spec >= (min_voltage - target_voltage) >= 0:
                break
            else:
                if min_voltage > target_voltage:
                    await self.move_step_with_test_name(test_name, "plus", step=init_step, method=method,
                                                        gap=(abs(min_voltage - target_voltage)))
                else:
                    await self.move_step_with_test_name(test_name, "mimus", step=init_step, method=method,
                                                        gap=(abs(min_voltage - target_voltage)))
            init_step = init_step / 1.2
            if init_step <= 0.05:
                init_step = 0.05
        self.approaching = False

    async def run_test_slot(self, point: Point, slot_name: str, read_definition: List[str],
                            with_cal=True):
        """
        test slot
        :param point:
        :param slot_name:
        :param read_definition:
        :param with_cal:
        :return:
        """
        if RequestReadyFlag:
            input(f">>Test {slot_name}")
        print(f"Test - {slot_name}")
        await self.move_to_test_point(point)
        if with_cal:
            await self.calibrate_to_zero(slot_name, 0.1, read_definition, ZStageChannel,
                                         method=CalibrateMethod.Approach)

        ret_dict = await self.read_definition_distance(read_definition, ZStageChannel, self.laser_sensor, self.mount)
        for key, value in ret_dict.items():
            print(f"{slot_name}-{key}: {value}")
        self.judge_test_result(list(ret_dict.values()), TEST_SPEC)
        return {slot_name: ret_dict}

    async def th_reading_c2(self):
        while True:
            ret_dict = await self.read_definition_distance(ZStagePoint[Mount.RIGHT]['Z-C2']["channel_definition"],
                                                           ZStageChannel, self.laser_sensor, self.mount)
            _ret_list = list(ret_dict.values())
            _difference = round(abs(max(_ret_list) - min(_ret_list)), 3)
            difference = int(-_difference * 1500 + 1500)
            if difference < 200:
                difference = 200
            if difference > 1500:
                difference = 1500
            fre = 100 if _difference > 0.03 else 1000
            print(_difference, difference)
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
        await self.calibrate_to_zero(slot_name, 0.1, _definition, ZStageChannel, method=CalibrateMethod.Approach)

        th = threading.Thread(target=self.run_th_reading_c2)
        th.start()
        input("Judging complete ? （完成校准回车）")
        self.judge_complete = True

    async def run_z_stage_test(self, flex_name, project_path=None):
        """
        main loop
        """
        self.judge_complete = False
        if self.robot_ip is None:
            addr = self.get_address().strip()
        else:
            addr = self.robot_ip
        self.initial_api(addr, hc=True)
        await self.api.home()
        self.init_laser_sensor(send=False)

        # adjust
        await self.adjust_leveling('Z-C2', Mount.RIGHT)
        input("Run Test (开始测试)？")
        # run test
        await self.api.home()

        csv_title = []
        csv_list = []

        now = datetime.datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S ")
        csv_list.append(time_str + flex_name)
        csv_title.append(time_str + flex_name)

        for mount in [Mount.RIGHT, Mount.LEFT]:
            self.mount = mount
            test_result = {}
            print(f"Start {self.mount.value} side...")
            for p_key, p_value in ZStagePoint[self.mount].items():
                _point = p_value["point"]
                _compensation = p_value["compensation"]
                _channel_definition = p_value["channel_definition"]
                result = await self.run_test_slot(_point, p_key, _channel_definition)
                test_result.update(result)
            await self.api.home()
            print(test_result)
            # save
            for key, value in test_result.items():
                result = []
                distance_list = list(value.values())
                difference = round(abs(distance_list[0] - distance_list[1]), 3)
                compensation = ZStagePoint[self.mount][key]["compensation"]
                if ApplyCompensationFlag:
                    compensation_idx = 0
                    for compensation_key, compensation_value in compensation.items():
                        print(
                            f"apply offset {compensation_key} -> {compensation_value}  to {distance_list[compensation_idx]}")
                        result.append(compensation_value + distance_list[compensation_idx])
                        compensation_idx += 1
                    difference = round(abs(result[0] - result[1]), 3)
                print(f"{key} --> {value} (mm) --> difference: {difference}(mm)")
                for item_key, item_value in value.items():
                    csv_title.append(self.mount.name + " " + key + " " + item_key)
                    csv_list.append(item_value)
                csv_title.append(key + "-Result")
                csv_list.append(difference)

        if project_path is not None:
            file_path = os.path.join(project_path, 'testing_data', 'z_stage_leveling.csv')
        else:
            file_path = '../../testing_data/z_stage_leveling.csv'
        self.save_csv(file_path, csv_title, csv_list)
        self.laser_sensor.close()

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


if __name__ == '__main__':
    obj = ZStageLeveling(ZStagePoint, robot_ip="192.168.6.33")
    asyncio.run(obj.run_z_stage_test("xxx"))
