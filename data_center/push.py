import os
import argparse
from src.settings import settings
from src.services.download_report_handler import ParamikoDriver

SERVER_IP_ADDRESS = settings.server_ip
SERVER_USER_NAME = "root"
SERVER_PASSWORD = "root"
REMOTE_PROJECT_PATH = '/opt/data-center-server'


class UploadScripts:
    def __init__(self):
        self.ssh_client: ParamikoDriver = ParamikoDriver(SERVER_IP_ADDRESS, SERVER_USER_NAME, SERVER_PASSWORD)
        self.sftp = self.ssh_client.sftp
        self.ssh = self.ssh_client.ssh

    def remove_remote_files(self, path_name):
        """
        递归删除远程目录内容
        """
        try:
            # 先尝试列出目录内容
            for item in self.sftp.listdir(path_name):
                item_path = os.path.join(path_name, item).replace('\\', '/')
                try:
                    # 尝试获取文件属性来判断是文件还是目录
                    attrs = self.sftp.stat(item_path)
                    if attrs.st_mode & 0o40000:  # 如果是目录
                        self.remove_remote_files(item_path)
                        self.sftp.rmdir(item_path)
                        print(f"Removed directory: {item_path}")
                    else:  # 如果是文件
                        self.sftp.remove(item_path)
                        print(f"Removed file: {item_path}")
                except IOError as e:
                    print(f"Error removing {item_path}: {e}")
        except IOError as e:
            print(f"Error accessing {path_name}: {e}")

    def sftp_mkdir_p(self, remote_path):
        """模拟 mkdir -p 功能，递归创建目录"""
        # 处理绝对路径
        if remote_path.startswith('/'):
            current_path = '/'
        else:
            current_path = ''

        dirs = [d for d in remote_path.split('/') if d]  # 过滤空字符串

        for dir_name in dirs:
            current_path = os.path.join(current_path, dir_name).replace('\\', '/')
            try:
                self.sftp.stat(current_path)
            except IOError:
                self.sftp.mkdir(current_path)
                print(f"Created remote directory: {current_path}")

    def upload_files(self, remote_base_path, local_pathname):
        """
        递归上传文件夹内容
        """
        # 确保本地路径存在
        if not os.path.exists(local_pathname):
            print(f"Local path does not exist: {local_pathname}")
            return

        # 计算远程路径
        relative_path = os.path.relpath(local_pathname, '.')
        remote_path = os.path.join(remote_base_path, relative_path).replace('\\', '/')

        # 确保远程目录存在
        try:
            self.sftp.stat(remote_path)
        except IOError:
            self.sftp_mkdir_p(remote_path)

        print(f"Uploading from {local_pathname} to {remote_path}")

        # 遍历本地目录
        for item in os.listdir(local_pathname):
            local_item_path = os.path.join(local_pathname, item)
            remote_item_path = os.path.join(remote_path, item).replace('\\', '/')

            if os.path.isdir(local_item_path):
                # 如果是目录，递归上传
                self.upload_files(remote_base_path, local_item_path)
            else:
                # 如果是文件，直接上传
                try:
                    print(f"Uploading file: {local_item_path} -> {remote_item_path}")
                    self.sftp.put(local_item_path, remote_item_path)
                except Exception as e:
                    print(f"Error uploading {local_item_path}: {e}")

    def upload_local(self):
        """上传本地文件到服务器"""
        print("Cleaning remote directory...")
        self.remove_remote_files(REMOTE_PROJECT_PATH)

        print("\nUploading files...")
        # 上传整个src目录
        self.upload_files(REMOTE_PROJECT_PATH, './src')

        # 如果需要上传其他特定目录，可以取消注释下面的行
        # self.upload_files(REMOTE_PROJECT_PATH, './src/services/download_report_handler')
        # self.upload_files(REMOTE_PROJECT_PATH, './src/services/google_driver_handler')

    def restart_server(self):
        """
        重启data-center server
        """
        print("\nRestarting data-center server...")
        try:
            commands = [
                'systemctl daemon-reload',
                'systemctl restart data-center.service',
                'systemctl status data-center.service --no-pager'
            ]

            for cmd in commands:
                stdin, stdout, stderr = self.ssh.exec_command(cmd)
                print(f"\n>>> {cmd}")

                # 读取输出
                output = stdout.read().decode('utf-8')
                error = stderr.read().decode('utf-8')

                if output:
                    print(f"Output: {output}")
                if error:
                    print(f"Error: {error}")

        except Exception as e:
            print(f"Error restarting server: {e}")


if __name__ == '__main__':
    # 创建解析器对象
    parser = argparse.ArgumentParser(description='Upload files to server')
    parser.add_argument('--host', type=str, required=False, help='Server hostname or IP address')
    args = parser.parse_args()

    # 使用指定的host或默认设置
    if args.host:
        SERVER_IP_ADDRESS = args.host
        print(f"Using specified host: {SERVER_IP_ADDRESS}")
    else:
        SERVER_IP_ADDRESS = settings.server_ip
        print(f"Using default host from settings: {SERVER_IP_ADDRESS}")

    try:
        cli = UploadScripts()
        cli.upload_local()
        cli.restart_server()
        print("\nUpload and restart completed successfully!")
    except Exception as e:
        print(f"Error: {e}")