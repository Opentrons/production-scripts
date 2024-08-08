import os.path

import paramiko
from utils import Utils


class SSHClient:
    def __init__(self, hostname: str, port=22, username="root", password="None"):
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.channel = None

    def connect(self, with_key=None):
        """
        connect host
        :return:
        """
        if with_key is None:
            self.ssh_client.connect(hostname=self.hostname, port=self.port,
                                    username=self.username, password=self.password)
            self.channel = self.ssh_client.invoke_shell()
        else:
            abs_dir = os.path.dirname(os.path.abspath(__file__))
            key_file = os.path.join(abs_dir, 'robot_key')
            key = paramiko.RSAKey.from_private_key_file(key_file)
            self.ssh_client.connect(hostname=self.hostname, port=self.port,
                                    username=self.username, pkey=key)
            self.channel = self.ssh_client.invoke_shell()

    def exec_command(self, cmd: str, buffer_size=-1, with_read=False):
        """
        使用exec_command方法执行命令,并使用变量接收命令的返回值并用print输出
        """
        stdin, stdout, stderr = self.ssh_client.exec_command(cmd, bufsize=buffer_size)
        # 获取命令结果
        if with_read:
            err = stderr.read()
            result = stdout.read()
            return result.decode('utf-8'), err.decode('utf-8')
        else:
            return None

    def exec_shell(self, cmd: str, stop_string: str):
        """
        exec shell
        :param cmd:
        :param stop_string:
        :return:
        """
        if self.channel is None:
            raise ValueError("current channel is none")
        self.channel.send(cmd)
        output_line = ""
        while True:
            result = self.channel.recv(1).decode()
            output_line = output_line + result
            if '\n' in result:
                print(output_line)
                output_line = ""
            if output_line.find(stop_string) != -1:
                break


    def scp_files(self, file_path: str, save_path: str, use_key=False, user_name="root"):
        """
        down files
        :param file_path:
        :param save_path:
        :param use_key:
        :param user_name:
        :return:
        """
        if not use_key:

            self.exec_shell(f'scp -r {user_name}@{self.hostname}:{file_path} {save_path}', 'close - IO')
        else:
            pass

    def close(self):
        self.ssh_client.close()


if __name__ == '__main__':
    client = SSHClient('192.168.6.46')
    client.connect(with_key=None)
    client.scp_files('/data/testing_data', './')

