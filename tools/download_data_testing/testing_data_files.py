import os
import paramiko
import stat
from tqdm import tqdm  # 进度条库
from PyInquirer import prompt
from prompt_toolkit.shortcuts import prompt as pt
import time
import base64
import io

timestamp = time.time()
local_time = time.localtime(timestamp)
formatted_time = time.strftime("%Y-%m-%d-%H-%M-%S", local_time)

LOAD_KEY_BY_STR = True

key_str = """
LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0NCmIzQmxibk56YUMxclpYa3RkakVBQUFBQUJHNXZibVVBQUFBRWJtOXVaUUFBQUFBQUFBQUJBQUFDRndBQUFBZHpjMmd0Y24NCk5oQUFBQUF3RUFBUUFBQWdFQTBxTm9kUHkzNERQY0NSYW5BcnlxaUJiMEtDbzBhTHlVM1dTZzRWMVQ4WWJ2MVU4Smg3Y2INCjNySHY3a3hDMXdSYlFhUS9Db0tEeVZmbVRXbVZNUnlralp5Y08wSmx4SWFyNjNKc3JHc0g5WjVTT3hhcHVnTVp2UC80L0gNCnV6YVdMcjdRZW1Nd2ZNZjY2NGtpaWtESkdYa1RBNnc1bExwVFZCZDROand4ejJKa3FSaU1sb2lla1p1TTEybThQTWlZN3UNCmQrN2IvRy9kVzVSNEFmZW96MGdGNjZiYUF3Wnc1RURWNTZ5WWZiS3BacnlJeEVMT0VlMFhpVThGRnhWV1kvWXpqbTRiakcNCnQrNHEzb25yOEszaWJuUjArQi80ZGhwMDdUUnBjNGJhYXlXd25jL0hCSGcxeHRDN1JEeWx3RmhrY2t4VTdDUkxTWmNHczgNCmRVR0lTMFhVSkZMVDZ3S1lLTGJiYzA2NmcydFBKNXRDVXdWUmY4THNPc3NqR1FEOE9qOC9FTGFyT2RWMURDaDhvNVVURmoNCjZ6NGV3ZFdTMndRVXl6TTlaVW1pOTY4RnB6TmYzbXJ5dllQeGYxVndxV2pvRldoanNiK3BBUUYwcEpEV2svM3BZNFgyOG4NCklabU9CU0QzSS9PdGdTWnFEK3RubnFuZzBhU0dqSnNwSnFkV0tTUEM3cFJ0QzBVU3dNRDEyNHlITm9yaUZRQXdoMDMxaGsNCmFZbXloU3NQVjlDRTM1dFVHL3V4RzZqcTVwaEF2YkwyZkV4aG5BN0tRZHZSTE9kNUJwZWNEbGsrcWlEYzFKL2xVT252MUENCnFrMG9yaU4vSkdiMi81cGwvUHBDNDRqUEduZnhTS2V2ZFpYQmdXNUlmdUNMMFdNUTMrSXZNeXJ5Mnlmd0pQdDJWbFpIRzUNCjhBQUFkWVc3azltMXU1UFpzQUFBQUhjM05vTFhKellRQUFBZ0VBMHFOb2RQeTM0RFBjQ1JhbkFyeXFpQmIwS0NvMGFMeVUNCjNXU2c0VjFUOFlidjFVOEpoN2NiM3JIdjdreEMxd1JiUWFRL0NvS0R5VmZtVFdtVk1SeWtqWnljTzBKbHhJYXI2M0pzckcNCnNIOVo1U094YXB1Z01adlAvNC9IdXphV0xyN1FlbU13Zk1mNjY0a2lpa0RKR1hrVEE2dzVsTHBUVkJkNE5qd3h6MkprcVINCmlNbG9pZWtadU0xMm04UE1pWTd1ZCs3Yi9HL2RXNVI0QWZlb3owZ0Y2NmJhQXdadzVFRFY1NnlZZmJLcFpyeUl4RUxPRWUNCjBYaVU4RkZ4VldZL1l6am00YmpHdCs0cTNvbnI4SzNpYm5SMCtCLzRkaHAwN1RScGM0YmFheVd3bmMvSEJIZzF4dEM3UkQNCnlsd0Zoa2NreFU3Q1JMU1pjR3M4ZFVHSVMwWFVKRkxUNndLWUtMYmJjMDY2ZzJ0UEo1dENVd1ZSZjhMc09zc2pHUUQ4T2oNCjgvRUxhck9kVjFEQ2g4bzVVVEZqNno0ZXdkV1Myd1FVeXpNOVpVbWk5NjhGcHpOZjNtcnl2WVB4ZjFWd3FXam9GV2hqc2INCitwQVFGMHBKRFdrLzNwWTRYMjhuSVptT0JTRDNJL090Z1NacUQrdG5ucW5nMGFTR2pKc3BKcWRXS1NQQzdwUnRDMFVTd00NCkQxMjR5SE5vcmlGUUF3aDAzMWhrYVlteWhTc1BWOUNFMzV0VUcvdXhHNmpxNXBoQXZiTDJmRXhobkE3S1FkdlJMT2Q1QnANCmVjRGxrK3FpRGMxSi9sVU9udjFBcWswb3JpTi9KR2IyLzVwbC9QcEM0NGpQR25meFNLZXZkWlhCZ1c1SWZ1Q0wwV01RMysNCkl2TXlyeTJ5ZndKUHQyVmxaSEc1OEFBQUFEQVFBQkFBQUNBRXlBSUozc2N2T3dvZ2VDL0tFWDJHK1l0cEFuMCtUK0tLckgNCnMwNW1VT2gxYzRGck5URGZKZllaZGVSOE9nSlJpTHNzWmVEeFNkL0VWdFppdEZhajZuZXNHMm5DVWFld3FadlhjUFNsNHINCndvQmdHRDE1ekJKNFhuQ1l6WmVHMmNDY2VLY2FneSt1aWNrbGd5L25HNkp1d0tNaTE3N1dkUkVqZlB0bG5VbU9tTFI1UUENCllrRkVNWjFXc2U4Y2k1cWlHS1hpVUc4OFNZN0xPMUtybWRtK2RMZ0RYMGFkL2o1SDllZ3dYU201eTZDT2RMV2k5YWk1RFUNClZITjdnTWZkWE1ReWxGZ0NmZG1yWEZKNmtRQldodGhLMzNpR1UvekEyeHFUWUlFZXh4RUhIVUFUaUZwdE5rckE0R0tHREUNClR4VlhuVmt6bzRiRWVMM0ZsSzJaWVdERk9haFdYZzJ6c2R3UzhMbGdFTmdNclBXQkgyQ2pFVE11ZEMrdCtlMjJHS0EyR3ANCjRwT3A1a3laSFBubC9MU0pGbFdyNTVhVXBPbzViUVRydVkvdTRKOGYzcndER09hQ2FCT2NBNDZFd3czQlZXeHU2Q0UrNSsNCnltOXlyaktYdG1Vd1VPYkR1NUxZZmRTUDdTSnJ2WWN3MTY0SytZZjZ1Nk5uazBlSmVpNlJTdE1ISmxYMStaWWNzZGtJVjcNClRrd3FPVHBjbkZLd0NHRkRxc0xhR0RPeFdVdFI0RldHRjNDWjZzcUxmWUw3ZU5BYVFQZlVxU1A4MjRGVitaNGFzZXM1Z1QNCmhTUlBvVXVLQUFkSUlyMGlwd1JUdXhCSmtIcmh2RFBCVlQyMTdNN09aR0V1WlFqSDlMbityVUlMQUVhY1R4ZUJ4NVlqOFANCm1BZ0FOTnhiN3hLbmQ1K0k5eEFBQUJBRnhLNjVKeHUycGdyUnRRKzN3YmNmL21ZM2hHaFRHVHZqanNtVm4zVlpSOXAyeUgNCmxSYWJiRkZhLzlsMTVTTWNMT3JBeldNKzZuNUZPdllCLzdyeC8vYUpLRUozUENhZS9VTGNETVFxdDZTQ0tvbGNuODhuYVQNCnIvM2lwaldIUzA2dXRHR0NmV2UxQlhGT21xc3Q2eXEwd3NPWms3by9ScXBZUFJUdGoraUp5QmZqTmJGNnJYMklsVVExRGwNCmVQKzlUZjBwSjFBQk1BMElTUk9SRFphWTFyQUlyZHhSUFVOdGp4cWFDR2x4eUg2cG1nVlIvZjdqbFg2Ny85NndOMncxeFoNCkVtR3MyUkdZcmVnWko1dUlrd3ZmalVvVzZBZnhvNXJOMUMzMEZDbFVQcjB0SEdEdFJQTzhsZDdFaEJHUXJFNkJLa2h3bXgNCituWXJyZlk1UkViT1ZIVUFBQUVCQVB1RDBtT1VnMlNHM1VzRlhyTzZpSnkwYnRPQ2JLc3p3bFlGN3NoemwrV3BqMGpUcE8NCjZwQ3dQRXNIVkdSZFA0S2hzK2hlM3JqZENJUENFQlQ0SXlpY0ROMVJBSk9mWVd0cWJSYmF0bnJYaFpyNTExMlFsKzZwZ2INClZGMkw5VkczWExBWFUzSzI5TVB2QkNkSHhoMDhoR015QVAxWFdXQzVMWUpXTjZtaWplSGJuZ0k0SWdPKzVkcVFJMFI2eWYNCnRRQ0JmM01KOFBwMC8vWFJlN05kd09SSXFjdnJ5c2dpR0phUHpOL3k5M1hUUlJrR2Nuemo0REg4V2o4eUpOS3RjTzlxb1INClF5R3JCRUVCaFlTV0NDTXlXaFE1ZkhIWFNFc05ndlRKN2RPdDRpWUgzVjJCRGNEUmg2a0FHYzhJWXJWQ2lXOXhET21ySjENCmplMDloTEZTMXM1NnNBQUFFQkFOWmsrMytNZFBwdHdBOUJyQmI0Vjl0MTdsSkZPeEE5MjRqU2NKVVhUOTZrRU1kWEZJZ1ENClVQcU9McHJ5Q3NGS2pUT0xBQ29XS3h1UlZxanQ4WFpTaUtlUDhKZmp1cXpReE1CTFgwS1NJTEtqOFNDMW9sTVU3UGdTTE8NCkhnQ3FxTTJmK0JJN01QekU1TTAzSjdtTm5veVhualNLa1Q3dTFIU0YrWTlpTmxJYk5BTlBnc09FaG5zT01wcTMrK3VUTmgNCnp0YVRxbTlDeWgxc0hibU5lRGdaZlBIU2Q3M1BGRTFub1BEZ0hxZkMvckhWTzlyTU9vN0U1YmI4VFNTMVExOGxKdW03RWINCi9wQzlndnQ5eWxwMmVOM3luSllpY1U4ZE1HSk1MMG5oVEdpUG9sT2wwU3MwRkxtcHFsSEVxRkxUdlVmWnBhaWZhVUM5clkNCklqRG1NcTJZVjkwQUFBQWRZbkpoZVdGdVlXeHRiMjUwWlVCWFV5MURNREpJUkRCWVdsRXdOVTRCQWdNRUJRWT0NCi0tLS0tRU5EIE9QRU5TU0ggUFJJVkFURSBLRVktLS0tLQ0K
"""

def get_downloads(files):
    question_download = {
        'type': 'list',
        'name': 'files',
        'message': '选择下载文件:',
        'choices': files
    }
    return question_download


class LinuxFileManager:
    def __init__(self, host, username, password=None, port=22):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.ssh = None
        self.sftp = None

    def connect(self, timeout=10):
        """建立 SSH 和 SFTP 连接"""
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if not self.password:
                # self.password = input(f"Enter SSH password for {self.username}@{self.host} (默认回车无密码) :")
                self.password = self.password if self.password is not "" else "None"
            self.ssh.connect(self.host, port=self.port, username=self.username, password=self.password, timeout=timeout)
            self.sftp = self.ssh.open_sftp()
            print("✅ SSH 连接成功！")
        except Exception as e:
            if "publickey" in str(e):
                try:
                    print("ssh with publickey...")
                    if LOAD_KEY_BY_STR:
                        key_data = base64.b64decode(key_str.strip())
                        key = paramiko.RSAKey.from_private_key(io.StringIO(key_data.decode("utf-8")))
                    else:
                        key_file = os.path.join(os.getcwd(), 'robot_key').replace('\\', '/')
                        print(f'key path: {key_file}')
                        key = paramiko.RSAKey.from_private_key_file(key_file)

                    self.ssh.connect(self.host, port=self.port, username=self.username, password=self.password,
                                     timeout=timeout, pkey=key)
                    self.sftp = self.ssh.open_sftp()
                    print("✅ SSH 连接成功！")
                except Exception as e:
                    print(f"❌ SSH 密钥连接失败: \n")
                    input("\n🚗 任意键退出...")
                    raise
            else:
                print(f"❌ SSH 连接失败: \n")
                input("\n🚗 任意键退出...")
                raise

    def list_files(self, remote_dir, show=True):
        """列出远程目录的文件"""
        try:
            files = self.sftp.listdir(remote_dir)
            print(f"📂 远程目录 {remote_dir} 下的文件：")
            if show:
                for file in files:
                    print(f" - {file}")
            return files
        except Exception as e:
            print(f"❌ 无法列出文件: {e}")
            return []

    def download_file(self, remote_path, local_path):
        """下载远程文件到本地"""
        try:
            self.sftp.get(remote_path, local_path)
            print(f"⬇️ 下载成功: {remote_path} → {local_path}")
        except Exception as e:
            print(f"❌ 下载失败: {e}")

    def _is_dir(self, remote_path):
        """检查远程路径是否是目录"""
        try:
            return stat.S_ISDIR(self.sftp.stat(remote_path).st_mode)
        except IOError:
            return False

    def _download_file_with_progress(self, remote_path, local_path):
        try:
            file_size = self.sftp.stat(remote_path).st_size
            with tqdm(
                    total=file_size,
                    unit='B',
                    unit_scale=True,
                    desc=os.path.basename(remote_path),
                    leave=False
            ) as pbar:
                def progress_callback(transferred, total):
                    pbar.update(transferred - pbar.n)  # 更新增量

                self.sftp.get(remote_path, local_path, callback=progress_callback)
            print(f"⬇️ 下载成功: {remote_path} → {local_path}")
        except Exception as e:
            print(f"❌ 下载失败: {e}")

    def download_dir(self, remote_dir, local_dir):
        """
        递归下载远程目录所有文件
        :param remote_dir: 远程目录路径 (e.g. '/home/user/data')
        :param local_dir: 本地存储路径 (e.g. 'C:/Downloads/data')
        """
        files = self.sftp.listdir(remote_dir)
        if len(files) == 0:
            print("\n🤔 文件夹目录为空, 下载跳出...\n")
            return
        try:
            os.makedirs(local_dir, exist_ok=True)
        except Exception as e:
            print(e)

        for item in files:
            remote_path = os.path.join(remote_dir, item).replace('\\', '/')
            local_path = os.path.join(local_dir, item)

            if self._is_dir(remote_path):
                self.download_dir(remote_path, local_path)  # 递归处理子目录
            else:
                self._download_file_with_progress(remote_path, local_path)

    def delete_file(self, remote_path):
        """删除远程文件"""
        try:
            self.sftp.remove(remote_path)
            print(f"🗑️ 删除成功: {remote_path}")
        except Exception as e:
            print(f"❌ 删除失败: {e}")

    def delete_dir(self, remote_dir):
        files = self.sftp.listdir(remote_dir)
        if len(files) == 0:
            print("\n🤔 文件夹目录为空, 删除跳出...\n")
            return

        for item in self.sftp.listdir(remote_dir):
            remote_path = os.path.join(remote_dir, item).replace('\\', '/')
            if self._is_dir(remote_path):
                self.delete_dir(remote_path)  # 递归处理子目录
            else:
                self.delete_file(remote_path)
                # 删除空目录
                files = self.sftp.listdir(remote_dir)
                if len(files) == 0:
                    try:
                        self.sftp.rmdir(remote_dir)
                        print(f"🗑️ 删除成功: {remote_dir}")
                    except Exception as e:
                        print(f"❌ 删除失败: {e}")
                else:
                    pass

    def close(self):
        """关闭连接"""
        if self.sftp:
            self.sftp.close()
        if self.ssh:
            self.ssh.close()
        print("\n🔌 连接已关闭")


def main():
    # 配置 SSH 连接
    host = pt(
        "请输入IP地址: ",
        default="192.168.6.15"  # 可编辑的默认值
    )
    username = pt(
        "请输入ssh 用户名: ",
        default="root"  # 可编辑的默认值
    )
    # 初始化管理器
    manager = LinuxFileManager(host, username)
    manager.connect()

    # 操作远程文件
    remote_dir = pt(
        "请输入远程目录: ",
        default="/data/testing_data"  # 可编辑的默认值
    )

    files = manager.list_files(remote_dir, show=False)
    if len(files) is not 0:
        # 选择要下载的文件
        question_files = get_downloads(files)
        answer = prompt(question_files)['files']

        remote_path = os.path.join(remote_dir, answer).replace('\\', '/')
        local_path = os.path.join(os.getcwd(), answer)

        if input("是否下载远程文件？(y/n): ").lower() == "y":
            timestamp = time.time()
            local_time = time.localtime(timestamp)
            formatted_time = time.strftime("%Y-%m-%d-%H-%M-%S", local_time)
            manager.download_dir(remote_path, local_path + '-' + formatted_time)

        # 是否删除远程文件
        if input("是否删除远程文件？(y/n): ").lower() == "y":
            manager.delete_dir(remote_path)
            manager.list_files(remote_path)
    else:
        print("\n🤔 文件夹目录为空...\n")

    # 关闭连接

    manager.close()
    input("\n🚗 任意键退出...")


if __name__ == "__main__":
    # main()
    LinuxFileManager("192.168.6.55", 'root').connect()