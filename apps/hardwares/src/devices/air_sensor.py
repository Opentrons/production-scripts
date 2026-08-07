from drivers.serial_driver import SerialDriver
from serial.serialutil import SerialException
import codecs
import time

addrs = {
    "01": "C40B",
    "02": "C438",
    "03": "C5E9",
    "04": "C45E",
    "05": "C58F",
    "06": "C5BC",
    "07": "C46D",
    "08": "C492",
    "09": "C543",
    "10": "C74A",
    "0A": "48d9",
}


class AirSensor:
    def __init__(self):
        self.serial = SerialDriver()
        self.serial.get_device()
        self.serial.init_serial(9600)
        self._sensor_address: str = "01"

    def get_read(self):
        """
        read tem, hum
        :return:
        """
        data_packet = "{}0300000002{}".format(
            self._sensor_address, addrs[self._sensor_address]
        )
        command_bytes = codecs.decode(data_packet.encode(), "hex")
        try:
            self.serial.com.flushInput()
            self.serial.com.flushOutput()
            self.serial.com.write(command_bytes)
            time.sleep(0.5)

            length = self.serial.com.inWaiting()
            res = self.serial.com.read(length)

            res = codecs.encode(res, "hex")
            relative_hum = res[6:10]
            temp = res[10:14]
            temp = float(int(temp, 16)) / 10
            relative_hum = float(int(relative_hum, 16)) / 10
            return temp, relative_hum

        except (IndexError, ValueError) as e:
            print("Bad value read", e)
        except SerialException:
            print("Communication error")
            error_msg = "Asair Sensor not connected. Check if port number is correct."
            print(error_msg)


if __name__ == '__main__':
    air = AirSensor()
    for i in range(1000):
        air.get_read()
        time.sleep(1)
