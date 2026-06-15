import os
import sys
addpathpat = os.path.dirname(__file__)
addpath = os.path.dirname(os.path.dirname(__file__))
addpath2 = os.path.dirname(addpath)
if addpath not in sys.path:
    sys.path.append(addpath)
if addpath2 not in sys.path:
    sys.path.append(addpath2)
if addpathpat not in sys.path:
    sys.path.append(addpathpat)
from drivers.ssh import SSHClient
import time
from drivers.play_sound import play_alarm_2
from tools.inquirer import prompt_ip, prompt_connect_method
import os

def get_cycles(client: SSHClient, device_name):
    current_path = os.getcwd()
    client.connect(key_path=current_path)
    channel = client.channel
    remote_dir = "/data/testing_data"
    # 获取按时间排序的最新CSV文件
    file_list = sorted(
        [f for f in channel.listdir(remote_dir) if f.endswith('.report')],
        key=lambda x: channel.stat(f"{remote_dir}/{x}").st_mtime,
        reverse=True
    )
    latest_file = file_list
    remote_path = f"{remote_dir}/{latest_file}"
    print(f"正在监控文件: {latest_file}")

    # 持续监控文件变化
    channel = channel.invoke_shell()
    channel.send(f"tail -n 0 -f {remote_path} \n")  # 从当前位置开始追踪

def test_run():
    ip = prompt_ip()
    use_key: str = prompt_connect_method()
    if "Y" in use_key.strip().upper():
        client = SSHClient(ip)
    else:
        client = SSHClient(ip, use_key=False)
    get_cycles(client, ip)
if __name__ == '__main__':
    pass