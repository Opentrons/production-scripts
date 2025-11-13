import os.path
import time

from ot3_testing.tests.base_init import TestBase
from ot3_testing.ot_type import Mount
from typing import Union, List, Dict
from devices.laser_stj_10_m0 import LaserSensor
from drivers.serial_driver import SerialDriver
from ot3_testing.test_config.pipette_leveling_config import *
import datetime
from utils import Utils
from ot3_testing.tests.base_init import DEBUGGING_MODE

MountDefinition = Mount.LEFT
RequestReadyFlag = False
DoCalibrate = True
ApplyCompensationFlag = True

TEST_SPEC = 0.45
WAIT_TIME = 15


class PipetteLeveling(TestBase):
    def __init__(self, slot_location, channel_definition, robot_ip=None):
        super(PipetteLeveling).__init__()
        self.test_name = "96ch"
        self.k = -2
        self.b = 35
        self.laser_sensor: Union[None, LaserSensor, Dict] = {}
        self.approaching = False
        self.slot_location = slot_location
        self.channel_definition = channel_definition
        self.channel_offsets = None
        self.robot_ip = robot_ip
        self.select_default = False
        self.mount = Mount.LEFT

    def init_laser_sensor(self, send=True):
        """
        init 96ch device
        :return:
        """
        # 判断port是否存在
        while True:
            ports = SerialDriver.get_com_list()
            ports_length = len(ports)
            if self.test_name == "96ch":
                if ports_length >= 1:
                    break
            elif self.test_name == "8ch":
                if ports_length >= 2:
                    break
            print("请插入测试设备...")
            time.sleep(1)

        if self.test_name == '96ch':
            default_com = SerialDriver.get_com_list()[0].device
            laser = LaserSensor()
            laser.accuracy = "low"

            laser.init_device(select_default=default_com)
            self.laser_sensor.update({"left": laser})
        else:
            self.laser_sensor = {}
            port_list = SerialDriver.get_com_list()
            for port in port_list:
                device = port.device
                print(f"Connect Port {device}...")
                laser = LaserSensor()
                laser.init_device(select_default=device)
                try:
                    result = laser.get_mount()
                    if result == "left":
                        self.laser_sensor.update({"left": laser})
                    elif result == "right":
                        self.laser_sensor.update({"right": laser})
                    else:
                        pass
                except Exception as e:
                    print(e)
            if len(list(self.laser_sensor.values())) == 2:
                print("Find Sensor Successful")
            else:
                raise ConnectionError("Failed to find sensors")

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

    async def _read_definition_distance(self, position: List[str], only_code=False) -> dict:
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
                distance_value = await self._read_distance_mm_from_code_value(code_value)
                result.update({item: distance_value})

        return result

    async def _read_distance_mm_from_code_value(self, code_value: int, get_voltage=False):
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
            step = gap / 0.9
            self.approaching = True
        print(f"Move Step: {round(step, 3)}")
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
        if DEBUGGING_MODE:
            print("move to: ", _point)
        await self.move_to_test_point(_point, MountDefinition)
        self.slot_location[test_name]["Point"] = _point

    async def calibrate_to_zero(self, test_name: str, spec: float, read_definition: List[str], target_distance=30,
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
            while True:
                # read voltage
                ret_dict, ret_success = await self.read_definition_distance(read_definition, self.channel_definition,
                                                               self.laser_sensor[self.mount.value], self.mount,
                                                               only_code=True, read_times=1)
                if ret_success:
                    break
                else:
                    print("正在重新连接设备...")
                    self.init_laser_sensor(send=False)
            # min_voltage = min(distance_list)
            _min = list(ret_dict.values())[0]  # judge the first channel
            min_distance = await self._read_distance_mm_from_code_value(_min, get_voltage=False)
            print("current min distance is: ", min_distance)
            if abs(min_distance - target_distance) < spec:
                break
            else:
                if min_distance > target_distance:
                    await self.move_step_with_test_name(test_name, "minus", step=init_step, method=method,
                                                        gap=(abs(min_distance - target_distance)))
                else:
                    await self.move_step_with_test_name(test_name, "plus", step=init_step, method=method,
                                                        gap=(abs(min_distance - target_distance)))
            init_step = init_step / 1.2
            if init_step <= 0.05:
                init_step = 0.06
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
                            with_cal=False, keep_reading=False):
        """
        test slot
        :param test_slot_name:
        :param test_slot_value:
        :param read_definition:
        :param with_cal:
        :param keep_reading:
        :return:
        """
        if RequestReadyFlag:
            input(f">>Test {test_slot_name}")
        print(f"Test - {test_slot_name}")
        await self.move_to_test_slot(test_slot_value)  # FIXME : maybe need to adjust to suitable position (FIXED)
        if with_cal:
            await self.calibrate_to_zero(test_slot_value, 0.1, read_definition, method=CalibrateMethod.Approach)
        ret_dict = {}
        while True:
            while True:

                ret_dict, ret_success = await self.read_definition_distance(read_definition, self.channel_definition,
                                                                   self.laser_sensor[self.mount.value], self.mount,
                                                                   wait_time=WAIT_TIME)

                if ret_success:
                    break
                else:
                    print("正在重新连接设备...")
                    self.init_laser_sensor(send=False)

            ret_with_compensation = {}
            _value_list = list(ret_dict.values())
            """
            Show messages
            """
            if DEBUGGING_MODE:
                print("==== 初始值 ====")
                for key, value in ret_dict.items():
                    print(f"{test_slot_value}-{key}: {value}")
                print(f"Difference: {round(max(_value_list) - min(_value_list), 3)}")
            if ApplyCompensationFlag:
                compensation: dict = self.slot_location[test_slot_value]["compensation"]
                for key, value in ret_dict.items():
                    add_compensation_result = value + compensation[key]
                    print(f"{key}: Apply {compensation[key]} to {value} -> {add_compensation_result}")
                    ret_with_compensation.update({key: add_compensation_result})
            _value_list_with_compensation = list(ret_with_compensation.values())
            for key, value in ret_with_compensation.items():
                print(f"{test_slot_value}-{key}: {value}")
            print(f"Difference: {round(max(_value_list_with_compensation) - min(_value_list_with_compensation), 3)}")

            self.judge_test_result(_value_list_with_compensation, TEST_SPEC)
            if keep_reading is False:
                return {test_slot_value: ret_dict}, {test_slot_value: ret_with_compensation}

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
        self.mount = MountDefinition
        self.init_laser_sensor(send=False)

        ret, _ret = await self.run_test_slot("Test A2-right", "Y-A2-Right", ["right_front", "right_rear"],
                                             with_cal=DoCalibrate)
        test_result.update(_ret)

        ret, _ret = await self.run_test_slot("Test C1-right", "Y-C1-Right", ["right_front", "right_rear"],
                                             with_cal=DoCalibrate)
        test_result.update(_ret)

        ret, _ret = await self.run_test_slot("Test C3-right", "Y-C3-Right", ["right_front", "right_rear"],
                                             with_cal=DoCalibrate)
        test_result.update(_ret)

        print("Test Left Side...")
        MountDefinition = Mount.LEFT
        await self.api.home()
        self.mount = MountDefinition
        ret, _ret = await self.run_test_slot("Test C1-left", "Y-C1-Left", ["left_front", "left_rear"],
                                             with_cal=DoCalibrate)
        test_result.update(_ret)

        # await self.move_to_test_slot("UninstallPos")  # 复位拆卸
        await self.api.home()  # 复位拆卸
        # show result
        csv_list = []
        csv_list_no_compensation = []
        csv_title = []
        now = datetime.datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S ")

        csv_list.append(flex_name)
        csv_list_no_compensation.append(flex_name + "no_compensation")
        csv_title.append("Pipette 8CH Leveling")
        print("=" * 5 + "Test Result" + "=" * 5 + "\n")
        for key, value in test_result.items():
            distance_list = list(value.values())
            difference = round(abs(distance_list[0] - distance_list[1]), 3)
            csv_list.extend([round(distance_list[0], 3), round(distance_list[1], 3), difference])

            #compensation = self.slot_location[key]["compensation"]
            # if ApplyCompensationFlag:
            #     compensation_idx = 0
            #     for compensation_key, compensation_value in compensation.items():
            #         print(
            #             f"apply offset {compensation_key} -> {compensation_value}  to {distance_list[compensation_idx]}")
            #         result.append(compensation_value + distance_list[compensation_idx])
            #         compensation_idx += 1
            #     difference = round(abs(result[0] - result[1]), 3)
            #     csv_list.extend([round(result[0], 3), round(result[1], 3), difference])
            # else:
            #     csv_list = csv_list_no_compensation
            print(f"{key} --> {value} (mm) --> difference: {difference}(mm)")
            for item_key, item_value in value.items():
                csv_title.append(key + " " + item_key)
            csv_title.append(key + "-Result")
        self.laser_sensor[self.mount.value].close()

        # save report
        if project_path is not None:
            file_path = os.path.join(project_path, 'testing_data', 'pipette_8ch_leveling.report')
        else:
            file_path = '../../testing_data/pipette_8ch_leveling.report'
        # self.save_csv(file_path, csv_title, csv_list_no_compensation)
        self.save_csv(file_path, csv_title, csv_list)

    def save_csv(self, file_path, title, content):
        """
        save report
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
        test_result_with_compensation = {}
        if self.robot_ip is None:
            addr = self.get_address().strip()
        else:
            addr = self.robot_ip
        self.initial_api(addr, hc=True)
        await self.api.home()
        self.mount = Mount.LEFT
        self.init_laser_sensor(send=False)

        test_config = [
            {"test_name": "Test y-Axis-A2", "test_location": "A2-Y", "test_define": ["left_front", "left_rear"]},
            {"test_name": "Test y-Axis-C1", "test_location": "C1-Y", "test_define": ["left_front", "left_rear"]},
            {"test_name": "Test y-Axis-C3", "test_location": "C3-Y", "test_define": ["right_front", "right_rear"]},
            {"test_name": "Test X-Axis-A2", "test_location": "A2-X", "test_define": ["rear_left", "rear_right"]},
            {"test_name": "Test X-Axis-C1", "test_location": "C1-X", "test_define": ["rear_left", "rear_right"]},
            {"test_name": "Test X-Axis-C3", "test_location": "C3-X", "test_define": ["rear_left", "rear_right"]},
            {"test_name": "Test Z-Axis-A2", "test_location": "A2-Z",
             "test_define": ["below_rear_left", "below_rear_right",
                             "below_front_left", "below_front_right"]},
            {"test_name": "Test Z-Axis-D1", "test_location": "D1-Z",
             "test_define": ["below_rear_left", "below_rear_right",
                             "below_front_left", "below_front_right"]},
            {"test_name": "Test Z-Axis-D3", "test_location": "D3-Z",
             "test_define": ["below_rear_left", "below_rear_right",
                             "below_front_left", "below_front_right"]},
            {"test_name": "Test Z-Axis-C2", "test_location": "C2-Z",
             "test_define": ["below_rear_left", "below_rear_right",
                             "below_front_left", "below_front_right"]},

        ]
        for target in test_config:
            test_location = target["test_location"]
            print(f"run slot: {test_location}")
        if DEBUGGING_MODE:
            select_default = input("select slot of running, if you want to run all, please Enter: ").strip()
        else:
            select_default = ""

        for _test_config in test_config:
            test_name = _test_config['test_name']
            test_location = _test_config['test_location']
            test_define = _test_config['test_define']
            if select_default != "" and select_default != test_location:
                continue
            ret, _ret = await self.run_test_slot(test_name, test_location, test_define, with_cal=DoCalibrate)
            test_result.update(ret)
            test_result_with_compensation.update(_ret)

        await self.move_to_test_slot("UninstallPos")  # 复位拆卸

        # show result
        for index, result in enumerate([test_result, test_result_with_compensation]):
            # with_compensation = "" if index == 0 else "with compensation"
            if index == 0:
                continue
            with_compensation = 'with_compensation'
            csv_list = []
            csv_title = []
            now = datetime.datetime.now()
            time_str = now.strftime("%Y-%m-%d %H:%M:%S ")
            # if not DEBUGGING_MODE and with_compensation == "":
            #     continue
            csv_title.append("Pipette 96CH Leveling")
            csv_list.append(flex_name)
            print(f"==== Test Result - {with_compensation} ====")
            for slot, definition_data in result.items():
                for pos, value in definition_data.items():
                    csv_title.append(slot + " " + pos)
                    csv_list.append(value)
                diff = list(definition_data.values())
                diff = round(abs(max(diff) - min(diff)), 3)
                csv_title.append("Result")
                csv_list.append(diff)

                print(f"Test Slot: {slot}, Test Result: {diff}")

            # save report
            if project_path is not None:
                file_path = os.path.join(project_path, 'testing_data', 'pipette_96ch_leveling.report')
            else:
                file_path = '../../testing_data/pipette_96ch_leveling.report'
            self.save_csv(file_path, csv_title, csv_list)
        self.laser_sensor[self.mount.value].close()

    async def test_96ch_slot(self, slot_name: str):
        """
        test special slot
        """
        if self.robot_ip is None:
            addr = self.get_address().strip()
        else:
            addr = self.robot_ip
        self.initial_api(addr, hc=True)
        await self.api.home()
        self.init_laser_sensor(send=False)

        await self.run_test_slot(slot_name, slot_name, SlotLocationCH96[slot_name]["definition"],
                                 with_cal=DoCalibrate, keep_reading=True)


if __name__ == '__main__':
    import asyncio

    pipette_leveling = PipetteLeveling(SlotLocationCH96, ChannelDefinitionCH96, )
    pipette_leveling.test_name = '96ch'
    asyncio.run(pipette_leveling.run_96ch_test("0527001"))

    # pipette_leveling = PipetteLeveling(SlotLocationCH8, ChannelDefinitionCH8, )
    # pipette_leveling.test_name = '8ch'
    # asyncio.run(pipette_leveling.run_8ch_test("0527001"))

    # pipette_leveling = PipetteLeveling(SlotLocationCH96, ChannelDefinitionCH96, robot_ip="192.168.6.85")
    # pipette_leveling.test_name = '96ch'
    # asyncio.run(pipette_leveling.test_96ch_slot("C3-X"))
