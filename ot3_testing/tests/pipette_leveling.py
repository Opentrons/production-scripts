import os.path
import time

from ot3_testing.tests.base_init import TestBase
from ot3_testing.ot_type import Mount
from typing import Union, List
from devices.amsamotion_sensor import LaserSensor

from ot3_testing.test_config.pipette_leveling_config import *
import datetime
from utils import Utils

MountDefinition = Mount.LEFT
RequestReadyFlag = False
DoCalibrate = True
Test_8CH_SIDE = "Left_Right"
ApplyCompensationFlag = True


class PipetteLeveling(TestBase):
    def __init__(self, slot_location, channel_definition, robot_ip=None):
        super(PipetteLeveling).__init__()
        self.test_name = "96ch"
        self.k = -2
        self.b = 35
        self.laser_sensor: Union[None, LaserSensor] = None
        self.approaching = False
        self.slot_location = slot_location
        self.channel_definition = channel_definition
        self.channel_offsets = None
        self.robot_ip = robot_ip
        self.select_default = False

    def init_laser_sensor(self, send=True):
        """
        init 96ch device
        :return:
        """
        self.laser_sensor = LaserSensor(send=send)
        self.laser_sensor.init_device(select_default=self.select_default)

    async def move_to_test_point(self, p: Point, mount: Mount):
        """
        move to the test position
        :param p:
        :param mount:
        :return:
        """
        await self.api.move_to(mount, p, target="pipette", )

    async def move_to_test_slot(self, slot_name: str):
        """
        move to slot
        :param slot_name:
        :return:
        """
        await self.move_to_test_point(self.slot_location[slot_name]["Point"], MountDefinition)

    async def read_definition_distance(self, position: List[str], only_code=False) -> dict:
        """
        read distance, using one device id (please use same device_id in the positions)
        :param position:
        :param only_code:
        :return:
        """
        print("Reading Sensor...")
        result = {}
        time.sleep(1)
        device_addr = self.channel_definition[position[0]]["device_addr"]
        code_value_list = self.laser_sensor.get_distance_multi(device_addr)
        if only_code:
            for item in position:
                result.update({item: code_value_list[self.channel_definition[item]["channel"]]})

        else:
            for item in position:
                code_value = code_value_list[self.channel_definition[item]["channel"]]
                distance_value = await self.read_distance_mm_from_code_value(code_value)
                result.update({item: distance_value})

        return result

    async def read_distance_mm_from_code_value(self, code_value: int, get_voltage=False):
        """
        read real value
        :param code_value:
        :param get_voltage: return voltage
        :return:
        """
        # if self.test_name == "96ch":
        #     voltage = round(float((code_value / 1600) / 2), 3)  # /V
        # else:
        voltage = round(float(code_value), 3)
        if get_voltage:
            return voltage
        else:
            distance = self.k * voltage + self.b  # /mm
            return round(float(distance), 3)

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

        _point: Point = self.slot_location[test_name]["Point"]

        if "Y" in test_name and "3" not in test_name:
            if direction == "plus":  # x+
                _point = _point + Point(step, 0, 0)
            else:
                _point = _point - Point(step, 0, 0)
        elif "Y" in test_name and "3" in test_name:
            _point: Point = self.slot_location[test_name]["Point"]
            if self.test_name == "96ch":
                if direction == "plus":  # x-
                    _point = _point - Point(step, 0, 0)
                else:
                    _point = _point + Point(step, 0, 0)
            else:
                if direction == "plus":  # x-
                    _point = _point + Point(step, 0, 0)
                else:
                    _point = _point - Point(step, 0, 0)
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
        await self.move_to_test_point(_point, MountDefinition)
        self.slot_location[test_name]["Point"] = _point

    async def calibrate_to_zero(self, test_name: str, spec: float, read_definition: List[str], target_voltage=2.5,
                                method=CalibrateMethod.Dichotomy):
        """
        move fixture to zero (30mm)
        :param test_name:
        :param spec:
        :param read_definition:
        :param target_voltage:
        :param method:
        :return:
        """
        init_step = 2
        while True:
            # read voltage
            ret_dict = await self.read_definition_distance(read_definition, only_code=True)
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

    async def apply_offset_by_definition_name(self, definition_name: str):
        """
        apply stable offset
        """
        return self.channel_offsets[definition_name]

    async def apply_offset_by_slot_name(self, read_value, slot_value: str):
        """
        apply stable offset
        """
        compensation = self.slot_location[slot_value]["compensation"]
        print(f"apply offset: {compensation} to {read_value}")
        return compensation + read_value

    async def run_test_slot(self, test_slot_name: str, test_slot_value: str, read_definition: List[str],
                            with_cal=False):
        """
        test slot
        :param test_slot_name:
        :param test_slot_value:
        :param read_definition:
        :param with_cal:
        :return:
        """
        if RequestReadyFlag:
            input(f">>Test {test_slot_name}")
        print(f"Test - {test_slot_name}")
        await self.move_to_test_slot(test_slot_value)  # FIXME : maybe need to adjust to suitable position (FIXED)
        if with_cal:
            await self.calibrate_to_zero(test_slot_value, 0.1, read_definition, method=CalibrateMethod.Approach)

        ret_dict = await self.read_definition_distance(read_definition)
        for key, value in ret_dict.items():
            print(f"{test_slot_value}-{key}: {value}")

        return {test_slot_value: ret_dict}

    async def run_8ch_test(self, flex_name: str, project_path=None):
        """
        8ch main loop
        """
        global MountDefinition
        test_result = {}
        if self.robot_ip is None:
            addr = self.get_address().strip()
        else:
            addr = self.robot_ip
        self.initial_api(addr, hc=True)

        print("Test Right Side...")
        MountDefinition = Mount.RIGHT
        await self.api.home()
        self.init_laser_sensor(send=False)

        ret = await self.run_test_slot("Test A2-right", "Y-A2-Right", ["right_front", "right_rear"],
                                       with_cal=DoCalibrate)
        test_result.update(ret)

        ret = await self.run_test_slot("Test C1-right", "Y-C1-Right", ["right_front", "right_rear"],
                                       with_cal=DoCalibrate)
        test_result.update(ret)

        ret = await self.run_test_slot("Test C3-right", "Y-C3-Right", ["right_front", "right_rear"],
                                       with_cal=DoCalibrate)
        test_result.update(ret)

        print("Test Left Side...")
        MountDefinition = Mount.LEFT
        await self.api.home()

        ret = await self.run_test_slot("Test C1-left", "Y-C1-Left", ["left_front", "left_rear"], with_cal=DoCalibrate)
        test_result.update(ret)

        await self.move_to_test_slot("UninstallPos")  # 复位拆卸
        # show result
        csv_list = []
        csv_title = []
        now = datetime.datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S ")
        csv_list.append(time_str + flex_name)
        csv_title.append(time_str + flex_name)
        print("=" * 5 + "Test Result" + "=" * 5 + "\n")
        for key, value in test_result.items():
            distance_list = list(value.values())
            difference = distance_list[0] - distance_list[1]
            compensation = self.slot_location[key]["compensation"]
            if ApplyCompensationFlag:
                print(f"apply offset {compensation} to {difference}, difference -> {difference - compensation}")
                difference = difference - compensation
            print(f"{key} --> {value} (mm) --> difference: {round(difference, 3)}(mm)")
            for item_key, item_value in value.items():
                csv_title.append(key + " " + item_key)
                if ApplyCompensationFlag and "front" in item_key:
                    csv_list.append(item_value - compensation)
                else:
                    csv_list.append(item_value)
            csv_title.append(key + "-Result")
            csv_list.append(abs(difference))

        # save csv
        if project_path is not None:
            file_path = os.path.join(project_path, 'testing_data', 'pipette_8ch_leveling.csv')
        else:
            file_path = '../../testing_data/pipette_8ch_leveling.csv'
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

    def get_max_index(self, lst: list):
        return max(range(len(lst)), key=lst.__getitem__)

    async def run_96ch_test(self, flex_name: str, project_path=None):
        """
        main loop
        :return:
        """
        test_result = {}
        if self.robot_ip is None:
            addr = self.get_address().strip()
        else:
            addr = self.robot_ip
        self.initial_api(addr, hc=True)
        await self.api.home()
        self.init_laser_sensor(send=False)

        ret = await self.run_test_slot("Test y-Axis-A2", "A2-Y", ["left_front", "left_rear"], with_cal=DoCalibrate)
        test_result.update(ret)

        ret = await self.run_test_slot("Test y-Axis-C1", "C1-Y", ["left_front", "left_rear"], with_cal=DoCalibrate)
        test_result.update(ret)

        ret = await self.run_test_slot("Test y-Axis-C3", "C3-Y", ["right_front", "right_rear"], with_cal=DoCalibrate)
        test_result.update(ret)

        ret = await self.run_test_slot("Test X-Axis-A2", "A2-X", ["rear_left", "rear_right"], with_cal=DoCalibrate)
        test_result.update(ret)

        ret = await self.run_test_slot("Test X-Axis-C1", "C1-X", ["rear_left", "rear_right"], with_cal=DoCalibrate)
        test_result.update(ret)

        ret = await self.run_test_slot("Test X-Axis-C3", "C3-X", ["rear_left", "rear_right"], with_cal=DoCalibrate)
        test_result.update(ret)

        ret = await self.run_test_slot("Test Z-Axis-A2", "A2-Z", ["below_rear_left", "below_rear_right",
                                                                  "below_front_left", "below_front_right"],
                                       with_cal=DoCalibrate)

        test_result.update(ret)
        ret = await self.run_test_slot("Test Z-Axis-D1", "D1-Z", ["below_rear_left", "below_rear_right",
                                                                  "below_front_left", "below_front_right"],
                                       with_cal=DoCalibrate)
        test_result.update(ret)
        ret = await self.run_test_slot("Test Z-Axis-D3", "D3-Z", ["below_rear_left", "below_rear_right",
                                                                  "below_front_left", "below_front_right"],
                                       with_cal=DoCalibrate)
        test_result.update(ret)
        ret = await self.run_test_slot("Test Z-Axis-C2", "C2-Z", ["below_rear_left", "below_rear_right",
                                                                  "below_front_left", "below_front_right"],
                                       with_cal=DoCalibrate)
        test_result.update(ret)

        await self.move_to_test_slot("UninstallPos")  # 复位拆卸
        # show result
        csv_list = []
        csv_title = []

        now = datetime.datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S ")
        csv_list.append(time_str + flex_name)
        csv_title.append(time_str + flex_name)
        print("=" * 5 + "Test Result" + "=" * 5 + "\n")
        for key, value in test_result.items():
            result = []  # 本次写入结果
            distance_list = list(value.values())
            # differences
            difference = round(abs(max(distance_list) - min(distance_list)), 3)
            compensation: dict = self.slot_location[key]["compensation"]
            if ApplyCompensationFlag:
                compensation_idx = 0
                for compensation_key, compensation_value in compensation.items():
                    print(f"apply offset {compensation_key} -> {compensation_value} to {distance_list[compensation_idx]}")
                    result.append(compensation_value + distance_list[compensation_idx])
                    compensation_idx += 1
                difference = round((abs(max(result) - min(result))), 3)
            print(f"{key} --> {value} (mm) \ndifference: {difference}(mm)")
            for item_key, item_value in value.items():
                csv_title.append(key + " " + item_key)
            for values in result:
                csv_list.append(values)
            if 'Z' not in key:
                csv_title.append(key + "-Result")
                csv_list.append(difference)
            else:
                csv_title.extend(['', '', key + "-Result"])
                csv_list.extend(['', '', difference])
            # 插入空行匹配数据格式
            if "C3-Y" in key:
                csv_title.extend(['Max', 'Comment'])
                csv_list.extend(['', ''])
            elif "C3-X" in key:
                csv_title.extend(['Max', 'Comment'])
                csv_list.extend(['', ''])
            elif 'C2-Z' in key:
                csv_title.extend(['Comment'])
                csv_list.extend([''])
            else:
                pass

        # save csv
        if project_path is not None:
            file_path = os.path.join(project_path, 'testing_data', 'pipette_96ch_leveling.csv')
        else:
            file_path = '../../testing_data/pipette_96ch_leveling.csv'
        self.save_csv(file_path, csv_title, csv_list)
        self.laser_sensor.close()


if __name__ == '__main__':
    import asyncio
    pipette_leveling = PipetteLeveling(SlotLocationCH96, ChannelDefinitionCH96, )
    asyncio.run(pipette_leveling.run_96ch_test("FLXA1020240513001"))
