import time

from tests.base_init import TestBase
from hardware_control.hardware_control import HardwareControl
from typing import Union
from ot_type import Point, Mount
from devices.sanliang import SanLiang
import asyncio
from devices.play_sound import play_alarm_2

"""
600>z>300, x>0, y>25
"""
Point_D3 = Point(465.5, 37.0, 397)  # right_front
Point_A3 = Point(465.5, 422.5, 397)  # right_rear
Point_A1 = Point(23.5, 422.5, 397)  # left_rear
Point_D1 = Point(23.5, 37.0, 397)  # left_front

FirstThreshold = 0.03
SecondThreshold = 0.15
ThisMount = Mount.LEFT


class GantryLeveling(TestBase):
    def __init__(self):
        super(GantryLeveling).__init__()
        self.sanliang = SanLiang()
        self.target_value = {}

    async def move_to_test_point(self, p: Point, mount: Mount):
        """
        move to the test position
        :param p:
        :param mount:
        :return:
        """
        await self.api.move_to(mount, p, target="mount")

    async def update_test_result(self, target_name, distance, result):
        """
        update
        :param target_name:
        :param distance:
        :param result:
        :return:
        """
        self.target_value.update({target_name: [distance, result]})

    async def checkout_result(self, target: Point, target_name: str, distance):
        """
        check result
        :param target:
        :param target_name:
        :param distance:
        :return:
        """
        if abs(distance) >= SecondThreshold:
            test_result = "Fail"
            print(f"{target_name} : {distance} - Fail")
            get_responds = input("retest this point ? (是否复测这个Deck ? y/n) : ")
            if get_responds.strip().upper() == "Y":
                await self.run_target_point(target, target_name)
            else:
                pass
        else:
            test_result = "Pass"
            print(f"{target_name} : {distance} - Pass")
        return target_name, distance, test_result

    async def re_verify_point(self, target, target_name):
        """
        verify point
        :param target:
        :param target_name:
        :return:
        """
        # check result
        await self.move_to_test_point(Point_D3, Mount.LEFT)
        self.sanliang.clear()  # 清零
        await self.move_to_test_point(target, Mount.LEFT)
        # 等待读数稳定
        self.sanliang.read_distance()
        self.delay_s(1)
        distance = self.sanliang.read_distance_n_times(5)
        target_name, distance, result = await self.checkout_result(target, target_name, distance)
        await self.update_test_result(target_name, distance, result)

    async def run_target_point(self, target: Point, target_name: str):
        """
        run test point
        :param target:
        :param target_name:
        :return:
        """
        # move to Zero Point
        await self.move_to_test_point(Point_D3, ThisMount)
        self.sanliang.clear()  # 清零
        # step 2 : move to target
        await self.move_to_test_point(target, ThisMount)
        # 等待读数稳定
        time.sleep(1)
        distance = self.sanliang.read_distance_n_times(5)  # 读取示数
        while abs(distance) >= FirstThreshold:
            play_alarm_2()
            print(f"Note...(当前高度 {distance} > {FirstThreshold})")
            distance = self.sanliang.read_distance()  # 读取示数
        input(f"Read to Go (当前 {distance} < {FirstThreshold}，继续测试...)")

    def get_test_result(self):
        """
        return test result
        :return:
        """
        point_value = []
        for key, value in self.target_value.items():
            if value[1] != "Pass":
                return "Fail", 1000
            point_value.append(value[0])
        point_value.append(0)
        sub_value = abs(max(point_value)-min(point_value))
        return "Pass", sub_value if sub_value < SecondThreshold else "Fail", sub_value

    async def run_test(self, only_check=False):
        """
        RUN
        :return:
        """
        finishing_flag = False
        addr = self.get_address().strip()
        self.initial_api(addr, hc=True)
        await self.api.home()
        # main loop
        if only_check is False:
            for target, target_name in zip([Point_A3, Point_A1, Point_D1], ["D3", "A3", "A1"]):
                await self.run_target_point(target, target_name)
        while not finishing_flag:
            for target, target_name in zip([Point_A3, Point_A1, Point_D1], ["D3", "A3", "A1"]):
                await self.re_verify_point(target, target_name)
            print("Test Values: ", self.target_value)
            print("Test Result: ", self.get_test_result())
            get_finishing = input("finishing this test ? (是否结束当前测试 y/n ?): ")
            finishing_flag = True if get_finishing.strip().upper() == "Y" else False
        self.sanliang.device.close()
        await self.api.home()


if __name__ == '__main__':
    gantry_level = GantryLeveling()
    asyncio.run(gantry_level.run_test(only_check=True))
