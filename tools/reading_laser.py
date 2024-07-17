import time

from ot3_testing.tests.base_init import TestBase
from ot3_testing.ot_type import Mount, Point
from typing import Union, List
from devices.amsamotion_sensor import LaserSensor
import asyncio
from utils import Utils
from devices.laser_stj_10_m0 import LaserSensor as HighAccuracySensor

# _point = Point(195, 195, 357)  # C2 - Right
Rounds = 30
KeepReading = False
UseHighAccuracy = False

WaitTime = 60


_point = Point(30, 90, 357)   # D1 - Right


# _point = Point(55, 92, 356.5)

class ReadLaser(TestBase):
    def __init__(self):
        super(ReadLaser).__init__()
        self.robot_ip = "192.168.6.33"
        self.laser_sensor = None
        self.mount = Mount.RIGHT
        self.high_laser_sensor = None

    def init_laser_sensor(self, send=False):
        """
        init 96ch device
        :return:
        """
        self.laser_sensor = HighAccuracySensor()
        self.laser_sensor.accuracy = "low"
        self.laser_sensor.init_device(select_default=False)
        if UseHighAccuracy:
            self.high_laser_sensor = HighAccuracySensor()
            self.high_laser_sensor.init_device()

    async def build_reading(self):
        if self.robot_ip is None:
            addr = self.get_address().strip()
        else:
            addr = self.robot_ip
        self.initial_api(addr, hc=True)
        await self.api.home()
        self.init_laser_sensor(send=False)

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

    async def move_to_test_point(self, p: Point):
        """
        move to the test position
        :param p:
        :return:
        """
        await self.api.move_to(self.mount, p, target="pipette", )

    async def run_test(self, slot_name):
        await self.build_reading()
        if KeepReading:
            await self.move_to_test_point(_point)
        for i in range(Rounds):
            print(f"Round --------------------------------- {i+1}")
            if not KeepReading:
                await self.move_to_test_point(_point)

            result = {}
            for _wait in range(WaitTime):
                print(f"wait {_wait + 1}...")
                time.sleep(1)
            low_res = self.laser_sensor.read_sensor_low()
            if UseHighAccuracy:
                high_res = self.high_laser_sensor.read_sensor_high()

            time_str = Utils.get_time_string()
            result.update({"time": time_str})
            for key, value in low_res.items():
                distance_value = await self.read_distance_mm_from_code_value(value)
                result.update({key: distance_value})
            if UseHighAccuracy:
                result.update({"high": high_res})
            print(result)

            file_path = '../testing_data/reading_sensor.csv'
            self.save_csv(file_path, [slot_name], list(result.values()))
            if KeepReading is not True:
                await self.api.home()


if __name__ == '__main__':
    re = ReadLaser()
    asyncio.run(re.run_test("RIGHT-D1"))
