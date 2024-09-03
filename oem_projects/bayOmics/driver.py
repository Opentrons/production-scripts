"""
@date: 2024-7-1
@author: andy.hu@opentrons.com
@description: this is basic controller driver for BayOmics temperature module
"""
import time
import serial
import serial.tools.list_ports
import codecs
from enum import Enum

VERIFY_RESPONDS = False
EXPLAIN_FLAG = False
SET_LED_VIRTUAL = True


class UserMode(Enum):
    Debugging = 1
    Running = 2


class BasicDriver:
    @classmethod
    def get_com_list(cls):
        port_list = serial.tools.list_ports.comports()
        return port_list

    def __init__(self, baud):
        self.baud = baud
        self.port = None
        self.device = None
        self.led_virtual = True
        self.simulate = False
        self.user_mode = UserMode.Running

    def build_connection(self):
        res = BasicDriver.get_com_list()
        print("=" * 5 + "PORT LIST" + "=" * 5)
        for index, p in enumerate(res):
            print(f"{index + 1} >>{p.device}")
        select = input("Select Port Number(输入串口号对应的数字):")
        if self.port is None:
            self.port = res[int(select.strip()) - 1].device
        self.device = serial.Serial(self.port, self.baud, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                                    bytesize=serial.EIGHTBITS, timeout=1)
        if self.device.isOpen():
            print(f"{self.port} Opened! \n")
        # settings
        self.device.bytesize = serial.EIGHTBITS  # 数据位 8
        self.device.parity = serial.PARITY_NONE  # 无校验
        self.device.stopbits = serial.STOPBITS_ONE  # 停止位 1

    def close_device(self):
        """
        close com
        :return:
        """
        self.device.close()
        print(f"{self.port} Closed! \n")

    def calc_crc(self, string):
        data = bytearray.fromhex(string)
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for i in range(8):
                if ((crc & 1) != 0):
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        crc_data = hex(((crc & 0xFF) << 8) + (crc >> 8))[2:]
        for i in range(4 - len(crc_data)):
            crc_data = '0' + crc_data
        return crc_data.upper()

    def send_and_read(self, send, delay=0.1, ReceiveBuffer=100):
        """
        send code and read buffer
        :param send:
        :param delay:
        :param ReceiveBuffer:
        :return:
        """
        if self.device is None:
            return
        if type(send) is not bytes:
            send = (send + "\r\n").encode('utf-8')
        self.device.flushInput()
        self.device.flushOutput()
        self.device.write(send)
        time.sleep(delay)
        data = self.device.read(ReceiveBuffer)
        data = codecs.encode(data, "hex")
        return data.decode('utf-8')

    def get_tm_data(self, code: str, is_without_crc=False):
        """
        get buffer
        :param code:
        :return:
        """
        # byte_array = codecs.decode(code.encode(), 'hex')
        if is_without_crc:
            code = code + self.calc_crc(code)
        byte_array = bytes.fromhex(code)
        data = self.send_and_read(byte_array)
        return data.upper()

    def _format_hex(self, value: int):
        value = hex(value)[2:]
        for i in range(4 - len(value)):
            value = '0' + value
        return value

    def _verify_responds(self, responds, words):
        """
        验证返回值
         :param responds: 返回值
        :param words: words in responds ?
        :return:
        """
        if not VERIFY_RESPONDS:
            return
        if responds == "":
            result = False
        else:
            if words in responds:
                result = True
            else:
                result = False
        assert result, f"{words} don't in {responds}"

    def send_to_device(self, _send: str, label, verify=None, is_without_crc=True):
        """
        send code
        :param _send:
        :param label:  explain
        :param verify:
        :param is_without_crc:
        :return:
        """
        _send = _send.replace(" ", "").strip()
        ret = self.get_tm_data(_send, is_without_crc=is_without_crc)
        verify = _send if verify is None else verify
        self._verify_responds(ret, verify)
        if EXPLAIN_FLAG:
            print(label + f": {ret}")
        return ret

    def set_led_rounds(self, _round: int, initial_point=True):
        """
        :param _round:
        :param initial_point:
        display screen number
        :return:
        """
        print(f"Setting Round {_round}...")
        # 设置小数点 - 0
        if initial_point:
            self.send_to_device("010600100000", "Set Led Point")
        # set round
        set_number = self._format_hex(_round)
        self.send_to_device(f"01060007{set_number}", "Set Led Value")

    def set_led_pressure_value(self, value: int):
        """
        set display pressure value
        :param value: pressure (Kpa)
        :return:
        """
        print(f"Setting Led Display")
        # 设置小数点 - 0
        if not self.led_virtual:
            self.send_to_device("010600100003", "Set Led Point")
        # set round
        set_number = self._format_hex(value)
        self.send_to_device(f"01060007{set_number}", "Set Led Value")

    def set_led_virtual_value(self):
        """
        设置虚拟值
        :return:
        """
        self.send_to_device("01 06 00 00 00 5F", "Set Virtual 1")
        self.send_to_device("01 06 00 01 00 5F", "Set Virtual 2")
        self.send_to_device("01 06 00 02 00 5F", "Set Virtual 3")
        self.send_to_device("01 06 00 03 00 5F", "Set Virtual 4")

    def set_pressure_off(self):
        """
        正压不加载，两通阀门闭合
        :return:
        """
        self.send_to_device("0406000A0000", "Set Pressure 0")
        self.send_to_device("030500410000", "Set Pressure Off")

    def set_motor_enable(self, y=True, z=True, r=True):
        """
        set motor enable
        :param y:
        :param z:
        :param r:
        :return:
        """
        if y:
            self.send_to_device("060600000101", "Set Y Axis Enable")
        if z:
            self.send_to_device("070600000101", "Set Z Axis Enable")
        if r:
            self.send_to_device("050600000101", "Set R Axis Enable")

    def judge_pos(self, run_times: int, axis: str, target_pos: str, judge_method="Interrupt"):
        """
        判断是否到达指定位置
        :param run_times:
        :param axis:
        :param target_pos:
        :param judge_method:
        :return:
        """
        if not self.simulate:
            for i in range(run_times):
                time.sleep(1)
                current_pos = self.get_axis_position(axis)
                if current_pos == target_pos:
                    return True
                if i == run_times - 1:
                    if judge_method == "Interrupt":
                        raise RuntimeError("Move timeout")
                    else:
                        return False
        else:
            pass

    def set_axis_speed(self, axis: str):
        """
        设置速度
        :param axis:
        :return:
        """
        if "y" in axis:
            self.send_to_device("06 10 00 03 00 02 04 00 00 44 7A", "Set Y Axis Speed", verify="061000030002")
        elif 'z' in axis:
            self.send_to_device("071000030002048000463B", "Set Z Axis Speed", verify="071000030002")  # 8000463B
        elif "r" in axis:
            pass

    def home(self, y=True, z=True, r=True):
        """
        home motor, move axis to the default position
        :param y:
        :param z:
        :param r:
        :return:
        """
        if r:
            self.send_to_device("05 10 00 03 00 02 04 00 00 42 48", "Set Speed 192000", verify="")
            self.send_to_device("05 10 00 01 00 02 04 FD 9C FF FF", "Move Relative", verify="")
            self.send_to_device("050600000302", "Set R Axis Relative Position Mode", verify="")
            time.sleep(5)
            self.send_to_device("050600000300", "Set R Axis Speed Mode", verify="")
            self.judge_pos(60, 'r', "00000000")
        if z:
            self.set_axis_speed('z')
            self.send_to_device("070600000302", "Set Z Axis Relative Position Mode", verify="")
            self.send_to_device("07 10 00 01 00 02 04 AC FF FF FF", "move relative", verify="")
            time.sleep(0.5)
            self.send_to_device("070600000300", "Set Z Axis Speed Mode", verify="")
            self.judge_pos(30, 'z', "00000000")
        if y:
            self.set_axis_speed('y')
            self.send_to_device("06 10 00 01 00 02 04 BA 24 FF FF", "Move Relative", verify="061000010002")
            self.send_to_device("060600000302", "Set Y Axis Relative Position Mode", verify="")
            time.sleep(1.5)
            self.send_to_device("060600000300", "Set Y Axis Speed Mode", verify="")
            self.judge_pos(30, 'y', "00000000")

    def init_motors(self):
        """
        初始话电机速度，各轴初始化工作位置
        :param y:
        :param z:
        :param r:
        :return:
        """
        self.set_motor_enable()
        self.set_axis_speed("y")
        self.set_axis_speed("z")

    def set_temperature_controller_off(self):
        """
        关闭温控器
        :return:
        """
        self.send_to_device("0206001B0001", "Set Temperature Controller Off")

    def init_device(self):
        """
        init device, ready for work
        :return:
        """
        self.set_pressure_off()
        self.init_motors()
        self.set_temperature_controller_off()
        # self.home()

    def close_lid(self):
        """
        close_lid
        :return:
        """
        self.send_to_device("050600000301", "Set R Axis Speed Mode", verify="")  # 位置模式
        self.send_to_device("05 10 00 01 00 02 04 F7 D4 FF FF", "close lid", verify="051000010002")
        ret = self.judge_pos(60, "r", "F7D4FFFF", judge_method="")
        if not ret:
            for i in range(3):
                judge_m = "Interrupt" if i >= 2 else ""
                self.home(y=False, z=False)
                self.send_to_device("050600000301", "Set R Axis Speed Mode", verify="")  # 位置模式
                self.send_to_device("05 10 00 01 00 02 04 F7 D4 FF FF", "close lid", verify="051000010002")
                self.judge_pos(60, "r", "F7D4FFFF", judge_method=judge_m)

    def dark_incubation(self, dark_time: int):
        """
        遮光时常
        :return:
        """
        self.close_lid()
        time.sleep(dark_time)
        self.home(y=False, z=False)

    def heat_device(self, temp: float):
        """
        heat
        :param temp: 浮点，一位小数
        :return:
        """
        temp = int(temp * 10)
        temp = self._format_hex(temp)
        self.send_to_device(f"02060000{temp}", f"Set Temperature {temp}")
        # 开始加热
        self.send_to_device("02 06 00 1B 00 00", "Start to heat")

    def stop_heat(self):
        """
        停止加热
        :return:
        """
        self.send_to_device("02 06 00 1B 00 01", "Stop heating")

    def read_setting_temperature(self):
        """
        获取设定的温度
        :return:
        """
        data = self.send_to_device("02 03 00 4B 00 01", "Read Setting Temperature", verify="0203")
        data_value = data[6:10]
        temp = int(data_value, 16)
        return float(int(temp) / 10)

    def read_real_temperature(self):
        """
        获取真实的温度
        :return:
        """
        data = self.send_to_device("02 03 00 4A 00 01", "Read Real Temperature", verify="0203")
        data_value = data[6:10]
        temp = int(data_value, 16)
        return float(int(temp) / 10)

    def read_heat_status(self):
        """
        读取加温状态
        :return:
        """
        data = self.send_to_device("02 03 00 4D 00 01", "Read Heat Controller Status", verify="0203")
        return data

    def heat_incubation(self, heat_list: list):
        """
        加温孵化
        1. 关盖
        2. 根据heat_list配置加温曲线
        :param heat_list:
        :return:
        """
        for heat_setting in heat_list:
            temp = heat_setting["temperature"]
            keep_times = heat_setting["time"]
            self.heat_device(temp)
            time.sleep(keep_times)
            # compare temp
            set_temp = self.read_setting_temperature()
            real_temp = self.read_real_temperature()
            assert abs(set_temp - real_temp) < 1, "heat device fail"

    def move_y(self, position: str):
        """
        移动y
        :param position:
        :return:
        """
        for i in range(3):
            self.set_axis_speed('y')
            self.send_to_device("060600000301", "Set Y Axis Position Mode", verify="")
            self.send_to_device(f"06100001000204{position}", f"Move Y To {position}", verify="061000010002")
            ret = self.judge_pos(30, 'y', position, judge_method="others")
            if ret:
                return 0
        raise TimeoutError("Move Y Time Out")

    def move_z(self, position: str):
        """
        移动z
        :param position:
        :return:
        """
        for i in range(3):
            self.set_axis_speed('z')
            self.send_to_device("070600000301", "Set Z Axis Position Mode", verify="")
            self.send_to_device(f"07100001000204{position}", f"Move Z To {position}", verify="071000010002")
            ret = self.judge_pos(30, 'z', position, judge_method="others")
            if ret:
                return 0
        raise TimeoutError("Move Z Time Out")

    def get_axis_position(self, axis: str):
        """
        get position
        :param axis: x, y, z
        :return:
        """
        if 'R' in axis.upper():
            data = self.send_to_device("05 04 00 02 00 02", "Get R Axis Position", verify="")
        elif "Z" in axis.upper():
            data = self.send_to_device("07 04 00 02 00 02", "Get Z Axis Position", verify="")
        elif "Y" in axis.upper():
            data = self.send_to_device("06 04 00 02 00 02", "Get Y Axis Position", verify="")
        else:
            raise ValueError("Can't find Axis")
        return (data[6:14].upper())

    def read_pressure(self):
        """
        读取气压值
        """
        data = self.send_to_device("04 04 00 00 00 01", "Read Pressure", verify="")
        value = data[6:10]
        value = int(value, 16) / 1000
        value_mpa = 0.125 * value - 0.124
        return value_mpa

    def set_pressure(self, pressure, duration):
        """
        施加压力过程
        :param pressure: 压力值（MPa）
        :param duration: 持续时间 （s）
        :return:
        """
        # self.move_to_work_position()
        if self.user_mode == UserMode.Debugging:
            pressure_kpa = 0
        else:
            pressure_kpa = pressure * 1000
        # voltage_mv = int(((pressure_kpa + 123.75) / 124.75) * 1000)  # * 10000
        voltage_mv = int(pressure_kpa * 10)
        voltage_mv_string = self._format_hex(voltage_mv)
        self.send_to_device("03 05 00 41 FF 00", "Pressure Open")  # 阀门开启
        self.send_to_device(f"0406000A{voltage_mv_string}", f"Set Pressure {pressure} Mpa", verify="")  # 设置正压
        time.sleep(0.5)
        pressure = self.read_pressure()
        print(f"SET {(i + 1) * 0.01} GET {pressure}")
        # 显示压力值
        self.set_led_pressure_value(int(pressure * 1000))
        time.sleep(duration)
        # 关闭压力
        self.set_pressure_off()
        # 释放work position
        # self.release_work_position()

    def move_to_work_position(self, home=False):
        """
        y轴和z轴移动到工作点
        :return:
        """
        if home:
            self.home()
        self.move_y("BAD0FFFF")
        self.move_z("8E3EFFFF")

    def release_work_position(self):
        """
        释放work position, ready home
        :return:
        """
        self.move_z("00000000")
        self.home(r=False)

    def init_led(self):
        """
        set led
        :return:
        """
        if SET_LED_VIRTUAL:
            self.set_led_virtual_value()

    def init_loop(self):
        """
        run main
        :return:
        """
        """ 一、串口连接
        1. 连接串口
        2. 初始化led
        """
        self.build_connection()
        self.init_led()

        """ 二、初始化
        1. 使能电机，初始化速度和复位
        2. 关闭加压
        3. 关闭温度控制器
        """
        self.init_device()


if __name__ == '__main__':
    bd = BasicDriver(19200)
    bd.build_connection()
    # for i in range(10):
    #     print(f"Round ---------------------------- {i + 1}")
    #     bd.set_pressure((i + 1) * 0.01, 10)
    bd.init_device()
    bd.close_lid()

    # bd.init_device()
    """
    1. x y z 轴电机测试
    """
    # for i in range(10):
    #     print(f"Round ---------------------------- {i + 1}")
    #     bd.move_to_work_position()
    #     bd.set_pressure((i + 1) * 0.01, 10)
    # bd.home()

    # """
    # 2. 保温测试
    # """
    # # bd.heat_incubation([{"temperature": 70, "time": 60}])
    # # bd.move_z("AC67FFFF")
    # """
    # 3. led测试
    # """
    # bd.set_led_virtual_value()
