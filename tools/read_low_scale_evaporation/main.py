import time

from devices.air_sensor import AirSensor
from devices.low_scale import Scale
import datetime


class ReadScale:
    def __init__(self):
        self.air_sensor = AirSensor()
        self.scale = Scale()

    def read(self):
        _time = datetime.datetime.now()
        value_g = self.scale.read_volume()
        air = self.air_sensor.get_read()
        return f"{str(_time)}, {value_g}, {air[0]}, {air[1]}"

    def write_csv(self, data):
        with open("../../testing_data/read_scale.csv", mode="a") as f:
            f.write(data + "\n")


if __name__ == '__main__':
    r = ReadScale()
    while True:
        data = r.read()
        print(data)
        r.write_csv(data)
        time.sleep(3)
