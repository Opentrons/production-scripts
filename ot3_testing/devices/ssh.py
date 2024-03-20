import paramiko
from ot3_testing.utils import Utils


class SSHClient:
    def __init__(self, hostname: str, port=22, username="root", password="None"):
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password

    def connect(self, with_key=None):
        """
        connect host
        :return:
        """
        if with_key is None:
            self.ssh_client.connect(hostname=self.hostname, port=self.port,
                                    username=self.username, password=self.password)
        else:
            key_file = Utils.add_path(Utils.get_root_path(), Utils.add_path("devices", "robot_key"))
            key = paramiko.RSAKey.from_private_key_file(key_file)
            self.ssh_client.connect(hostname=self.hostname, port=self.port,
                                    username=self.username, pkey=key)

    def exec_command(self, cmd: str, buffer_size=-1, with_read=False):
        """
        使用exec_command方法执行命令，并使用变量接收命令的返回值并用print输出
        """
        stdin, stdout, stderr = self.ssh_client.exec_command(cmd, bufsize=buffer_size)
        # 获取命令结果
        if with_read:
            err = stderr.read()
            result = stdout.read()
            return result.decode('utf-8'), err.decode('utf-8')
        else:
            return None

    def close(self):
        self.ssh_client.close()


if __name__ == '__main__':
    pass
    # test_cmd = "cd /opt/opentrons-robot-server/ && nohup python3 -m hardware_testing.scripts.force_pick_up_test --cycles 10000 --speed 10 --current 0.55 > /data/testing_data/z_life_time.txt &"
    # # test_cmd = "cd /opt/opentrons-robot-server/ && python3 -m hardware_testing.scripts.force_pick_up_test --cycles 10000 --speed 10 --current 0.55"
    # command = "df -h"
    # client = SSHClient('192.168.6.8')
    # client.connect(with_key=True)
    # res = client.exec_command(command)
    # print(res)
    # res = client.exec_command(test_cmd)
    # import time
    #
    # time.sleep(5)
    # client.close()
