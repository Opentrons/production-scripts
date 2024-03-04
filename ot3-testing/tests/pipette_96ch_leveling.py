import time

from tests.base_init import TestBase
from ot_type import Point, Mount
from typing import Union, List
from devices.amsamotion_sensor import LaserSensor
import asyncio

SlotLocation = {"C1-Y": Point(223, 203, 318),
                "C3-Y": Point(207, 203, 318),
                "A2-Y": Point(387, 421, 318),
                "C1-X": Point(50, 91, 300),
                "C3-X": Point(382, 91, 300),
                "A2-X": Point(213, 305, 300),
                "D1-Z": Point(51, 99, 318),
                # "B2-Z": Point(213, 324, 317),
                "D3-Z": Point(377, 99, 318),
                "C2-Z": Point(214, 210, 318),
                "A2-Z": Point(218, 424, 390.5),
                }
ChannelDefinition = {"left_front": {"device_addr": 1, "channel": 4},
                     "left_rear": {"device_addr": 1, "channel": 5},
                     "right_front": {"device_addr": 1, "channel": 3},
                     "right_rear": {"device_addr": 1, "channel": 2},
                     "rear_right": {"device_addr": 1, "channel": 0},
                     "rear_left": {"device_addr": 1, "channel": 1},
                     "below_front_left": {"device_addr": 2, "channel": 1},
                     "below_front_right": {"device_addr": 2, "channel": 0},
                     "below_rear_left": {"device_addr": 2, "channel": 3},
                     "below_rear_right": {"device_addr": 2, "channel": 2},
                     }
MountDefinition = Mount.LEFT
RequestReadyFlag = False
DoCalibrate = True


class Pipette96Leveling(TestBase):
    def __init__(self):
        super(Pipette96Leveling).__init__()
        self.laser_sensor: Union[None, LaserSensor] = None

    def init_laser_sensor(self):
        """
        init 96ch device
        :return:
        """
        self.laser_sensor = LaserSensor()
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
        await self.move_to_test_point(SlotLocation[slot_name], MountDefinition)

    async def read_definition_distance(self, position: str, only_code=False):
        """
        read distance
        :param position:
        :param only_code:
        :return:
        """
        device_addr = ChannelDefinition[position]["device_addr"]
        channel = ChannelDefinition[position]["channel"]
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
        voltage = (code_value / 1600) / 2  # /V
        distance = -2 * voltage + 35  # /mm
        return distance

    async def move_step_with_test_name(self, test_name: str, direction: str, step=0.1):
        """
        move a step
        :param test_name:
        :param direction:
        :param step:
        :return:
        """
        global SlotLocation
        _point: Point = SlotLocation[test_name]
        if "Y" in test_name and "3" not in test_name:
            if direction == "plus":  # x+
                _point = _point + Point(step, 0, 0)
            else:
                _point = _point - Point(step, 0, 0)
        elif "Y" in test_name and "3" in test_name:
            _point: Point = SlotLocation[test_name]
            if direction == "plus":  # x-
                _point = _point - Point(step, 0, 0)
            else:
                _point = _point + Point(step, 0, 0)
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
        SlotLocation[test_name] = _point

    async def calibrate_to_zero(self, test_name: str, spec: float, read_definition: List[str], target_voltage=2.5):
        """
        move fixture to zero (30mm)
        :param test_name:
        :param spec:
        :param read_definition:
        :param target_voltage:
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
                distance_list.append(get_voltage(ret))
            min_voltage = min(distance_list)
            print("current min voltage is: ", min_voltage)
            if spec > (min_voltage - target_voltage) > 0:
                break
            else:
                if min_voltage > target_voltage:
                    await self.move_step_with_test_name(test_name, "plus", step=init_step)
                else:
                    await self.move_step_with_test_name(test_name, "mimus", step=init_step)
            init_step = init_step / 1.2
            if init_step <= 0.1:
                init_step = 0.1

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
        read_result = []
        print(f"Test - {test_slot_name}")
        await self.move_to_test_slot(test_slot_value)  # FIXME : maybe need to adjust to suitable position
        if with_cal:
            await self.calibrate_to_zero(test_slot_value, 0.1, read_definition)
        for item in read_definition:
            ret = await self.read_definition_distance(item)
            print(f"{test_slot_name}-{test_slot_value}-{item}: {ret}")
            read_result.append(ret)
        return {test_slot_name: read_result}

    async def run_test(self):
        """
        main loop
        :return:
        """
        test_result = {}
        addr = self.get_address().strip()
        self.initial_api(addr, hc=True)
        await self.api.home()
        self.init_laser_sensor()
        if RequestReadyFlag:
            input(">>Test y-Axis-C1 - right")
        ret = await self.run_test_slot("Test y-Axis-C1", "C1-Y", ["left_front", "left_rear"], with_cal=DoCalibrate)
        test_result.update(ret)
        if RequestReadyFlag:
            input(">>Test y-Axis-C3 - left")
        ret = await self.run_test_slot("Test y-Axis-C3", "C3-Y", ["right_front", "right_rear"], with_cal=DoCalibrate)
        test_result.update(ret)
        if RequestReadyFlag:
            input(">>Test y-Axis-A2 - left")
        ret = await self.run_test_slot("Test y-Axis-A2", "A2-Y", ["left_front", "left_rear"], with_cal=DoCalibrate)
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
            input(">>Test X-Axis-A2 - front")
        ret = await self.run_test_slot("Test X-Axis-A2", "A2-X", ["rear_left", "rear_right"], with_cal=DoCalibrate)
        test_result.update(ret)
        if RequestReadyFlag:
            input(">>Test Z-Axis-D1 - hover")
        ret = await self.run_test_slot("Test Z-Axis-D1", "D1-Z", ["below_front_left", "below_front_right",
                                                                  "below_rear_left", "below_rear_right"],
                                       with_cal=DoCalibrate)
        test_result.update(ret)
        if RequestReadyFlag:
            input(">>Test Z-Axis-D3 - hover")
        ret = await self.run_test_slot("Test Z-Axis-D3", "D3-Z", ["below_front_left", "below_front_right",
                                                                  "below_rear_left", "below_rear_right"],
                                       with_cal=DoCalibrate)
        test_result.update(ret)
        if RequestReadyFlag:
            input(">>Test Z-Axis-C2 - hover")
        ret = await self.run_test_slot("Test Z-Axis-C2", "C2-Z", ["below_front_left", "below_front_right",
                                                                  "below_rear_left", "below_rear_right"],
                                       with_cal=DoCalibrate)
        test_result.update(ret)
        if RequestReadyFlag:
            input(">>Test Z-Axis-A2 - hover")
        ret = await self.run_test_slot("Test Z-Axis-A2", "A2-Z", ["below_front_left", "below_front_right",
                                                                  "below_rear_left", "below_rear_right"],
                                       with_cal=DoCalibrate)

        test_result.update(ret)
        await self.api.home()
        # show result
        print("=" * 5 + "Test Result" + "=" * 5 + "\n")
        for key, value in test_result.items():
            print(f"{key} --> {value} (mm)")


if __name__ == '__main__':
    pipette_96_leveling = Pipette96Leveling()
    asyncio.run(pipette_96_leveling.run_test())
