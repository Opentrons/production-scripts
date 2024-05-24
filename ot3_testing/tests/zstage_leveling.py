from ot3_testing.tests.base_init import TestBase
from ot3_testing.ot_type import Mount, Point
from devices.amsamotion_sensor import LaserSensor
from ot3_testing.test_config.zstage_leveling_config import ZStagePoint, CalibrateMethod, ZStageChannel
from typing import List
from drivers.play_sound import play_alarm_3

RequestReadyFlag = False


class ZStageLeveling(TestBase):
    def __init__(self, slot_location, robot_ip=None):
        super(ZStageLeveling).__init__()
        self.robot_ip = robot_ip
        self.mount = Mount.LEFT
        self.laser_sensor = None
        self.slot_location: ZStagePoint = slot_location
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
            await self.calibrate_to_zero(slot_name, 0.1, read_definition, ZStageChannel[self.mount],
                                         method=CalibrateMethod.Approach)

        ret_dict = await self.read_definition_distance(read_definition)
        for key, value in ret_dict.items():
            print(f"{slot_name}-{key}: {value}")

        return {slot_name: ret_dict}

    async def adjust_leveling(self, slot_name: str, mount: Mount):
        """
        移动到指定slot, 调平
        """
        _definition = ZStagePoint[mount][slot_name]["channel_definition"]
        _point = ZStagePoint[mount][slot_name]["point"]
        self.mount = mount
        await self.move_to_test_point(_point)
        await self.calibrate_to_zero(slot_name, 0.1, _definition, ZStageChannel, method=CalibrateMethod.Approach)

        while True:
            play_alarm_3(500, 500)

        # async def thread_play_beep():
        #     while True:
        #         result = await self.read_definition_distance(_definition, ZStageChannel, self.laser_sensor)
        #         _rear = result['below_rear']
        #         _front = result['below_front']
        #         print(f"Rear: {_rear}")
        #         print(f"_front: {_front}")
        #         difference = _rear - _front
        #         if abs(difference) > 0.03:
        #             play_alarm_3(1000, 500)
        #         else:
        #             play_alarm_3(500, 500)
        #
        # while True:
        #     result: dict = await self.read_definition_distance(_definition, ZStageChannel, self.laser_sensor, self.mount)

    async def run_z_stage_test(self):
        """
        main loop
        """
        test_result = {}
        if self.robot_ip is None:
            addr = self.get_address().strip()
        else:
            addr = self.robot_ip
        self.initial_api(addr, hc=True)
        await self.api.home()
        self.init_laser_sensor(send=False)

        # adjust
        await self.adjust_leveling('Z-C2', Mount.RIGHT)

        # run test
        for mount in [Mount.RIGHT, Mount.LEFT]:
            self.mount = mount
            print(f"Start {self.mount.value} side...")
            for p_key, p_value in ZStagePoint[self.mount].items():
                _point = p_value["point"]
                _compensation = p_value["compensation"]
                _channel_definition = p_value["channel_definition"]
                await self.run_test_slot(_point, p_key, _channel_definition)
        # save


if __name__ == '__main__':
    import asyncio

    obj = ZStageLeveling(ZStagePoint, robot_ip="192.168.6.33")
    asyncio.run(obj.run_z_stage_test())
