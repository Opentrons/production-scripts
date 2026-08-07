from drivers.serial_driver import SerialDriver


class Scale:
    def __init__(self):
        self.scale = SerialDriver()
        self.scale.init(9600, device_name="Scale")

    def read_volume(self):
        res = self.scale.write_and_get_buffer("S")
        print(f"Scale: {res}")
        res = res.split()
        for item in res:
            if '.' in str(item):
                res = float(item)
        return res


if __name__ == '__main__':
    s = Scale()
    s.read_volume()
