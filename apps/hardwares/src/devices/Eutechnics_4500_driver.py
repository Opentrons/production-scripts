"""
This driver is for the Eutechnics 4500 thermometer

Written by Carlos Fernandez
"""
import serial
import time
import os
import sys


class Eutechnics(serial.Serial):
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                 bytesize=serial.EIGHTBITS, timeout=0.1):
        self.error_count = 0
        self.max_errors = 100
        self.unlimited_errors = False
        self.raise_exceptions = True
        self.reading_raw = ''
        # Most likely port is the only parameter that would change
        self._serial = serial.Serial.__init__(self,
                                      port=port,
                                      baudrate=baudrate,
                                      parity=parity,
                                      stopbits=stopbits,
                                      bytesize=8,
                                      timeout=timeout)

    """This setups the themometer in outputing the temperature
    This function needs to be called first before retrieving data off the
    thermometer"""

    def setup(self):
        self.rts = True
        self.__enter__()
        condition = True
        while condition:
            self._serial.write('\r\n'.encode("utf-8"))
            time.sleep(0.5)
            self.reading_raw = self.readline()
            # print(self.reading_raw)
            if self.reading_raw == b'> \r\n':
                self._serial.write('T'.encode("utf-8"))
                time.sleep(4)
                condition = False
        # self.reading_raw = self.readline()
        # print(self.reading_raw)

    """
    Return Readings off the thermometer
    """

    def temp_read(self):
        self.reset_input_buffer()
        self.reset_output_buffer()
        try:
            condition = True
            while condition:
                self._serial.write('\r\n'.encode("utf-8"))
                time.sleep(0.5)
                self.reading_raw = self._serial.readline().strip()
                # print(self.reading_raw )
                if self.reading_raw == b'> T':
                    pass
                elif len(self.reading_raw.decode().strip()) != 7:
                    pass
                elif self.reading_raw != b'':
                    # print('Reading Temperature')
                    condition = False
            return self.reading_raw.decode()
        except self.raise_exceptions:
            raise print('Bad Readings, check the connection')


if __name__ == '__main__':
    thermometer = Eutechnics(port='COM14')
    thermometer.unlimited_errors = True
    thermometer.setup()
    while True:
        temp_reading = thermometer.temp_read()
        print("Temp Reading: ", temp_reading, " C", len(temp_reading))
