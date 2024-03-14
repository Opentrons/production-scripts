import os
import subprocess
from typing import List
import csv

ProjectName = "ot3_testing"


class Utils:

    @classmethod
    def get_root_path(cls):
        current_dir = os.getcwd()
        current_dir = current_dir[:(current_dir.index(ProjectName) + len(ProjectName))]
        return current_dir

    @classmethod
    def add_path(cls, root_path, add):
        """
        connect path
        :param root_path:
        :param add:
        :return:
        """
        res = os.path.join(root_path, add)
        return res

    @classmethod
    def test_online(cls, device: str):
        """
        ping device
        :param device: id address
        :return:
        """
        cmd = f"ping -n 1 {device}"
        try:
            result = subprocess.check_output(cmd, shell=True).decode('gbk')
            if 'ttl' in result.lower():
                print(f"{device} online")
                return True
            else:
                print(f"{device} offline")
                return False
        except subprocess.CalledProcessError as e:
            print(e, f"{device} online")
            return False

    @classmethod
    def test_online2(cls, device):
        """
        test online
        :param device:
        :return:
        """
        import os
        forbidden = ['&', ';', '-', ' ', '||', '|']
        for i in forbidden:
            if i in device:
                print('Catch you')
                exit()
        result = os.popen(f'ping -c 1 -t 1 {device}').read()
        if 'ttl' in result:
            print('IP 在线')
        else:
            print('IP 不在线')

    @classmethod
    def test_devices_online(cls, devices: List[str]):
        """
        show online devices
        :param devices:
        :return:
        """
        print("============list devices=============")
        for device in devices:
            Utils.test_online(device)

    @classmethod
    def write_to_csv(cls, filename, row: list):
        with open(filename, 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(row)


if __name__ == '__main__':
    Utils.write_to_csv("output.csv", [1,2,3])