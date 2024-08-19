from opentrons import protocol_api
import serial
import serial.tools.list_ports
import codecs
from enum import Enum
import hashlib

"""
User Arguments, 定义用户参数
1. USER_LIQUID - slot1 试剂所有列及配比容量(ul)
2. SERIAL_DEVICE_INDEX 设备端口号所在索引 (一般不需要变，假如机器连接多个串口设备可能需要改动)
4. LIQUID_CAL_VALUE 每个孔板试剂的安全液体容量警戒值（ul）
4. LIQUID_REAL_VALUE 每个孔板试剂的真实值（ul）
5. SINGLE_VOLUME 每次吸取的固定容量 (ul)
6. DARK_DURATION 遮光孵化时间 (min)
7. HEAT_TEMP_GAP 加热设备真实与预期的差值 （摄氏度）
8. USE_MODE 运行模式 调试模式会缩短运行时间
"""
LIQUID_CAL_RANGE = 880
LIQUID_REAL_RANGE = 1000

USER_LIQUID = {
    "Ac": {1: LIQUID_REAL_RANGE, 2: LIQUID_REAL_RANGE},
    "Rd": {3: LIQUID_REAL_RANGE},
    "Tf": {4: LIQUID_REAL_RANGE},
    "Et": {5: LIQUID_REAL_RANGE},
    "Ds": {6: LIQUID_REAL_RANGE},
    "Wa": {7: LIQUID_REAL_RANGE, 8: LIQUID_REAL_RANGE, 9: LIQUID_REAL_RANGE},
    "Sample": {1: LIQUID_REAL_RANGE},
    "Enzyme": {1: LIQUID_REAL_RANGE}
}  # BayOmics Liquid loaded on slot1, 每种液体定义所在列及孔板容量(Ul)

SERIAL_DEVICE_INDEX = 1
SINGLE_VOLUME = 20
DARK_DURATION = 1

HEAT_TEMP_GAP = 2
USE_MODE = "Debugging"

"""
import serial driver
"""
INIT_DEVICE = True
VERIFY_RESPONDS = True
EXPLAIN_FLAG = False

RUN_TIMES = 0


class DropMethod(Enum):
    DoNotDrop = 1  # 不丢针管
    DropAtLast = 2  # 最后再丢针管
    DropForAColumn = 3  # 完成一列移液后丢针管
    DropOnceUse = 4  # 一旦使用就丢针管


class BayOmicsLib:
    @classmethod
    def get_com_list(cls):
        port_list = serial.tools.list_ports.comports()
        return port_list

    def __init__(self, baud, protocol):
        self.baud = baud
        self.port = None
        self.device = None
        self.protocol: protocol_api.ProtocolContext = protocol
        self.simulate = False
        self.led_virtual = True

    def opentrons_delay(self, times):
        self.protocol.delay(times)

    def print_f(self, msg):
        self.protocol.comment(msg)

    def build_connection(self):
        res = BayOmicsLib.get_com_list()
        self.print_f("=" * 5 + "PORT LIST" + "=" * 5)
        for index, p in enumerate(res):
            self.print_f(f"{index + 1} >>{p.device}")
        # select = input("Select Port Number(输入串口号对应的数字):")
        select = str(SERIAL_DEVICE_INDEX)
        if self.port is None:
            if len(res) == 0:
                self.port = "None"
            else:
                self.port = res[int(select.strip()) - 1].device
        if self.port == "None":
            self.device = None
            return
        self.device = serial.Serial(self.port, self.baud, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                                    bytesize=serial.EIGHTBITS, timeout=1)
        if self.device.isOpen():
            self.print_f(f"{self.port} Opened! \n")
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
        self.print_f(f"{self.port} Closed! \n")

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
        self.opentrons_delay(delay)
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
            if words.upper() in responds.upper():
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
        if self.simulate:
            ret = ""
        else:
            ret = self.get_tm_data(_send, is_without_crc=is_without_crc)
        verify = _send if verify is None else verify
        if not self.simulate:
            self._verify_responds(ret, verify)
        if EXPLAIN_FLAG:
            self.print_f(label + f": {ret}")
        return ret

    def set_led_rounds(self, _round: int, initial_point=True):
        """
        :param _round:
        :param initial_point:
        display screen number
        :return:
        """
        self.print_f(f"Setting Round {_round}...")
        # 设置小数点 - 0
        if initial_point:
            self.send_to_device("010600100000", "Set Led Point")
        # set round
        set_number = self._format_hex(_round)
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
        if not self.led_virtual:
            self.set_led_pressure_value(0)

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
                self.opentrons_delay(1)
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
            self.opentrons_delay(5)
            self.send_to_device("050600000300", "Set R Axis Speed Mode", verify="")
            self.judge_pos(60, 'r', "00000000")
        if y:
            self.set_axis_speed('y')
            self.send_to_device("06 10 00 01 00 02 04 BA 24 FF FF", "Move Relative", verify="061000010002")
            self.send_to_device("060600000302", "Set Y Axis Relative Position Mode", verify="")
            self.opentrons_delay(1.5)
            self.send_to_device("060600000300", "Set Y Axis Speed Mode", verify="")
            self.judge_pos(30, 'y', "00000000")
        if z:
            self.set_axis_speed('z')
            self.send_to_device("07 10 00 01 00 02 04 AC FF FF FF", "move relative", verify="")
            self.send_to_device("070600000302", "Set Z Axis Relative Position Mode", verify="")
            self.opentrons_delay(1)
            self.send_to_device("070600000300", "Set Z Axis Speed Mode", verify="")
            self.judge_pos(30, 'z', "00000000")

    def init_motors(self, y=True, z=True, r=True):
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

    def set_lights(self, light):
        """
        开启等带
        :param light:
        :return:
        """
        self.print_f("Set rail lights ON" if light else "Set rail lights OFF")
        self.protocol.set_rail_lights(light)

    def init_device(self):
        """
        init device, ready for work
        :return:
        """
        self.set_pressure_off()
        self.init_motors()
        self.set_temperature_controller_off()
        self.home()
        self.protocol.comment("Set rail lights ON")
        self.set_lights(True)

    def close_lid(self):
        """
        close_lid
        :return:
        """
        self.send_to_device("050600000301", "Set R Axis Speed Mode", verify="")  # 位置模式
        self.send_to_device("05 10 00 01 00 02 04 F7 D4 FF FF", "close lid", verify="051000010002")
        self.judge_pos(60, "r", "F7D4FFFF")

    def dark_incubation(self, dark_time: int):
        """
        遮光时常
        :return:
        """
        self.set_lights(False)
        self.close_lid()
        self.opentrons_delay(dark_time)
        self.home(y=False, z=False)
        self.set_lights(True)

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
        if not self.simulate:
            data_value = data[6:10]
            temp = int(data_value, 16)
            return float(int(temp) / 10)
        else:
            return 0

    def read_real_temperature(self):
        """
        获取真实的温度
        :return:
        """
        data = self.send_to_device("02 03 00 4A 00 01", "Read Real Temperature", verify="0203")
        if not self.simulate:
            data_value = data[6:10]
            temp = int(data_value, 16)
            return float(int(temp) / 10)
        else:
            return 0

    def compare_temperature(self, tolerance):
        """
        compare difference between temp
        :param tolerance: 允许的差异
        :return:
        """
        for i in range(600):
            self.opentrons_delay(1)
            setting_temp = self.read_setting_temperature()
            real_temp = self.read_real_temperature()
            if abs(setting_temp - real_temp) < tolerance:
                break
        raise TimeoutError("reach time out")

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
        self.close_lid()
        for heat_setting in heat_list:
            temp = heat_setting["temperature"]
            keep_times = heat_setting["time"]
            self.heat_device(temp)
            for i in range(keep_times):
                self.opentrons_delay(0.3)
                self.set_led_rounds(i + 1)
            # compare temp
            set_temp = self.read_setting_temperature()
            real_temp = self.read_real_temperature()
            assert abs(set_temp - real_temp) < HEAT_TEMP_GAP, "heat device fail"
        self.stop_heat()
        self.home(y=False, z=False)

    def move_y(self, position: str):
        """
        移动y
        :param position:
        :return:
        """
        for i in range(3):
            self.send_to_device("060600000301", "Set Y Axis Position Mode", verify="")
            self.send_to_device(f"06100001000204{position}", f"Move Y To {position}", verify="061000010002")
            ret = self.judge_pos(30, 'y', position, judge_method="others")
            if ret:
                return 0
        if not self.simulate:
            raise TimeoutError("Move Y Time Out")

    def move_z(self, position: str):
        """
        移动z
        :param position:
        :return:
        """
        for i in range(3):
            self.send_to_device("070600000301", "Set Z Axis Position Mode", verify="")
            self.send_to_device(f"07100001000204{position}", f"Move Z To {position}", verify="071000010002")
            ret = self.judge_pos(30, 'z', position, judge_method="others")
            if ret:
                return 0
        if not self.simulate:
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

    def set_pressure(self, pressure, duration):
        """
        施加压力过程
        :param pressure: 压力值（MPa）
        :param duration: 持续时间 （s）
        :return:
        """
        self.move_to_work_position()
        pressure_kpa = pressure * 1000
        # 显示压力值
        self.set_led_pressure_value(int(pressure_kpa))
        voltage_mv = int(((pressure_kpa + 123.75) / 124.75) * 1000)
        voltage_mv_string = self._format_hex(voltage_mv)
        self.send_to_device("03 05 00 41 FF 00", "Pressure Open")  # 阀门开启
        self.send_to_device(f"0406000A{voltage_mv_string}", f"Set Pressure {pressure} Mpa", verify="")  # 设置正压
        self.opentrons_delay(duration)
        # 关闭压力
        self.set_pressure_off()
        # 释放work position
        self.release_work_position()

    def move_to_work_position(self, home=False):
        """
        y轴和z轴移动到工作点
        :return:
        """
        if home:
            self.home()
        self.move_y("BA24FFFF")
        self.move_z("AC67FFFF")

    def release_work_position(self):
        """
        释放work position, ready home
        :return:
        """
        # self.move_z("00000000")
        self.home(r=False)

    def init_led(self):
        """
        set led
        :return:
        """
        if self.led_virtual:
            self.set_led_virtual_value()

    def release_device(self):
        """
        释放设备
        :return:
        """
        self.print_f("实验完成，正在关闭设备...")
        self.home()
        self.set_pressure_off()
        self.set_temperature_controller_off()
        self.set_led_rounds(0)
        self.close_device()
        self.set_lights(False)

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


def _transfer_user_liquid(pipette: protocol_api.InstrumentContext, liquid_labware: protocol_api.Labware,
                         customer_labware: protocol_api.labware, customer_labware_pos: str, liquid_name: str,
                         volume: float, move_location: protocol_api.Labware, pick_up=False, drop=False):
    """
    移液&加压
    :param pipette:
    :param liquid_labware:
    :param customer_labware:
    :param customer_labware_pos:
    :param liquid_name:
    :param volume:
    :param move_location:
    :param drop:
    :param pick_up:
    :return:
    """

    def _drop_tip():
        if not drop:
            pass
        else:
            pipette.move_to(move_location['A1'].top(z=50))
            pipette.drop_tip()

    aspirate_flag = False
    if pick_up:
        pipette.pick_up_tip()
    liquid: dict = USER_LIQUID[liquid_name]
    _trans_times = int(volume / SINGLE_VOLUME)
    _trans_last_volume = (volume % SINGLE_VOLUME)

    for i in range(_trans_times):
        for key, value in liquid.items():
            if value > (LIQUID_REAL_RANGE - LIQUID_CAL_RANGE):
                pipette.aspirate(SINGLE_VOLUME, liquid_labware[f"A{key}"])
                USER_LIQUID[liquid_name][key] -= SINGLE_VOLUME
                aspirate_flag = True
                break
        assert aspirate_flag, "Aspirate liquid fail"
        pipette.dispense(SINGLE_VOLUME, customer_labware[customer_labware_pos])

    if _trans_last_volume > 0:
        for key, value in liquid.items():
            if value > (LIQUID_REAL_RANGE - LIQUID_CAL_RANGE):
                pipette.aspirate(_trans_last_volume, liquid_labware[f"A{key}"])
                USER_LIQUID[liquid_name][key] -= _trans_last_volume
                aspirate_flag = True
                break
        assert aspirate_flag, "Aspirate liquid fail"
        pipette.dispense(_trans_last_volume, customer_labware[customer_labware_pos])
    _drop_tip()


def transform_round(pipette: protocol_api.InstrumentContext, liquid_labware: protocol_api.Labware,
                    customer_labware: protocol_api.labware, liquid_name: str, sample_counts: int,
                    volume: float, move_location: protocol_api.Labware, serial_device: BayOmicsLib, pressure=None,
                    duration=30, drop_method: DropMethod = DropMethod.DropAtLast, protocol=None):
    """
    执行加液，正压，一个流程
    :param pipette:
    :param liquid_labware:
    :param customer_labware:
    :param liquid_name:
    :param sample_counts:
    :param volume:
    :param move_location:
    :param serial_device:
    :param pressure:
    :param duration:
    :param drop_method:
    :param protocol:
    :return:
    """
    for i in range(int(sample_counts / 8)):
        if drop_method == DropMethod.DropAtLast:
            drop = True if i == (int(sample_counts / 8) - 1) else False
            pick_up = True if i == 0 else False
        elif drop_method == DropMethod.DropForAColumn:
            drop = True
            pick_up = True
        else:
            drop = True
            pick_up = True
        _transfer_user_liquid(pipette, liquid_labware, customer_labware, f'A{i + 1}', liquid_name, volume, move_location,
                             pick_up=pick_up, drop=drop)
    if pressure:
        if USE_MODE == "Debugging":
            duration = 1
        serial_device.set_pressure(pressure, duration)
    if protocol is not None:
        protocol.pause(f"USER_LIQUID: {USER_LIQUID}")


"""
用户密码
"""


def _auth(pwd: int):
    """
    用户鉴权
    :param pwd: 0 ~ 999999
    :return:
    """
    md5_object = hashlib.md5()  # 创建MD5对象
    saved_pwd = "2a123be7c92297bf4ebf9eeeb69d3e98"  # 当前临时密码 342566
    user_pwd = str(pwd).strip().encode('utf-8')
    md5_object.update(user_pwd)
    user_pwd = md5_object.hexdigest()
    if user_pwd == saved_pwd:
        return True
    else:
        return False
