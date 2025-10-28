import os
import paramiko
import stat
import time
import base64
import io
from typing import Callable, Optional
from files_server.utils.utils import zip_directory, delete_folder
from files_server.api.api_files import check_system_dir_call_back
from files_server.database.read_data_base import MongoDBReader
from dataclasses import dataclass
from datetime import datetime, date
from download_report_handler.discover_flex import scan_flex
from download_report_handler.testing_data_ana import Ana, TEST_NAME_SETTING
from google_driver_handler.main_updata import updata_class as UploadData
from google_driver_handler.main_updata import Productions

from files_server.database.read_data_base import MongoDBReader
from threading import Thread
from typing import Any, Tuple


def get_time_str():
    timestamp = time.time()
    local_time = time.localtime(timestamp)
    formatted_time = time.strftime("%Y-%m-%d-%H-%M-%S", local_time)
    return formatted_time


LOAD_KEY_BY_STR = True

key_str = """
LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0NCmIzQmxibk56YUMxclpYa3RkakVBQUFBQUJHNXZibVVBQUFBRWJtOXVaUUFBQUFBQUFBQUJBQUFDRndBQUFBZHpjMmd0Y24NCk5oQUFBQUF3RUFBUUFBQWdFQTBxTm9kUHkzNERQY0NSYW5BcnlxaUJiMEtDbzBhTHlVM1dTZzRWMVQ4WWJ2MVU4Smg3Y2INCjNySHY3a3hDMXdSYlFhUS9Db0tEeVZmbVRXbVZNUnlralp5Y08wSmx4SWFyNjNKc3JHc0g5WjVTT3hhcHVnTVp2UC80L0gNCnV6YVdMcjdRZW1Nd2ZNZjY2NGtpaWtESkdYa1RBNnc1bExwVFZCZDROand4ejJKa3FSaU1sb2lla1p1TTEybThQTWlZN3UNCmQrN2IvRy9kVzVSNEFmZW96MGdGNjZiYUF3Wnc1RURWNTZ5WWZiS3BacnlJeEVMT0VlMFhpVThGRnhWV1kvWXpqbTRiakcNCnQrNHEzb25yOEszaWJuUjArQi80ZGhwMDdUUnBjNGJhYXlXd25jL0hCSGcxeHRDN1JEeWx3RmhrY2t4VTdDUkxTWmNHczgNCmRVR0lTMFhVSkZMVDZ3S1lLTGJiYzA2NmcydFBKNXRDVXdWUmY4THNPc3NqR1FEOE9qOC9FTGFyT2RWMURDaDhvNVVURmoNCjZ6NGV3ZFdTMndRVXl6TTlaVW1pOTY4RnB6TmYzbXJ5dllQeGYxVndxV2pvRldoanNiK3BBUUYwcEpEV2svM3BZNFgyOG4NCklabU9CU0QzSS9PdGdTWnFEK3RubnFuZzBhU0dqSnNwSnFkV0tTUEM3cFJ0QzBVU3dNRDEyNHlITm9yaUZRQXdoMDMxaGsNCmFZbXloU3NQVjlDRTM1dFVHL3V4RzZqcTVwaEF2YkwyZkV4aG5BN0tRZHZSTE9kNUJwZWNEbGsrcWlEYzFKL2xVT252MUENCnFrMG9yaU4vSkdiMi81cGwvUHBDNDRqUEduZnhTS2V2ZFpYQmdXNUlmdUNMMFdNUTMrSXZNeXJ5Mnlmd0pQdDJWbFpIRzUNCjhBQUFkWVc3azltMXU1UFpzQUFBQUhjM05vTFhKellRQUFBZ0VBMHFOb2RQeTM0RFBjQ1JhbkFyeXFpQmIwS0NvMGFMeVUNCjNXU2c0VjFUOFlidjFVOEpoN2NiM3JIdjdreEMxd1JiUWFRL0NvS0R5VmZtVFdtVk1SeWtqWnljTzBKbHhJYXI2M0pzckcNCnNIOVo1U094YXB1Z01adlAvNC9IdXphV0xyN1FlbU13Zk1mNjY0a2lpa0RKR1hrVEE2dzVsTHBUVkJkNE5qd3h6MkprcVINCmlNbG9pZWtadU0xMm04UE1pWTd1ZCs3Yi9HL2RXNVI0QWZlb3owZ0Y2NmJhQXdadzVFRFY1NnlZZmJLcFpyeUl4RUxPRWUNCjBYaVU4RkZ4VldZL1l6am00YmpHdCs0cTNvbnI4SzNpYm5SMCtCLzRkaHAwN1RScGM0YmFheVd3bmMvSEJIZzF4dEM3UkQNCnlsd0Zoa2NreFU3Q1JMU1pjR3M4ZFVHSVMwWFVKRkxUNndLWUtMYmJjMDY2ZzJ0UEo1dENVd1ZSZjhMc09zc2pHUUQ4T2oNCjgvRUxhck9kVjFEQ2g4bzVVVEZqNno0ZXdkV1Myd1FVeXpNOVpVbWk5NjhGcHpOZjNtcnl2WVB4ZjFWd3FXam9GV2hqc2INCitwQVFGMHBKRFdrLzNwWTRYMjhuSVptT0JTRDNJL090Z1NacUQrdG5ucW5nMGFTR2pKc3BKcWRXS1NQQzdwUnRDMFVTd00NCkQxMjR5SE5vcmlGUUF3aDAzMWhrYVlteWhTc1BWOUNFMzV0VUcvdXhHNmpxNXBoQXZiTDJmRXhobkE3S1FkdlJMT2Q1QnANCmVjRGxrK3FpRGMxSi9sVU9udjFBcWswb3JpTi9KR2IyLzVwbC9QcEM0NGpQR25meFNLZXZkWlhCZ1c1SWZ1Q0wwV01RMysNCkl2TXlyeTJ5ZndKUHQyVmxaSEc1OEFBQUFEQVFBQkFBQUNBRXlBSUozc2N2T3dvZ2VDL0tFWDJHK1l0cEFuMCtUK0tLckgNCnMwNW1VT2gxYzRGck5URGZKZllaZGVSOE9nSlJpTHNzWmVEeFNkL0VWdFppdEZhajZuZXNHMm5DVWFld3FadlhjUFNsNHINCndvQmdHRDE1ekJKNFhuQ1l6WmVHMmNDY2VLY2FneSt1aWNrbGd5L25HNkp1d0tNaTE3N1dkUkVqZlB0bG5VbU9tTFI1UUENCllrRkVNWjFXc2U4Y2k1cWlHS1hpVUc4OFNZN0xPMUtybWRtK2RMZ0RYMGFkL2o1SDllZ3dYU201eTZDT2RMV2k5YWk1RFUNClZITjdnTWZkWE1ReWxGZ0NmZG1yWEZKNmtRQldodGhLMzNpR1UvekEyeHFUWUlFZXh4RUhIVUFUaUZwdE5rckE0R0tHREUNClR4VlhuVmt6bzRiRWVMM0ZsSzJaWVdERk9haFdYZzJ6c2R3UzhMbGdFTmdNclBXQkgyQ2pFVE11ZEMrdCtlMjJHS0EyR3ANCjRwT3A1a3laSFBubC9MU0pGbFdyNTVhVXBPbzViUVRydVkvdTRKOGYzcndER09hQ2FCT2NBNDZFd3czQlZXeHU2Q0UrNSsNCnltOXlyaktYdG1Vd1VPYkR1NUxZZmRTUDdTSnJ2WWN3MTY0SytZZjZ1Nk5uazBlSmVpNlJTdE1ISmxYMStaWWNzZGtJVjcNClRrd3FPVHBjbkZLd0NHRkRxc0xhR0RPeFdVdFI0RldHRjNDWjZzcUxmWUw3ZU5BYVFQZlVxU1A4MjRGVitaNGFzZXM1Z1QNCmhTUlBvVXVLQUFkSUlyMGlwd1JUdXhCSmtIcmh2RFBCVlQyMTdNN09aR0V1WlFqSDlMbityVUlMQUVhY1R4ZUJ4NVlqOFANCm1BZ0FOTnhiN3hLbmQ1K0k5eEFBQUJBRnhLNjVKeHUycGdyUnRRKzN3YmNmL21ZM2hHaFRHVHZqanNtVm4zVlpSOXAyeUgNCmxSYWJiRkZhLzlsMTVTTWNMT3JBeldNKzZuNUZPdllCLzdyeC8vYUpLRUozUENhZS9VTGNETVFxdDZTQ0tvbGNuODhuYVQNCnIvM2lwaldIUzA2dXRHR0NmV2UxQlhGT21xc3Q2eXEwd3NPWms3by9ScXBZUFJUdGoraUp5QmZqTmJGNnJYMklsVVExRGwNCmVQKzlUZjBwSjFBQk1BMElTUk9SRFphWTFyQUlyZHhSUFVOdGp4cWFDR2x4eUg2cG1nVlIvZjdqbFg2Ny85NndOMncxeFoNCkVtR3MyUkdZcmVnWko1dUlrd3ZmalVvVzZBZnhvNXJOMUMzMEZDbFVQcjB0SEdEdFJQTzhsZDdFaEJHUXJFNkJLa2h3bXgNCituWXJyZlk1UkViT1ZIVUFBQUVCQVB1RDBtT1VnMlNHM1VzRlhyTzZpSnkwYnRPQ2JLc3p3bFlGN3NoemwrV3BqMGpUcE8NCjZwQ3dQRXNIVkdSZFA0S2hzK2hlM3JqZENJUENFQlQ0SXlpY0ROMVJBSk9mWVd0cWJSYmF0bnJYaFpyNTExMlFsKzZwZ2INClZGMkw5VkczWExBWFUzSzI5TVB2QkNkSHhoMDhoR015QVAxWFdXQzVMWUpXTjZtaWplSGJuZ0k0SWdPKzVkcVFJMFI2eWYNCnRRQ0JmM01KOFBwMC8vWFJlN05kd09SSXFjdnJ5c2dpR0phUHpOL3k5M1hUUlJrR2Nuemo0REg4V2o4eUpOS3RjTzlxb1INClF5R3JCRUVCaFlTV0NDTXlXaFE1ZkhIWFNFc05ndlRKN2RPdDRpWUgzVjJCRGNEUmg2a0FHYzhJWXJWQ2lXOXhET21ySjENCmplMDloTEZTMXM1NnNBQUFFQkFOWmsrMytNZFBwdHdBOUJyQmI0Vjl0MTdsSkZPeEE5MjRqU2NKVVhUOTZrRU1kWEZJZ1ENClVQcU9McHJ5Q3NGS2pUT0xBQ29XS3h1UlZxanQ4WFpTaUtlUDhKZmp1cXpReE1CTFgwS1NJTEtqOFNDMW9sTVU3UGdTTE8NCkhnQ3FxTTJmK0JJN01QekU1TTAzSjdtTm5veVhualNLa1Q3dTFIU0YrWTlpTmxJYk5BTlBnc09FaG5zT01wcTMrK3VUTmgNCnp0YVRxbTlDeWgxc0hibU5lRGdaZlBIU2Q3M1BGRTFub1BEZ0hxZkMvckhWTzlyTU9vN0U1YmI4VFNTMVExOGxKdW03RWINCi9wQzlndnQ5eWxwMmVOM3luSllpY1U4ZE1HSk1MMG5oVEdpUG9sT2wwU3MwRkxtcHFsSEVxRkxUdlVmWnBhaWZhVUM5clkNCklqRG1NcTJZVjkwQUFBQWRZbkpoZVdGdVlXeHRiMjUwWlVCWFV5MURNREpJUkRCWVdsRXdOVTRCQWdNRUJRWT0NCi0tLS0tRU5EIE9QRU5TU0ggUFJJVkFURSBLRVktLS0tLQ0K
"""


@dataclass(kw_only=True)
class TestPlanInterface:
    _id: str
    date: str
    product: str
    test_name: list[str]
    barcode: str
    fixture_name: str
    fixture_ip: str
    auto_upload: bool
    link: str


class LinuxFileManager:
    def __init__(self, host, username, logger, password=None, port=22):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.ssh = None
        self.sftp = None
        self.logger = logger

    def connect(self, timeout=10):
        """建立 SSH 和 SFTP 连接"""
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if not self.password:
                self.password = ""
                self.password = self.password if self.password != "" else "None"
            self.ssh.connect(self.host, port=self.port, username=self.username, password=self.password, timeout=timeout)
            self.sftp = self.ssh.open_sftp()
            return True, "connect successfully"
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
                    return True, "connect successfully"
                except Exception as e:
                    return False, "connect failed"
            else:
                return False, "connect failed"

    def update_date(self, your_time):
        command = f'date -s "{your_time}"'
        # 执行命令
        stdin, stdout, stderr = self.ssh.exec_command(command, get_pty=True)
        time.sleep(0.1)
        return stdout.read().decode("utf-8")

    def run_script(self, script):
        stdin, stdout, stderr = self.ssh.exec_command(script, get_pty=True)
        time.sleep(0.1)
        return stdout.read().decode("utf-8")

    def list_files(self, remote_dir, show=True):
        """列出远程目录的文件"""
        try:
            files = self.sftp.listdir(remote_dir)
            return files
        except Exception as e:
            self.logger.error(f"❌ 无法列出文件: {e}")
            return []

    def download_file(self, remote_path, local_path):
        """下载远程文件到本地"""
        try:
            self.sftp.get(remote_path, local_path)
            return True
        except Exception as e:
            print(e)
            print(remote_path, local_path)
            return False

    def _is_dir(self, remote_path):
        """检查远程路径是否是目录"""
        try:
            return stat.S_ISDIR(self.sftp.stat(remote_path).st_mode)
        except IOError:
            return False

    def remote_dir_exists(
            self,
            dir_path: str
    ) -> bool:
        """
        检查远程目录是否存在

        Args:
            sftp: 已连接的SFTP客户端
            dir_path: 远程目录绝对路径

        Returns:
            bool: 目录是否存在
        """
        try:
            # 获取目录属性（会跟随符号链接）
            attrs = self.sftp.stat(dir_path)
            return attrs.st_mode & 0o40000  # 检查是否是目录
        except FileNotFoundError:
            return False
        except Exception as e:
            print(f"检查目录出错: {e}")
            return False

    def check_remote_dir_exists(self, remote_path):

        try:
            self.sftp.stat(remote_path)
            return True
        except IOError as e:
            print("IOError")
            return False

    def re_name_dir(self, local_dir, re_name):
        """
        rename
        """
        print("rename ", local_dir, re_name)
        if self.remote_dir_exists(local_dir):
            self.sftp.rename(local_dir, re_name)
            return True
        else:
            return False

    def download_dir(self, remote_dir, local_dir):
        """
        递归下载远程目录所有文件
        :param remote_dir: 远程目录路径 (e.g. '/home/user/data')
        :param local_dir: 本地存储路径 (e.g. 'C:/Downloads/data')
        """
        # 判断远程目录是否存在

        print("remote_dir:", remote_dir)

        if not self.check_remote_dir_exists(remote_dir):
            return False, "no such directory", ""

        files = self.sftp.listdir(remote_dir)
        if len(files) == 0:
            return True, "no files", ""
        try:
            os.makedirs(local_dir, exist_ok=True)
        except Exception as e:
            return False, "create dir failed", ""

        for item in files:
            remote_path = os.path.join(remote_dir, item).replace('\\', '/')
            local_path = os.path.join(local_dir, item)

            if self._is_dir(remote_path):
                self.download_dir(remote_path, local_path)  # 递归处理子目录
            else:
                self.download_file(remote_path, local_path)
        return True, "download success", local_dir

    def delete_file(self, remote_path):
        """删除远程文件"""
        try:
            self.sftp.remove(remote_path)
            self.logger.info(f"🗑️ 删除成功: {remote_path}")
            return True
        except Exception as e:
            self.logger.error(f"❌ 删除失败: {e}")
            return False

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

    def download_testing_data_to_server(self, get_local_path: Callable[[], str]) -> Tuple[str, str]:
        """
        download the testing data and zip the data, saving to server
        """
        _, download_path = get_local_path()
        _ret, _message, local_dir = self.download_dir("/data/testing_data", download_path)
        rename_dir = local_dir + "_" + get_time_str()
        self.re_name_dir(download_path, rename_dir)
        if not _ret:
            raise FileExistsError("Download Fail")
        self.close()
        # Zip the directory
        zip_path = f"{rename_dir}.zip"
        zip_directory(local_dir, zip_path)
        delete_folder(local_dir)
        if '\\' in zip_path:
            zip_path = zip_path.replace('\\', '/')
        saved_name = zip_path.split('/')[-1]
        return saved_name, zip_path

    @staticmethod
    def upload_target(db: MongoDBReader, drive: UploadData, file_name: str, production: Productions,
                      test_name: str, sn: str, zip_file: str, csv_id=None) -> Optional[dict[Any, Any]]:
        # filter the CSV file
        if 'csv' or "CSV" not in file_name:
            return

        def function_callback(progress: int):
            callback_result = db.set_database_filed({"barcode": sn}, {"auto_upload": progress})
            if callback_result is not None:
                print("sat progress")

        print("Debug Parameters: ")
        print(file_name),
        print(sn)
        print(production.value)
        print(zip_file)
        print(test_name)
        result = drive.update_data_to_google_drive(file_name, sn, production.value, zip_file, test_name,
                                                   func_callback=function_callback, csv_link=csv_id)
        print(result)

    def run_test_plan_trial(self, db: MongoDBReader, test_plan: TestPlanInterface):
        # 判断是否已上传或者是否为今日的日期
        auto_upload = test_plan.auto_upload
        if auto_upload:
            return
        plan_date = test_plan.date
        current_date = datetime.now().strftime("%Y-%m-%d")
        if plan_date != current_date:
            return
        # download
        robot_ip = test_plan.fixture_ip
        if robot_ip == "":
            flex_group = scan_flex()
            for _ip, value in flex_group.items():
                if value["name"] == test_plan.fixture_name:
                    robot_ip = _ip
        assert robot_ip != "", "Can not search the robot ip"
        self.host = robot_ip
        self.username = 'root'
        _ret, _message = self.connect()
        assert _ret, "connect to robot fail"
        sn = test_plan.barcode
        production = test_plan.product
        value_to_enum = {member.value: member for member in Productions}
        zip_name, zip_path = self.download_testing_data_to_server(check_system_dir_call_back)
        a = Ana(zip_path)
        res = a.ana_testing_data_zip()
        _link = db.find_by_condition({"barcode": sn})[0]["link"]
        if _link == "":
            _link = None
        for test_name in test_plan.test_name:
            test_key = TEST_NAME_SETTING[test_plan.product][test_name]
            data_files = res[test_key]  # 当前产品下的测试下的所有CSV
            for data_file in data_files:
                # format data_file
                if "\\" in data_file:
                    data_file = data_file.replace("\\", "/")
                if sn in data_file:
                    # TODO：分析当前数据是否为测试完整文件
                    # TODO：分析operator信息是否为半成品测试结果
                    google_drive_obj = UploadData()
                    google_drive_obj.star_int()

                    th = Thread(target=self.__class__.upload_target,
                                args=(db, google_drive_obj, data_file,value_to_enum[production], test_key, sn,zip_path),
                                kwargs={'csv_id': _link})
                    th.start()
                    th.join()
            return

    def run_test_plan_trials(self, db: MongoDBReader):
        reader = db
        reader.db_name = "TestPlan"
        reader.collection_name = "Index"
        reader.connect()
        collections = reader.find_all(limit=10000)
        for collection in collections:
            try:
                self.run_test_plan_trial(reader, TestPlanInterface(**collection))
            except Exception as e:
                raise Exception(e)

    @staticmethod
    def download_load_and_upload_cycling():
        """
        循环读取和上传
        :return:
        """
        from files_server.logs import logger
        # step1 读取开关状态，是否需要打开自动上传开关
        reader = MongoDBReader()
        is_turn_on = reader.auto_upload
        if is_turn_on:
            # step2 读取test plan table
            handler = LinuxFileManager("", "", logger)
            handler.run_test_plan_trials(reader)


if __name__ == '__main__':
    LinuxFileManager.download_load_and_upload_cycling()
