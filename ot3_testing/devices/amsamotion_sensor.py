import codecs
from devices.driver import SerialDriver
from devices.crc_func import crc16_modbus


class LaserSensor:
    def __init__(self):
        self.serial = SerialDriver()

    def init_device(self):
        """
        get device
        :return:
        """
        self.serial.init(9600)

    def get_distance_multi(self, device_addr: int):
        """
        get multi ch data
        :param device_addr:
        :return: return 8ch value
        """
        multi_value = {}
        read_data = ""
        crc_16 = crc16_modbus(f"0{device_addr}0400000008")
        for repeat in range(5):
            read_data = self.serial.write_and_get_buffer(bytes.fromhex(f'0{device_addr}0400000008{crc_16}'), times=1)
            if read_data[0] == device_addr and read_data[1] == 4:
                break
            if repeat >= 4:
                raise ConnectionError("can't read sensor")
        data_length = codecs.encode(read_data[2:3], "hex")
        data_length = int(data_length.decode(), 16)
        data_value = read_data[3:(3 + data_length)]
        data_value = codecs.encode(data_value, "hex")
        # trans to int
        for i in range(8):
            data_channel = data_value[i * 4: (i * 4 + 4)]
            multi_value.update({i: int(data_channel.decode(), 16)})
        return multi_value

    def get_distance_single(self, device_addr: int, ch: int):
        """
        get single
        :param device_addr:
        :param ch:
        :return:
        """
        ret = self.get_distance_multi(device_addr)
        return ret[ch]


if __name__ == '__main__':
    ls = LaserSensor()
    ls.init_device()
    for i in range(100):
        ret = ls.get_distance_multi(2)
        print(ret)
