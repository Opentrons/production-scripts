import time,os,sys
codepath = os.path.dirname(__file__)
addpath = os.path.dirname(os.path.dirname(__file__))
addpath2 = os.path.dirname(addpath)
if addpath not in sys.path:
    sys.path.append(addpath)
if addpath2 not in sys.path:
    sys.path.append(addpath2)
from ot3_testing.tests.base_init import TestBase
from ot3_testing.ot_type import Mount, Point
from typing import Union, List
from devices.amsamotion_sensor import LaserSensor
import asyncio
from utils import Utils
from devices.laser_stj_10_m0 import LaserSensor as HighAccuracySensor
import os
from drivers.serial_driver import SerialDriver

# _point = Point(195, 195, 357)  # C2 - Right
Rounds = 30
KeepReading = False
UseHighAccuracy = False

WaitTime = 8

# _point = Point(60, 90, 356.5)  # D1 - Right

_point1 = Point(331.69, 217.3, 100.89)
_point2 = Point(331.69, 278.29, 100.89)


# _point = Point(203.68, 213.29, 453.86)
# _point = Point(207.73, 243.32, 454.26)
# _point = Point(200.73, 233.32, 433.21)
# _point = Point(202.73, 233.32, 435.16)
_point = Point(157.73, 233.32, 427.06)

class ReadLaser(TestBase):
    def __init__(self, add_height):
        super(ReadLaser).__init__()
        self.robot_ip = "192.168.8.46"
        self.laser_sensor = None
        self.mount = Mount.RIGHT
        self.high_laser_sensor = None
        self.accuracy = "low"
        self.point = _point
        # self.point = _point + Point(0, 0, add_height)

    def init_laser_sensor(self, send=False):
        """
        init 96ch device
        :return:
        """
        self.laser_sensor = HighAccuracySensor()
        self.laser_sensor.accuracy = "low"
        COM_LIST = SerialDriver.get_com_list()
        _com = COM_LIST[0].device
        print(f"Com: {_com}")
        self.laser_sensor.init_device(select_default=_com)

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
        save report
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

    async def run_test(self, robot_ip):
        self.robot_ip = robot_ip
        while True:
            answer = input("Select mount(L/R)?").upper().strip()
            if "L" in answer:
                self.mount = Mount.LEFT
                break
            elif "R" in answer:
                self.mount = Mount.RIGHT
                break
            else:
                print("请重新输入!")
        while True:
            try:
                times = int(input("Reading times (default 30 times):"))
                break
            except Exception as e:
                print(e)
        while True:
            try:
                point = input("Define reading point (example: 200,200,500):").strip()
                point_list = list(map(lambda x: float(x), point.split(',')))
                self.point = Point(*point_list)
                break
            except Exception as e:
                print(e)
        await self.build_reading()
        if KeepReading:
            await self.move_to_test_point(self.point)
        for i in range(int(times)):
            # print(f"Round --------------------------------- {i + 1}")
            await self.api.home()
            if not KeepReading:
                await self.move_to_test_point(self.point)

            result = {}
            for _wait in range(WaitTime):
                # print(f"wait {_wait + 1}...")
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
            print(f"{i+1} -> Time: {result['time']},{result[2]},{result[3]}")
        await self.api.home()

    async def move_to_and_read(self, p: Point, ch: int):
        await self.move_to_test_point(p)
        for _wait in range(10):
            # print(f"wait {_wait + 1}...")
            time.sleep(1)
        low_res = self.laser_sensor.read_sensor_low(show_distance=True)
        ch_res = low_res[ch]
        return ch_res

    async def _test2(self):
        res_list = []
        for p in [_point1, _point2]:
            res = await self.move_to_and_read(p, 5)
            res_list.append(res)
            # print(f"RES: {round(res, 3)}")
        diff = abs(max(res_list) - min(res_list))
        print(f"DIFF: {round(diff, 3)}")

    async def run_test2(self):
        await self.build_reading()
        while True:
            await self._test2()


if __name__ == '__main__':
    l = ReadLaser(add_height=0)
    asyncio.run(l.run_test("", ""))
