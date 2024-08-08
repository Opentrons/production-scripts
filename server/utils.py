import json
import platform
import os
import subprocess
from typing import List
import csv
import hashlib


def create_id():
    import time
    this_time = time.time()

    def generate_md5(string):
        md5 = hashlib.md5(string.encode('utf-8')).hexdigest()
        return md5
    return (generate_md5(str(this_time)))


def write_local_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def read_local_json(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = json.load(f)
            return content
    except:
        return 0


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
                return True
            else:
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
            return True
        else:
            return False

    @classmethod
    def test_online3(cls, device):
        sys = platform.system()
        # IP地址
        IP = device
        if sys == "Windows":
            # 打开一个管道ping IP地址
            visit_IP = os.popen('ping %s' % IP)
            # 读取结果
            result = visit_IP.read()
            # 关闭os.popen()
            visit_IP.close()
            # 判断IP是否在线
            if 'TTL' in result:
                return True
            else:
                return False
        else:
            visit_IP = os.popen('ping -c 1 %s' % IP)
            result = visit_IP.read()
            visit_IP.close()
            if 'ttl' in result:
                return True
            else:
                return False

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
    create_id()
