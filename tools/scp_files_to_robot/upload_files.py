
import time
import subprocess

file_name = "C:\\Users\\22192\\Desktop\\ssh-flex\\plunger_lifetime.py"
key_name = "C:\\Users\\22192\\Desktop\\ssh-flex\\robot_key"
ot3_target_path = "/opt/opentrons-robot-server/hardware_testing/scripts"

from tools.scp_files_to_robot.run_scripts import RunScripts


command3 = "mount -o remount ,rw /"
robot_list = [
        '192.168.31.28','192.168.31.144','192.168.31.243', '192.168.31.129',  '192.168.31.32', '192.168.31.101',
        '192.168.31.230','192.168.31.87', '192.168.31.32', '192.168.31.103']
for ip in robot_list:
    run_script = RunScripts(ip)
    run_script.run_command(command3)
    time.sleep(1)
    _cmd = f"scp -i {key_name} -r {file_name} root@{ip}:{ot3_target_path}"
    print(f"running {ip}...")
    print(_cmd)
    result = subprocess.run(
        _cmd,
        shell=True,
        capture_output=True,  # 捕获标准输出和标准错误
        text=True,  # 以文本形式返回结果
        timeout=30  # 设置超时时间（秒）
    )

    time.sleep(1)

    # 打印命令执行结果
    print(f"返回码: {result.returncode}")
    print(f"标准输出: {result.stdout}")
    print(f"标准错误: {result.stderr}")