from ot3_testing.tests.base_init import TestBase
from ot3_testing.ot_type import Mount, Point
from devices.amsamotion_sensor import LaserSensor
from ot3_testing.test_config.gripper_leveling_config import CalibrateMethod, Gripper_Position, GripperChannel, \
    GripperMiddlePosition
import asyncio
from typing import List
from utils import Utils
import os, datetime

ApplyCompensationFlag = True
CalibrateFlag = True

TEST_SPEC = 0.45


class GripperLeveling(TestBase):
    def __init__(self, slot_location, robot_ip=None):
        super(GripperLeveling).__init__()
        self.robot_ip = robot_ip
        self.mount = Mount.LEFT
        self.laser_sensor = None
        self.slot_location = slot_location
        self.approaching = False

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

        if "y" in test_name:
            if direction == "plus":  # x+
                _point = _point - Point(step, 0, 0)
            else:
                _point = _point + Point(step, 0, 0)
        elif "x" in test_name:
            if direction == "plus":  # x+
                _point = _point + Point(0, step, 0)
            else:
                _point = _point - Point(0, step, 0)
        elif "z" in test_name:
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

    async def run_slot(self, p: Point, test_name, definition, keep_reading=False):
        """
        run per slot, test z slot without calibrate to zero
        """
        await self.move_to_test_point(p)
        # calibrate to zero
        if CalibrateFlag and "z" not in test_name:
            await self.calibrate_to_zero(test_name, 0.1, definition, GripperChannel, method=CalibrateMethod.Approach)
        while True:
            result = await self.read_definition_distance(definition, GripperChannel, self.laser_sensor, self.mount)
            print(result)
            self.judge_test_result(list(result.values()), TEST_SPEC)
            if not keep_reading:
                return {test_name: result}

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

    async def run_gripper_test(self, flex_name, project_path=None):
        """
        run main
        """
        if self.robot_ip is None:
            addr = self.get_address().strip()
        else:
            addr = self.robot_ip
        self.initial_api(addr, hc=True)
        await self.api.home()
        self.init_laser_sensor(send=False)

        _gripper_position = Gripper_Position[self.mount]
        result_dict = {}
        csv_title = []
        csv_list = []
        now = datetime.datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S ")
        csv_list.append(time_str + flex_name)
        csv_title.append(time_str + flex_name)

        for slot_key, slot_value in _gripper_position.items():
            test_name = slot_key
            _point = slot_value["point"]
            _definition = slot_value["definition"]
            ret = await self.run_slot(_point, test_name, _definition)

            if "x" in slot_key:
                await self.api.home()
            result_dict.update(ret)
        print(result_dict)
        for key, value in result_dict.items():
            difference = abs(list(value.values())[0] - list(value.values())[1])
            for _key, _value in value.items():
                csv_title.append(key + "_" + _key)
                csv_list.append(_value)
            csv_title.append(key + "_result")
            csv_list.append(difference)

        await self.api.home()
        await self.move_to_test_point(GripperMiddlePosition)
        self.laser_sensor.close()

        # save
        if project_path is not None:
            file_path = os.path.join(project_path, 'testing_data', 'gripper_leveling.csv')
        else:
            file_path = '../../testing_data/gripper_leveling.csv'
        self.save_csv(file_path, csv_title, csv_list)


if __name__ == '__main__':
    _gripper = GripperLeveling(Gripper_Position, "192.168.6.33")
    asyncio.run(_gripper.run_gripper_test("xxx"))
