from ..download_report_handler import ParamikoDriver
import time


class FlexCommunication:
    def __init__(self, client: ParamikoDriver):
        self.sshClient = client

    def update_date(self, your_time):
        command = f'date -s "{your_time}"'
        # 执行命令
        stdin, stdout, stderr = self.sshClient.ssh.exec_command(command, get_pty=True)
        time.sleep(0.1)
        return stdout.read().decode("utf-8")

    def run_script(self, script):
        stdin, stdout, stderr = self.sshClient.ssh.exec_command(script, get_pty=True)
        time.sleep(0.1)
        return stdout.read().decode("utf-8")
