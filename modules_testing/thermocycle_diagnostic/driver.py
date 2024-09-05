# encoding:utf-8

import time

import serial
import serial.tools.list_ports

Baud = 115200
ReceiveBuffer = 100


class SerialDriver:

    @classmethod
    def get_com_list(cls):
        port_list = serial.tools.list_ports.comports()
        return port_list

    def __init__(self):
        self.device = None
        self.com = None

    def get_device(self):
        """
        select device
        :return:
        """
        port_list = SerialDriver.get_com_list()
        print("=" * 5 + "PORT LIST" + "=" * 5)
        for port in port_list:
            print(f">>{port.device}")
        select = input("Select Port Number(输入串口号数字):")
        self.device = f'COM{select}'

    def init_serial(self):
        """
        init connection
        :return:
        """
        self.com = serial.Serial(self.device, Baud, timeout=0.01)
        if self.com.isOpen():
            print(f"{self.device} Opened! \n")

    def close(self):
        """
        close com
        :return:
        """
        self.com.close()
        print(f"{self.device} Closed! \n")

    def init(self):
        """
        main
        :return:
        """
        self.get_device()
        self.init_serial()

    def write_and_get_buffer(self, send: str, only_write=False, delay=None, times=30):
        """
        send cmd
        :return:
        """
        if self.com is None:
            return
        send = (send + "\r\n").encode('utf-8')
        self.com.write(send)
        if delay is None:
            pass
        else:
            time.sleep(delay)
        if only_write is True:
            return
        for i in range(times):
            data = self.com.read(ReceiveBuffer)
            if "OK" not in data.decode('utf-8') or "busy" in data.decode('utf-8'):
                time.sleep(1)
                continue
            return data.decode('utf-8')

    def read_buffer(self):
        """
        读取缓存
        :return:
        """
        data = self.com.read(ReceiveBuffer)
        return data.decode('utf-8')


if __name__ == '__main__':
    s = SerialDriver()
    s.init()
    res = s.write_and_get_buffer("M115")
