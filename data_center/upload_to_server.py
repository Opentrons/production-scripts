import paramiko
import os


class Cli:
    def __init__(self, ip, username='root', password='root'):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(ip, port=22, username=username, password=password, timeout=10)
        self.sftp = self.ssh.open_sftp()

    def remove_remote_files(self, path_name='/opt/data-center-server'):
        """
        remove server
        """
        for item in self.sftp.listdir(path_name):
            item_path = path_name + '/' + item
            try:
                # 如果是文件，直接删除
                self.sftp.remove(item_path)
            except IOError:
                # 如果是文件夹，递归删除
                self.remove_remote_files(item_path)
                self.sftp.rmdir(item_path)

    def sftp_mkdir_p(self, remote_path):
        """模拟 mkdir -p 功能，递归创建目录"""
        dirs = remote_path.split('/')
        current_path = ''

        for dir in dirs:
            if not dir:  # 跳过空路径（如开头的/）
                continue
            current_path += '/' + dir
            try:
                self.sftp.stat(current_path)  # 检查目录是否存在
            except IOError:  # 目录不存在
                self.sftp.mkdir(current_path)  # 创建目录

    def upload_files(self, remote_path='/opt/data-center-server', local_pathname='./files_server'):
        """
           递归上传文件夹内容
           """
        # 确保远程目录存在
        remote_item_path = remote_path + local_pathname.replace('./', '/')
        try:
            self.sftp.stat(remote_item_path)
        except IOError:
            print(f'mkdir: {remote_item_path}')
            self.sftp_mkdir_p(remote_item_path)

        # 遍历本地目录
        for item in os.listdir(local_pathname):
            local_item_path = os.path.join(local_pathname, item)
            if '\\' in local_item_path:
                local_item_path = local_item_path.replace('\\', '/')
            if os.path.isdir(local_item_path):
                # 如果是目录，递归上传
                remote_item_path = remote_path + local_item_path.replace('./', '/')
                self.upload_files(remote_path, local_item_path)
            else:
                # 如果是文件，直接上传
                remote_item_path = remote_path + local_item_path.replace('./', '/')
                print(f'upload: {remote_item_path}')
                self.sftp.put(local_item_path, remote_item_path)


if __name__ == '__main__':
    cli = Cli('192.168.0.28')
    cli.remove_remote_files()
    cli.upload_files()
    cli.upload_files(local_pathname='./download_report_handler')
    cli.upload_files(local_pathname='./google_driver_handler')
