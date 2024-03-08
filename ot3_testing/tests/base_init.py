from protocol.protocol_context import ProtocolContext
from hardware_control.hardware_control import HardwareControl
from typing import Union
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
            print(f"delay {(i+1)}/({second})s")
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
