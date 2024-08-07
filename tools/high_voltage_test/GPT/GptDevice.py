#! /usr/bin/env python

"""
Gpt  Driver
The driver allows a user to retrieve raw data
from the scale by using a USB connection.
Specify the port to establish Connection

Author: samuel@opentrons.com

"""
from serial import Serial
from serial.tools.list_ports import comports
from serial import SerialException
from enum import Enum

from .code import Code,SimulateResponse
from .cmd_args import *

import serial


def scan_for_port(name: str) -> str:
    instruments = {
        'Gpt': 'VID:PID=10C4:EA60',
    }
    port = None
    ports = comports()
    if name == '' or name == None:
        raise Exception("No instrument was named!")
    port_list = []
    for com_port, desc, hwid in sorted(ports):
        print("{}: {} [{}]".format(com_port, desc, hwid))
        port_list.append((com_port, desc, hwid))
    for vid in range(len(port_list)):
        if instruments[name] in port_list[vid][2]:
            port = port_list[vid][0]
            print("COM PORT: ", port_list[vid][0])
    return port


class GptDeviceError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return 'Bad Response: ' + repr(self.value)


class GptDevice:
    def __init__(self, simulate=True, Baudrate=115200):
        self._baudrate = Baudrate
        self.device = None
        self._simulate_device = SimulateResponse()
        self._port = scan_for_port('Gpt')
        if self._port is None:
            self.simulate = True
        else:
            self.simulate = False

    def connect(self):
        if self.simulate:
            print("Virtual Device Port Connected")
        else:
            print("Connection established: ", self._port)
            self._connect_to_port()

    def _connect_to_port(self):
        try:
            self.device = Serial(port=self._port,
                                 baudrate=self._baudrate,
                                 parity=serial.PARITY_NONE,
                                 stopbits=serial.STOPBITS_ONE,
                                 bytesize=serial.EIGHTBITS,
                                 timeout=2)
            self.clear_buffer()
        except SerialException:
            error_msg = '\nUnable to access Serial port to Device: \n'
            error_msg += '1. Check that the Usb cable is plugged into the computer. \n'
            error_msg += '2. CHeck if the assigned port is correct. \n'
            raise SerialException(error_msg)

    def _send_command(self, cmd: str):
        if self.simulate:
            pass
        else:
            self.device.write('{}\n'.format(cmd).encode('utf-8'))
        # print("\nSend command <{}> to Device".format(cmd))

    def _get_response(self) -> str:
        response = self.device.readline().strip()
        return response.decode('utf-8')

    def clear_buffer(self):
        while True:
            self._send_command(Code.system_error.value + Query.NO_SPACE.value)
            if self.simulate is False:
                res = self._get_response()
                if 'No Error' in res:
                    break
            else:
                self._simulate_device.system_error = '0, No Error'
                break
        # print("\nBuffer is empty")

    def query_command(self,cmd:Code) ->str:
        if self.simulate is False:
            def _query_command(cmd: Code, suffix: Enum):
                self.clear_buffer()
                self._send_command(cmd.value + suffix.value)
                self._send_command(Code.system_error.value + Query.NO_SPACE.value)
                res = self._get_response()
                res = res + "*****" + self._get_response()
                res = res.split("*****")
                return res
            res = _query_command(cmd,Query.NO_SPACE)
            if "Error" in res[0]:
                res = _query_command(cmd, Query.SPACE)
                if "Error" in res[0]:
                    return_str = "State: <{}>\t|{}\t |Response: <{}>".format(res[0],cmd.value,"Empty")
                else:
                    return_str = "State: <{}>\t|{}\t |Response: <{}>".format(res[1],cmd.value, res[0])
            else:
                return_str = "State: <{}>\t|{}\t |Response: <{}>".format(res[1],cmd.value, res[0])
            return return_str
        else:
            self.clear_buffer()
            return_str = "State: <{}>\t|{}\t |Response: <{}>".format(
                self._simulate_device.__getattribute__(Code.system_error.name),
                cmd.value,
                self._simulate_device.__getattribute__(cmd.name)
            )
            return return_str

    def _send_command_with_enum(self, cmd: Code, setup: Enum) -> str:
        self.clear_buffer()
        if self.simulate is False:
            self._send_command(cmd.value +" "+  setup.value)
            self._send_command(Code.system_error.value + Query.NO_SPACE.value)
            res = self._get_response()
            return res
        else:
            self._simulate_device.__setattr__(cmd.name, setup.value)
            return '0,No Error'

    def _send_command_with_vaule(self, cmd: Code, setup: str) -> str:
        self.clear_buffer()
        if self.simulate is False:
            self._send_command(cmd.value +" "+  setup)
            self._send_command(Code.system_error.value +Query.NO_SPACE.value)
            res = self._get_response()
            return res
        else:
            self._simulate_device.__setattr__(cmd.name, setup)
            return '0,No Error'

    def send_setup_to_device(self,cmd:Code, setup) ->str:
        if isinstance(setup,str):
            return self._send_command_with_vaule(cmd,setup)
        else:
            return self._send_command_with_enum(cmd,setup)

    def set_buzzer_time(self,cmd:Code,value:float) ->str:
        if cmd.name not in ['system_buzzer_ptime','system_buzzer_ftime']:
            print("You can only choice ['system_buzzer_ptime',\
                        'system_buzzer_ftime'] in function set_buzz_time")
            raise TypeError
        if value <0.2 or value>999.9:
            # print("Value out of range")
            raise TypeError("Value out of range")
        value = round(value,1)
        res = self._send_command_with_vaule(cmd, " "+str(value) + " S")
        return res

    def set_manu_rise_time(self,value:float) ->str:
        if value <0.1 or value>999.9:
            # print("Value out of range")
            raise TypeError("Value out of range")
        value = round(value,1)
        res = self._send_command_with_vaule(Code.manu_rtim, " "+str(value) + " S")
        return res

    def _send_command_with_no_response(self,cmd:Code,value:str):
        self._send_command(cmd.value + " " + value)
        self._send_command(Code.system_error.value + Query.NO_SPACE.value)

    def change_mode(self,mode:Enum):
        cmd = Code.main_func
        self.clear_buffer()
        if self.simulate is False:
            self._send_command_with_no_response(cmd,mode.value)
            res = self._get_response()
            return res
        else:
            self._simulate_device.__setattr__(cmd.name, mode.value+ " MODE")
            return '0,No Error'

    def set_manu_test_serial(self,serial:int):
        if serial <0 or serial >100:
            # print("the number you set is out off range")
            raise TypeError("the number you set is out off range")
        return self.send_setup_to_device(Code.manu_step,str(serial))

    def set_manu_test_name(self,name:str):
        if len(name) > 10:
            # print("the length of your name is longer than we expect")
            raise TypeError("the length of your name is longer than we expect")
        return self.send_setup_to_device(Code.manu_name,name)

    def set_manu_mode(self,mode:ManuMode):
        return self.send_setup_to_device(Code.manu_edit_mode, mode.value)

    def set_manu_acw_vol(self,value:float):
        if value <0.05 or value >5:
            # print("the number you set is out off range")
            raise TypeError("the number you set is out off range")
        value = round(value, 3)
        return self.send_setup_to_device(Code.manu_acw_vol, " "+str(value))

    def set_manu_acw_high_current(self,value:float):
        if value <0.001 or value >110:
            # print("the number you set is out off range")
            raise TypeError("the number you set is out off range")
        value = round(value, 3)
        return self.send_setup_to_device(Code.manu_acw_cur_hi_set, " "+str(value))

    def set_manu_acw_low_current(self,value:float):
        if value <0.001 or value >110:
            # print("the number you set is out off range")
            raise TypeError("the number you set is out off range")
        value = round(value, 3)
        return self.send_setup_to_device(Code.manu_acw_cur_lo_set, " "+str(value))

    def set_manu_acw_test_time(self,value:float):
        if value <0.5 or value >999.9:
            # print("the number you set is out off range")
            raise TypeError("the number you set is out off range")
        value = round(value, 1)
        return self.send_setup_to_device(Code.manu_acw_ttime, " "+str(value))

    def set_manu_acw_frequency(self,value:int):
        if value  not in [50, 60]:
            # print("the number you set is out off range")
            raise TypeError("the number should be 50 or 60")
        return self.send_setup_to_device(Code.manu_acw_freq, " "+str(value))

    def set_manu_acw_ref(self,value:float):
        if value <0 or value >109.9:
            # print("the number you set is out off range")
            raise TypeError("the number you set is out off range")
        value = round(value, 3)
        return self.send_setup_to_device(Code.manu_acw_ref, " "+str(value))

    def set_manu_acw_arc_current(self,value:float):
        if value <2 or value >200:
            # print("the number you set is out off range")
            raise TypeError("the number you set is out off range")
        value = round(value, 3)
        return self.send_setup_to_device(Code.manu_acw_arc_cur, " "+str(value))

    def set_manu_dcw_vol(self,value:float):
        if value <0.05 or value >6:
            # print("the number you set is out off range")
            raise TypeError("the number you set is out off range")
        value = round(value, 3)
        return self.send_setup_to_device(Code.manu_dcw_vol, " "+str(value))

    def set_manu_dcw_high_current(self,value:float):
        if value <0.001 or value >21:
            # print("the number you set is out off range")
            raise TypeError("the number you set is out off range")
        value = round(value, 3)
        return self.send_setup_to_device(Code.manu_dcw_cur_hi_set, " "+str(value))

    def set_manu_dcw_low_current(self,value:float):
        if value <0.001 or value >21:
            # print("the number you set is out off range")
            raise TypeError("the number you set is out off range")
        value = round(value, 3)
        return self.send_setup_to_device(Code.manu_dcw_cur_lo_set, " "+str(value))

    def set_manu_dcw_test_time(self,value:float):
        if value <0.5 or value >999.9:
            # print("the number you set is out off range")
            raise TypeError("the number you set is out off range")
        value = round(value, 1)
        return self.send_setup_to_device(Code.manu_dcw_ttime, " "+str(value))

    def set_manu_dcw_ref(self,value:float):
        if value <0 or value >20.9:
            # print("the number you set is out off range")
            raise TypeError("the number you set is out off range")
        value = round(value, 3)
        return self.send_setup_to_device(Code.manu_dcw_ref, " "+str(value))

    def set_manu_dcw_arc_current(self,value:float):
        if value <2 or value >40:
            # print("the number you set is out off range")
            raise TypeError("the number you set is out off range")
        value = round(value, 3)
        return self.send_setup_to_device(Code.manu_dcw_arc_cur, " "+str(value))


















    # def setup_command(self,cmd:Code,state:Enum=Query.NO_SPACE) ->str:
    #     self.clear_buffer()
    #     self._send_command(cmd.value + state.value)
    #
    #     return res
    #
    # def get_right_response(self) ->tuple:
    #     self._send_command(Code.system_error.value)
    #     res = self._get_response()
    #     res = res + self._get_response()
    #     print(res)
    #     if 'No Error' in res:
    #         return (True,res)
    #     else:
    #         return (False,res)
    #
    # def send_command(self,cmd:Code,argu:Enum=Query.NO_SPACE) ->str:
    #     self._send_command(cmd.value + argu.value)
    #     if self.simulate is False:
    #         res = self.get_right_response()
    #         print(res)
    #         if res[0] is True and '?' in argu.value:
    #             return res[1]
    #         elif res[0] is True and '?' not in argu.value:
    #             return argu.value
    #         else:
    #             raise GptDeviceError(res[1])
    #     else:
    #         response = self._simulate_device.__getattribute__(cmd.name)
    #         if argu.value == '?':
    #             return response
    #         else:
    #             self._simulate_device.__setattr__(cmd.name,argu.value)
    #             return argu.value
    #
    # def send_value_with_command(self,cmd:Code,value:float) ->str:
    #     self._send_command(cmd.value + str(value))
    #     # if it is real, return nothing
    #     if self.simulate is False:
    #         return value
    #     # if simulate,
    #     else:
    #         response = self._simulate_device.__getattribute__(cmd.name)
    #         self._simulate_device.__setattr__(cmd.name, value)
    #         return value
    #
    #
    # def start(self)->str:
    #     if self.simulate is True:
    #         res= 'TEST ON'
    #     else:
    #         res = self.send_command(Code.main_func,State.ON)
    #     return res
    #
    # def stop(self)->str:
    #     if self.simulate is True:
    #         res= 'TEST OFF'
    #     else:
    #         res = self.send_command(Code.main_func,State.OFF)
    #     return res
    #
    #
    # def get_manu_test_result(self):
    #     pass
    #
    #
    # def get_auto_test_result(self):
    #     pass
