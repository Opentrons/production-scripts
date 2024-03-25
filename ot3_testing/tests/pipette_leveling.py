import time

from ot3_testing.tests.base_init import TestBase
from ot3_testing.ot_type import Point, Mount
from typing import Union, List
from ot3_testing.devices.amsamotion_sensor import LaserSensor
import asyncio

from ot3_testing.tests.test_type import *

MountDefinition = Mount.LEFT
RequestReadyFlag = False
DoCalibrate = True
from ot3_testing.utils import Utils


class PipetteLeveling(TestBase):
    def __init__(self, slot_location, channel_definition, channel_offsets):
        super(PipetteLeveling).__init__()
        self.test_name = "96ch"
        self.k = -2
        self.b = 35
        self.laser_sensor: Union[None, LaserSensor] = None
        self.approaching = False
        self.slot_location = slot_location
        self.channel_definition = channel_definition
        self.channel_offsets = channel_offsets

    def init_laser_sensor(self, send=True):
        """
        init 96ch device
        :return:
        """
        self.laser_sensor = LaserSensor(send=send)
        self.laser_sensor.init_device()

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
        await self.move_to_test_point(self.slot_location[slot_name], MountDefinition)

    async def read_definition_distance(self, position: str, only_code=False):
        """
        read distance
        :param position:
        :param only_code:
        :return:
        """
        print("Reading Sensor...")
        time.sleep(1)
        device_addr = self.channel_definition[position]["device_addr"]
        channel = self.channel_definition[position]["channel"]
        code_value = self.laser_sensor.get_distance_single(device_addr, channel)
        if only_code:
            return code_value
        else:
            distance_value = await self.read_distance_mm_from_code_value(code_value)
            return distance_value

    async def read_distance_mm_from_code_value(self, code_value: int):
        """
        read real value
        :param code_value:
        :return:
        """
        if self.test_name == "96ch":
            voltage = (code_value / 1600) / 2  # /V
        else:
            voltage = code_value
        distance = self.k * voltage + self.b  # /mm
        return distance

    async def move_step_with_test_name(self, test_name: str, direction: str, step=0.1,
                                       method=CalibrateMethod.Dichotomy, gap=0):
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
<<<<<<< HEAD
            step = 0.06
=======
            step = 0.1
>>>>>>> dad3f2ae8939831d2d3c648c1b8bdb8011090228
        elif method == CalibrateMethod.Approach and not self.approaching:
            step = gap * 2
            self.approaching = True

        _point: Point = self.slot_location[test_name]
        if "Y" in test_name and "3" not in test_name:
            if direction == "plus":  # x+
                _point = _point + Point(step, 0, 0)
            else:
                _point = _point - Point(step, 0, 0)
        elif "Y" in test_name and "3" in test_name:
            _point: Point = self.slot_location[test_name]
<<<<<<< HEAD
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
=======
            if direction == "plus":  # x-
                _point = _point - Point(step, 0, 0)
            else:
                _point = _point + Point(step, 0, 0)
>>>>>>> dad3f2ae8939831d2d3c648c1b8bdb8011090228
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
        self.slot_location[test_name] = _point

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

        def get_voltage(code_value):
            voltage = (code_value / 1600) / 2
            return voltage

        init_step = 2
        while True:
            # read current
            distance_list = []
            for item in read_definition:
                ret = await self.read_definition_distance(item, only_code=True)
                if self.test_name == "96ch":
                    distance_list.append(get_voltage(ret))
                else:
                    distance_list.append(ret)
            # min_voltage = min(distance_list)
            min_voltage = distance_list[0]  # judge the first channel

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
<<<<<<< HEAD
        if RequestReadyFlag:
            input(f">>Test {test_slot_name}")
=======
>>>>>>> dad3f2ae8939831d2d3c648c1b8bdb8011090228
        read_result = []
        print(f"Test - {test_slot_name}")
        await self.move_to_test_slot(test_slot_value)  # FIXME : maybe need to adjust to suitable position
        if with_cal:
            await self.calibrate_to_zero(test_slot_value, 0.1, read_definition, method=CalibrateMethod.Approach)
        for item in read_definition:
            ret = await self.read_definition_distance(item)
            offset = await self.apply_offset_by_definition_name(item)
            print(f"apply offset: {offset} to {ret}")
            ret = ret + offset
            print(f"{test_slot_name}-{test_slot_value}-{item}: {ret}")
            read_result.append(ret)
        return {test_slot_name: read_result}

    async def run_8ch_test(self, flex_name: str):
        """
        8ch main loop
        """
<<<<<<< HEAD
        global MountDefinition
        test_result = {}
        addr = self.get_address().strip()
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
        self.init_laser_sensor(send=False)

        ret = await self.run_test_slot("Test C1-left", "Y-C1-Left", ["left_front", "left_rear"], with_cal=DoCalibrate)
        test_result.update(ret)
=======
        test_result = {}
        addr = self.get_address().strip()
        self.initial_api(addr, hc=True)
        await self.api.home()
        self.init_laser_sensor(send=False)
        if RequestReadyFlag:
            input(">>Test C1-left:")
        ret = await self.run_test_slot("Test C1-left", "Y-C1-Left", ["left_front", "left_rear"], with_cal=DoCalibrate)
        test_result.update(ret)
        # if RequestReadyFlag:
        #     input(">>Test C1-right:")
        # ret = await self.run_test_slot("Test C1-right", "Y-C1-Right", ["right_front", "right_rear"], with_cal=DoCalibrate)
        # test_result.update(ret)
        # if RequestReadyFlag:
        #     input(">>Test C3-left:")
        # ret = await self.run_test_slot("Test C3-right", "Y-C3-Right", ["right_front", "right_rear"], with_cal=DoCalibrate)
        # test_result.update(ret)
        # if RequestReadyFlag:
        #     input(">>Test A2-left:")
        # ret = await self.run_test_slot("Test A2-right", "Y-A2-Right", ["right_front", "right_rear"], with_cal=DoCalibrate)
        test_result.update(ret)
>>>>>>> dad3f2ae8939831d2d3c648c1b8bdb8011090228

        await self.move_to_test_slot("UninstallPos")  # 复位拆卸
        # show result
        csv_list = []
        csv_title = []
        import datetime

        now = datetime.datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S ")
        csv_list.append(time_str + flex_name)
        csv_title.append(time_str + flex_name)
        print("=" * 5 + "Test Result" + "=" * 5 + "\n")
        for key, value in test_result.items():
            print(f"{key} --> {value} (mm) --> offset: {max(value) - min(value)}(mm)")
            for item in value:
                csv_title.append(key)
                csv_list.append(item)
            csv_title.append(key + "-Result")
            csv_list.append(max(value) - min(value))

        # save csv
        Utils.write_to_csv("pipette_leveling.csv", csv_list)
        self.laser_sensor.close()

    async def run_96ch_test(self, flex_name: str):
        """
        main loop
        :return:
        """
        test_result = {}
        addr = self.get_address().strip()
        self.initial_api(addr, hc=True)
        await self.api.home()
        self.init_laser_sensor()
<<<<<<< HEAD

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

=======
        if RequestReadyFlag:
            input(">>Test y-Axis-A2 - left")
        ret = await self.run_test_slot("Test y-Axis-A2", "A2-Y", ["left_front", "left_rear"], with_cal=DoCalibrate)
        test_result.update(ret)
        if RequestReadyFlag:
            input(">>Test y-Axis-C1 - right")
        ret = await self.run_test_slot("Test y-Axis-C1", "C1-Y", ["left_front", "left_rear"], with_cal=DoCalibrate)
        test_result.update(ret)
        if RequestReadyFlag:
            input(">>Test y-Axis-C3 - left")
        ret = await self.run_test_slot("Test y-Axis-C3", "C3-Y", ["right_front", "right_rear"], with_cal=DoCalibrate)
        test_result.update(ret)

        if RequestReadyFlag:
            input(">>Test X-Axis-A2 - front")
        ret = await self.run_test_slot("Test X-Axis-A2", "A2-X", ["rear_left", "rear_right"], with_cal=DoCalibrate)
        test_result.update(ret)
        if RequestReadyFlag:
            input(">>Test X-Axis-C1 - front")
        ret = await self.run_test_slot("Test X-Axis-C1", "C1-X", ["rear_left", "rear_right"], with_cal=DoCalibrate)
        test_result.update(ret)
        if RequestReadyFlag:
            input(">>Test X-Axis-C3 - front")
        ret = await self.run_test_slot("Test X-Axis-C3", "C3-X", ["rear_left", "rear_right"], with_cal=DoCalibrate)
        test_result.update(ret)

        if RequestReadyFlag:
            input(">>Test Z-Axis-A2 - hover")
>>>>>>> dad3f2ae8939831d2d3c648c1b8bdb8011090228
        ret = await self.run_test_slot("Test Z-Axis-A2", "A2-Z", ["below_front_left", "below_front_right",
                                                                  "below_rear_left", "below_rear_right"],
                                       with_cal=DoCalibrate)

        test_result.update(ret)
<<<<<<< HEAD

=======
        if RequestReadyFlag:
            input(">>Test Z-Axis-D1 - hover")
>>>>>>> dad3f2ae8939831d2d3c648c1b8bdb8011090228
        ret = await self.run_test_slot("Test Z-Axis-D1", "D1-Z", ["below_front_left", "below_front_right",
                                                                  "below_rear_left", "below_rear_right"],
                                       with_cal=DoCalibrate)
        test_result.update(ret)
<<<<<<< HEAD

=======
        if RequestReadyFlag:
            input(">>Test Z-Axis-D3 - hover")
>>>>>>> dad3f2ae8939831d2d3c648c1b8bdb8011090228
        ret = await self.run_test_slot("Test Z-Axis-D3", "D3-Z", ["below_front_left", "below_front_right",
                                                                  "below_rear_left", "below_rear_right"],
                                       with_cal=DoCalibrate)
        test_result.update(ret)
<<<<<<< HEAD

=======
        if RequestReadyFlag:
            input(">>Test Z-Axis-C2 - hover")
>>>>>>> dad3f2ae8939831d2d3c648c1b8bdb8011090228
        ret = await self.run_test_slot("Test Z-Axis-C2", "C2-Z", ["below_front_left", "below_front_right",
                                                                  "below_rear_left", "below_rear_right"],
                                       with_cal=DoCalibrate)
        test_result.update(ret)

        await self.move_to_test_slot("UninstallPos")  # 复位拆卸
<<<<<<< HEAD

=======
>>>>>>> dad3f2ae8939831d2d3c648c1b8bdb8011090228
        # show result
        csv_list = []
        csv_title = []
        import datetime

        now = datetime.datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S ")
        csv_list.append(time_str + flex_name)
        csv_title.append(time_str + flex_name)
        print("=" * 5 + "Test Result" + "=" * 5 + "\n")
        for key, value in test_result.items():
            print(f"{key} --> {value} (mm) --> offset: {max(value) - min(value)}(mm)")
            for item in value:
                csv_title.append(key)
                csv_list.append(item)
            if 'Z' not in key:
                csv_title.append(key + "-Result")
                csv_list.append(max(value) - min(value))
            else:
                csv_title.extend(['', '', key + "-Result"])
                csv_list.extend(['', '', max(value) - min(value)])
            # 插入空行匹配数据格式
            if "y-Axis-C3" in key:
                csv_title.extend(['', ''])
                csv_list.extend(['', ''])
            elif "X-Axis-C3" in key:
                csv_title.extend(['', '', ''])
                csv_list.extend(['', '', ''])
            elif 'Z-Axis-C2' in key:
                csv_title.extend([''])
                csv_list.extend([''])
            else:
                pass

        # save csv
        Utils.write_to_csv("pipette_leveling.csv", csv_title)
        Utils.write_to_csv("pipette_leveling.csv", csv_list)
        self.laser_sensor.close()


if __name__ == '__main__':
    # run 96
    # pipette_leveling = PipetteLeveling(SlotLocationCH96, ChannelDefinitionCH96, ChannelOffsetsCH96)
    # asyncio.run(pipette_leveling.run_96ch_test())

    # run 8
    # pipette_leveling = PipetteLeveling(SlotLocationCH8, ChannelDefinitionCH8, ChannelOffsetsCH8)
    # pipette_leveling.test_name = "8ch"
    # pipette_leveling.k = -2
    # pipette_leveling.b = 35
    # asyncio.run(pipette_leveling.run_8ch_test())
    pass
