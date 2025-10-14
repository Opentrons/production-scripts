from tools.scp_files_to_robot.basic import FlexConnector
from typing import Tuple
import paramiko
import time


class RunScripts(FlexConnector):
    def __init__(self, host_name):
        super(RunScripts, self).__init__(host_name)
        self.connected = self.connect()

    def execute_remote_command(self, command: str, get_pty: bool = False) -> Tuple[int, str, str]:
        """
        执行远程命令

        Args:
            ssh_client: SSH客户端对象
            command: 要执行的命令
            get_pty: 是否获取伪终端（用于交互式命令）

        Returns:
            tuple: (退出状态码, 标准输出, 标准错误)
        """
        try:
            stdin, stdout, stderr = self.ssh.exec_command(
                command,
                get_pty=get_pty,
                timeout=60  # 命令执行超时时间
            )

            # 等待命令执行完成
            exit_status = stdout.channel.recv_exit_status()

            # 读取输出
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()

            return exit_status, output, error

        except paramiko.SSHException as e:
            return -1, "", f"SSH执行错误: {e}"
        except Exception as e:
            return -1, "", f"执行错误: {e}"

    def run_command(self, _command):
        if self.connected:
            try:
                print(f"🔍 执行命令 {_command}")
                stdin, stdout, stderr = self.ssh.exec_command(_command)

                # 等待命令完成
                exit_status = stdout.channel.recv_exit_status()
                output = stdout.read().decode('utf-8').strip()
                error = stderr.read().decode('utf-8').strip()

                print(f"退出状态: {exit_status}")
                print(f"输出: {output}")
                print(f"错误: {error}")

                return exit_status == 0

            except Exception as e:
                print(f"❌ 测试执行异常: {e}")
                return False

        else:
            return False

    def execute_with_nohup_detached(self, command):
        """使用nohup并确保完全脱离"""
        ssh_client = self.ssh
        try:
            # 创建完整的脱离命令
            nohup_cmd = f"nohup {command} > /dev/null 2>&1 &"
            print(f"📝 执行: {nohup_cmd}")

            # stdin, stdout, stderr = ssh_client.exec_command(nohup_cmd)
            # exit_status = stdout.channel.recv_exit_status()
            # error = stderr.read().decode('utf-8').strip()

            channel = ssh_client.invoke_shell()
            channel.send(nohup_cmd)

            exit_status = 0

            if exit_status == 0:
                print("✅ 进程已使用nohup, 等待 5s 让进程启动...")

                # 等待并检查进程
                import time
                time.sleep(5)
                channel.send("exit\n")

                check_cmd = f"ps aux | grep 'python3.*hardware_testing' | grep -v grep | head -5"
                stdin, stdout, stderr = ssh_client.exec_command(check_cmd)
                processes = stdout.read().decode('utf-8').strip()

                if processes:
                    print(f"📊 运行中的进程:\n{processes}")
                    return True
                else:
                    print("⚠️  未找到运行中的进程")
                    return False
            else:
                print(f"❌ nohup执行失败: ")
                return False

        except Exception as e:
            print(f"❌ nohup执行异常: {e}")
            return False

    def release(self):
        self.ssh.close()


if __name__ == '__main__':
    command1 = "rm -rf /data/testing_data/finished_number.json"
    command2 = "cat /data/testing_data/finished_plunger.json"
    # script = "python3 -m hardware_testing.scripts.tip_pick_up"
    script = "python3 -m hardware_testing.scripts.plunger_lifetime --trials 450000"
    # robot_list = ['192.168.31.129', '192.168.31.28', '192.168.31.243','192.168.31.144', '192.168.31.16', '192.168.31.230',
    #               '192.168.31.87', '192.168.31.32', '192.168.31.103', '192.168.31.101',  '192.168.31.103',]
    robot_list = [
        '192.168.31.28', '192.168.31.129', '192.168.31.16',  '192.168.31.32',  '192.168.31.103'
    ]

    robot_list2 = ['192.168.31.101', '192.168.31.103']
    for robot_name in robot_list:
        run_scripts = RunScripts(robot_name)
        if run_scripts.connected:
            print(f'Robot {robot_name} is connected')
            run_scripts.run_command(command2)
            # run_scripts.execute_with_nohup_detached(script)
            run_scripts.release()
        else:
            print(f'Robot {robot_name} is not connected')
