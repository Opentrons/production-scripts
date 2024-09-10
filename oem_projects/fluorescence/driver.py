import time
import serial
import serial.tools.list_ports
import codecs


class SerialDriver:
    @classmethod
    def get_com_list(cls):
        port_list = serial.tools.list_ports.comports()
        return port_list

    def __init__(self, baud):
        self.baud = baud
        self.port = None
        self.device = None

    def build_connection(self):
        res = SerialDriver.get_com_list()
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

    def format_code(self, code):
        return code.replace(" ", "").strip()

    def get_data(self, code: str, delay=0.1, buffer=100):
        """
        get buffer
        :param code:
        :param delay:
        :param buffer:
        :return:
        """
        # byte_array = codecs.decode(code.encode(), 'hex')

        byte_array = bytes.fromhex(code)
        data = self.send_and_read(byte_array, delay=delay, ReceiveBuffer=buffer)
        return data.upper()

    def check_connection(self):
        """
        检查连接状态
        """
        result = self.get_data('5E 01 00 05 64')
        if self.format_code(result) == self.format_code('5E 81 00 06 00 E5'):
            print("Connect Successfully")
            return True
        else:
            raise ConnectionError("Connection fail")

    def get_fluorescence_data(self):
        """
        获取荧光原始数据
        """
        length = ''
        status = ''
        result = ''
        for _ in range(4):
            if length == '1E' and status == '00':
                channels = [int(result[8:14], 16), int(result[14:20], 16), int(result[20:26], 16),
                            int(result[26:32], 16),
                            int(result[32:38], 16), int(result[38:44], 16), int(result[44:50], 16),
                            int(result[50:56], 16)]
                return channels
            else:
                result = self.get_data('5E 17 00 06 01 7C', delay=5, buffer=200)
                length = result[6:8]
                status = result[-4:-2]
        raise ValueError('Check received data error !')

    def get_concentration(self, fluorescence: list) -> list:
        """
        获取浓度
        """
        k = 0.000198
        b = -0.049392
        return [round(i * k + b, 3) for i in fluorescence]


if __name__ == '__main__':
    device = SerialDriver(9600)
    device.build_connection()
    device.check_connection()
    data = device.get_fluorescence_data()
    concentration = device.get_concentration(data)
    print(concentration)
