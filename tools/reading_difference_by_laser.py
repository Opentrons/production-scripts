import time

from ot3_testing.tests.base_init import TestBase
from ot3_testing.ot_type import Mount, Point
from typing import Union, List
from devices.amsamotion_sensor import LaserSensor
import asyncio
from utils import Utils
from devices.laser_stj_10_m0 import LaserSensor as HighAccuracySensor

from statistics import mode
import pandas as pd

_point_1 = Point(195, 215, 357)  # C2 - Right
_point_2 = Point(195, 175, 357)  # C2 - Right

Rounds = 10
KeepReading = False
UseFilter = True
Method = 1


class ReadLaser(TestBase):
    def __init__(self):
        super(ReadLaser).__init__()
        self.robot_ip = "192.168.6.54"
        self.laser_sensor = None
        self.mount = Mount.RIGHT
        self.high_laser_sensor = None

    def init_laser_sensor(self, send=False):
        """
        init 96ch device
        :return:
        """
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

    async def read_sensor_multi(self, p: Point, times=6, delay=1):
        result = []
        for i in range(times):
            print(f"Times: {i + 1}")
            await self.move_to_test_point(p)
            time.sleep(delay)
            res = self.high_laser_sensor.read_sensor_high()
            result.append(res)
        print(f"Read Result: {result}")
        if Method == 1:
            result.sort()
            result.pop(0)
            result.pop(-1)
            filtered_data = sum(result)/len(result)
            print(f"Filtered_data: {filtered_data}")
        elif Method == 2:
            series = pd.Series(result)
            # 应用移动平均滤波器，窗口大小为3
            filtered_data = series.rolling(window=3).mean()
        else:
            filtered_data = sum(result) / len(result)

        print(f"Result: {filtered_data}")
        return filtered_data

    async def run_test(self, slot_name):
        await self.build_reading()

        for i in range(Rounds):
            print(f"Round --------------------------------- {i + 1}")
            result = []
            time_str = Utils.get_time_string()
            result.append(time_str)
            for p in [_point_1, _point_2]:
                if not UseFilter:
                    await self.move_to_test_point(p)
                    for _wait in range(8):
                        print(f"wait {_wait + 1}...")
                        time.sleep(1)
                    res = self.high_laser_sensor.read_sensor_high()
                    result.append(res)
                else:
                    res = await self.read_sensor_multi(p)
                    result.append(res)
            _rear = result[1]
            _front = result[2]

            diff = (abs(_rear - _front))
            result.append(diff)
            print(result)
            file_path = '../testing_data/reading_sensor.csv'
            self.save_csv(file_path, [slot_name], result)
            if KeepReading is not True:
                await self.api.home()


if __name__ == '__main__':
    re = ReadLaser()
    asyncio.run(re.run_test("RIGHT-C2"))
