from ot3_testing.protocol.protocol_context import ProtocolContext
from ot3_testing.hardware_control.hardware_control import HardwareControl
from typing import Union, List
from devices.laser_stj_10_m0 import LaserSensor
import time

DEBUGGING_MODE = False


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
            input(f"Difference - {diff} don't match test spec - {test_spec} (测试结果超过预期，请复测!)")
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

    async def get_device_mount(self, laser: LaserSensor):
        """
        获取设备是左还是右
        """
        mount = laser.get_mount()
        return mount

    async def read_definition_distance(self, definition: List, channel_definition, laser: LaserSensor, mount,
                                       only_code=False,
                                       send=False, add_compensation=True, wait_time=8, read_times=5):
        """
        read distance, using one device id (please use same device_id in the positions)
        :param definition:
        :param channel_definition:
        :param laser:
        :param mount:
        :param only_code:
        :param send: 是否需要发送再接收，区分两种传感器
        :param add_compensation: 添加补偿
        :param wait_time: 等待时间
        :return:
        """
        print("Reading Sensor...")
        read_successful = True
        result = {}
        if wait_time >= 0:
            for i in range(wait_time):
                time.sleep(1)
                print(f"wait ({wait_time})/{i + 1}...")

        _channel_definition = channel_definition[mount]
        device_addr = _channel_definition[definition[0]]["device_addr"]
        sensor_readers = []  # [{1: xx, 2: xx}, {1: xx, 2: xx}]
        try:
            # 读取五次，去掉最大最小，取平均值
            for i in range(read_times):
                print(f"Reading {i + 1} times...")
                while True:
                    code_value_list = laser.read_sensor_low()
                    if code_value_list != {}:
                        break
                    print(f"read wrong value: {code_value_list}")
                sensor_readers.append(code_value_list)  # {1: xx, 2: xx}
        except:
            read_successful = False

        def sensor_readers_handler(sensor_readers):
            """
             去除最大最小取平均值
            """
            handler = {}
            output = {}
            for key in sensor_readers[0].keys():
                output[key] = []
            for ret_dict in sensor_readers:
                for key, value in ret_dict.items():
                    output[key].append(value)
            for key, value in output.items():
                _avg = round(sum(value) / len(value), 3)
                if len(value) > 1:
                    _min = min(value)
                    _max = max(value)
                    value.remove(_min)
                    value.remove(_max)
                else:
                    _min = _avg
                    _max = _avg
                if DEBUGGING_MODE:
                    print("各通道取平均如下：")
                    print(f"{key}: {value}")
                    print(f"min: {_min}, max: {_max}, avg: {_avg}")

                handler.update({key: _avg})
            return handler

        code_value_list = sensor_readers_handler(sensor_readers)

        if read_successful:

            if only_code:
                for item in definition:
                    result.update({item: code_value_list[_channel_definition[item]["channel"]]})

            else:
                for item in definition:
                    code_value = code_value_list[_channel_definition[item]["channel"]]
                    distance_value = await self.read_distance_mm_from_code_value(code_value)
                    result.update({item: distance_value})

        return result, read_successful
