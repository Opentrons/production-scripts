from ot3_testing.protocol.protocol_context import ProtocolContext
from ot3_testing.hardware_control.hardware_control import HardwareControl
from typing import Union, List
from devices.amsamotion_sensor import LaserSensor
import time


class TestBase:
    def __init__(self):
        self.api: Union[None, ProtocolContext, HardwareControl] = None

    def initial_api(self, ip: str, hc=False):
        """
        init environment
        :param ip:
        :param hc:
        :return:
        """
        if hc:
            self.api = HardwareControl(ip)
        else:
            self.api = ProtocolContext(ip)

    def judge_test_result(self, result_list, test_spec):
        """
        judge the difference
        """
        diff = abs(max(result_list) - min(result_list))
        if diff > test_spec:
            raise ValueError(f"Difference - {diff} don't match test spec - {test_spec} (测试结果超过预期，请复测!)")

    def initial_server(self):
        """
        restart opentrons-robot-server
        :return:
        """
        pass

    def delay_s(self, second):
        """
        int
        :param second:
        :return:
        """
        for i in range(second):
            print(f"delay {(i + 1)}/({second})s")
            time.sleep(1)

    def get_address(self):
        """
        get input
        :return:
        """
        addr = input("Please type IP (请输入IP地址) ：")
        return addr

    def print_info(self, info: str):
        """
        print information
        :param info:
        :return:
        """
        input("=======Info======\n"
              + info)

    async def read_distance_mm_from_code_value(self, code_value: int, get_voltage=False, k=-2, b=35):
        """
        read real value
        :param code_value:
        :param get_voltage: return voltage
        :param k:
        :param b:
        :return:
        """
        # if self.test_name == "96ch":
        #     voltage = round(float((code_value / 1600) / 2), 3)  # /V
        # else:
        voltage = round(float(code_value), 3)
        if get_voltage:
            return voltage
        else:
            distance = k * voltage + b  # /mm
            return round(float(distance), 3)

    async def read_definition_distance(self, definition: List, channel_definition, laser: LaserSensor, mount,
                                       only_code=False,
                                       send=False, add_compensation=True, wait_time= 1) -> dict:
        """
        read distance, using one device id (please use same device_id in the positions)
        :param definition:
        :param channel_definition:
        :param laser:
        :param mount:
        :param only_code:
        :param send: 是否需要发送再接收，区分两种传感器
        :param add_compensation: 添加补偿
        :return:
        """
        print("Reading Sensor...")
        result = {}
        for i in range(wait_time):
            time.sleep(1)
            print(f"wait ({wait_time})/{i+1}...")
        _channel_definition = channel_definition[mount]
        device_addr = _channel_definition[definition[0]]["device_addr"]
        code_value_list = laser.get_distance_multi(device_addr)

        if only_code:
            for item in definition:
                result.update({item: code_value_list[_channel_definition[item]["channel"]]})

        else:
            for item in definition:
                code_value = code_value_list[_channel_definition[item]["channel"]]
                distance_value = await self.read_distance_mm_from_code_value(code_value)
                result.update({item: distance_value})

        return result
