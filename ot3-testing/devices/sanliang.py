from devices.driver import SerialDriver
import time


class SanLiang:
    def __init__(self):
        self.device = SerialDriver()
        self.device.init(9600)

    def read_distance(self):
        """
        read 1 times
        :return:
        """
        time.sleep(0.3)
        res = self.device.read_buffer()
        res = res.split()
        float_res = [float(item) for item in res]
        return sum(float_res) / len(float_res)

    def read_distance_n_times(self, number: int):
        """
        read n times
        :param number:
        :return:
        """
        res_list = []
        for i in range(number):
            res = self.read_distance()
            res_list.append(res)
        res_list.pop(res_list.index(max(res_list)))
        res_list.pop(res_list.index(min(res_list)))
        return sum(res_list) / len(res_list)

    def clear(self):
        """
        Zero
        :return:
        """
        for i in range(3):
            self.device.write_and_get_buffer("CLR", only_write=True)
            time.sleep(0.3)


if __name__ == '__main__':
    s = SanLiang()
    ret = s.read_distance_n_times(5)
    print(ret)
    # s.clear()
