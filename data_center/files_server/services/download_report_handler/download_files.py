import os
import paramiko
import stat
import time
import base64
import io
from typing import Callable, Optional, Union
from files_server.utils.main import zip_directory, delete_folder
from files_server.api.api_files import check_system_dir_call_back
from dataclasses import dataclass
from datetime import datetime
from files_server.services.flex_communications.discover_flex import scan_flex
from files_server.services.download_report_handler.analysis import Ana, TEST_NAME_SETTING
from files_server.services.google_driver_handler.main_updata import updata_class as UploadData
from files_server.services.google_driver_handler.main_updata import Productions
from files_server.settings.logs import get_logger
from files_server.database.driver import MongoDBReader
from threading import Thread
from typing import Any, Tuple
from files_server.services.slack.message import SlackBotMessenger

from .driver import ParamikoDriver
logger = get_logger('remote.handler')








class FilesHandler:
    def __init__(self, client: ParamikoDriver):
        self.sshClient = client

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

    def list_files(self, remote_dir):
        """列出远程目录的文件"""
        try:
            files = self.sftp.listdir(remote_dir)
            return files
        except Exception as e:
            logger.error(f"❌ 无法列出文件: {e}")
            return []

    def download_file(self, remote_path, local_path):
        """下载远程文件到本地"""
        try:
            self.sftp.get(remote_path, local_path)
            return True
        except Exception as e:
            logger.info(e)
            logger.info(remote_path, local_path)
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
            logger.info(f"检查目录出错: {e}")
            return False

    def check_remote_dir_exists(self, remote_path):

        try:
            self.sftp.stat(remote_path)
            return True
        except FileNotFoundError:
            logger.info("FileNotFound")
            return False
        except Exception as e:
            logger.info(f"其他错误: {e}")
            return False

    def re_name_dir(self, local_dir, re_name):
        """
        rename
        """
        logger.info(f"rename:  {local_dir} -> {re_name}")
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

        logger.info(f"remote_dir: {remote_dir}")

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
            logger.info(f"删除成功: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"删除失败: {e}")
            return False

    def delete_dir(self, remote_dir):
        files = self.sftp.listdir(remote_dir)
        if len(files) == 0:
            logger.info("文件夹目录为空, 删除跳出...")
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
                        logger.info(f"删除成功: {remote_dir}")
                    except Exception as e:
                        logger.info(f"删除失败: {e}")
                else:
                    pass

    def close(self):
        """关闭连接"""
        try:
            if self.sftp:
                self.sftp.close()
            if self.ssh:
                self.ssh.close()
            logger.info("连接已关闭")
        except Exception:
            pass

    def download_testing_data_to_server(self, get_local_path: Callable[[], str]) -> Tuple[str, str]:
        """
        download the testing data and zip the data, saving to server
        """
        _, download_path = get_local_path()
        remote_dir = "/data/testing_data"
        logger.info(f"Ready to download from {remote_dir} -> {download_path}")
        _ret, _message, local_dir = self.download_dir("/data/testing_data", download_path)
        rename_dir = local_dir + "_" + get_time_str()
        self.re_name_dir(download_path, rename_dir)
        if not _ret:
            raise FileExistsError("Download Fail")
        logger.info("Download files successful")
        # Zip the directory
        zip_path = f"{rename_dir}.zip"
        zip_directory(local_dir, zip_path)
        delete_folder(local_dir)
        if '\\' in zip_path:
            zip_path = zip_path.replace('\\', '/')
        saved_name = zip_path.split('/')[-1]
        return saved_name, zip_path

    def list_files_in_folder(self, folder):
        """
        递归列出远程文件夹下的所有文件

        Args:
            folder: 文件夹路径

        Returns:
            list: 所有文件的完整路径列表
        """
        all_files = []

        try:
            # 获取当前文件夹下的文件和文件夹列表
            files = self.list_files(folder)

            for file in files:
                file_path = folder + '/' + file

                if self._is_dir(file_path):
                    # 如果是文件夹，递归调用，并合并结果
                    sub_files = self.list_files_in_folder(file_path)
                    all_files.extend(sub_files)
                else:
                    # 如果是文件，添加到结果列表
                    all_files.append(file_path)

        except Exception as e:
            print(f"访问文件夹 {folder} 时出错: {e}")

        return all_files

    def is_production_exist(self, production, test_name, sn):
        folder_name = TEST_NAME_SETTING[production][test_name]
        root_folder = f'/data/testing_data/{folder_name}'.strip()
        logger.info(f"Remote folder: {root_folder}")
        if self.check_remote_dir_exists(root_folder):
            logger.info(f"Found remote folder: {root_folder}")
            files = self.list_files_in_folder(root_folder)
            for file in files:
                if sn in file:
                    logger.info(f"Find {file}")
                    return True
        else:
            return False

    @staticmethod
    def upload_target(db: MongoDBReader, drive: UploadData, file_name: str, production: Productions,
                      test_name: str, sn: str, zip_file: str, csv_id=None) -> Optional[dict[Any, Any]]:
        # filter the CSV file
        if '.csv' not in file_name:
            logger.info(f"Ignore {file_name}")
            return
        logger.info(f"Ready to upload {file_name}")

        def function_callback(progress: int):
            callback_result = db.set_database_filed({"barcode": sn}, {"auto_upload": progress})
            if callback_result is not None:
                logger.info(f"sat progress: {progress}")

        result = drive.update_data_to_google_drive(file_name, sn, production.value, zip_file, test_name,
                                                   func_callback=function_callback, csv_link=csv_id)
        result_handler = UploadResult(**result)
        db.set_database_filed({"barcode": sn}, {"link": result_handler.sheet_link})

        if result_handler.success:
            logger.info("=======================================================")
            logger.info(f"上传成功, sheet link: {result_handler.sheet_link}")
            logger.info("=======================================================")

            bot = SlackBotMessenger()

            # 发送测试通过消息
            bot.send_test_result(
                channel="production-data-center",
                test_type=test_name,
                test_result=result_handler.test_result if result_handler is not None else "None",
                serial_number=sn,
                test_data_link=result_handler.sheet_link if result_handler.sheet_link is not None else "None",
                tracking_sheet_link=result_handler.tracking_sheet if result_handler.tracking_sheet is not None else "None"
            )

    def run_test_plan_trial(self, db: MongoDBReader, test_plan: TestPlanInterface):
        # 判断是否已上传或者是否为今日的日期
        auto_upload = test_plan.auto_upload
        if auto_upload:
            logger.info("already uploaded")
            return
        plan_date = test_plan.date
        current_date = datetime.now().strftime("%Y-%m-%d")
        logger.info(plan_date)
        if plan_date != current_date:
            logger.info("out of date")
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
        logger.info(f"connect to {self.host} successful")
        sn = test_plan.barcode
        production = test_plan.product
        value_to_enum = {member.value: member for member in Productions}
        for test_name in test_plan.test_name:
            try:
                self.ensure_connection()
                logger.info(f"开始处理 {test_name}")
                # 判断当前文件是否生成
                if not self.is_production_exist(production, test_name, sn):
                    logger.info(f"No {production}-{sn} Found yet")
                    return
                zip_name, zip_path = self.download_testing_data_to_server(check_system_dir_call_back)
                a = Ana(zip_path)
                res = a.ana_testing_data_zip()
                _link = db.find_by_condition({"barcode": sn})[0]["link"]

                if _link == "":
                    logger.info("Link is '', set None")
                    _link = None
                else:
                    logger.debug(type(_link))
                    logger.info(f"Find Link: {_link}")

                test_key = TEST_NAME_SETTING[test_plan.product][test_name]
                data_files = res[test_key]  # 当前产品下的测试下的所有CSV
                for data_file in data_files:
                    # format data_file
                    if "\\" in data_file:
                        data_file = data_file.replace("\\", "/")
                    if sn in data_file:
                        # TODO：分析当前数据是否为测试完整文件
                        # TODO：分析operator信息是否为半成品测试结果
                        try:
                            logger.info("初始化google driver")
                            google_drive_obj = UploadData()
                            google_drive_obj.star_int()
                            logger.info("初始化google driver successful")
                        except Exception as e:
                            logger.error("初始化google driver failed")
                            logger.error(e)
                            raise

                        th = Thread(target=self.__class__.upload_target,
                                    args=(db, google_drive_obj, data_file, value_to_enum[production], test_key, sn,
                                          zip_path),
                                    kwargs={'csv_id': _link})
                        th.start()
                        th.join()
            except Exception as e:
                logger.info(f"处理 {test_name} 失败")
                logger.info(e)
        return

    def run_test_plan_trials(self, db: MongoDBReader):
        reader = db
        reader.db_name = "TestPlan"
        reader.collection_name = "Index"
        reader.connect()
        collections = reader.find_all(limit=10000)
        for collection in collections:
            try:
                logger.info(f"run upload trial: "
                            f"Production: {collection['product']}, "
                            f"SerialNumber: {collection['barcode']}")
                self.run_test_plan_trial(reader, TestPlanInterface(**collection))
            except Exception as e:
                logger.error(e)

    @staticmethod
    def download_load_and_upload_cycling():
        """
        循环读取和上传
        :return:
        """
        while True:
            # step1 读取开关状态，是否需要打开自动上传开关
            logger.info("="*20)
            logger.info("Starting Cycle")
            logger.info("=" * 20)
            reader = MongoDBReader()
            is_turn_on = reader.auto_upload
            if is_turn_on:
                # step2 读取test plan table
                logger.info("start upload")
                handler = LinuxFileManager("", "")
                handler.run_test_plan_trials(reader)
            else:
                logger.info("auto upload closed")
            reader.close()
            time.sleep(1 * 60)

if __name__ == '__main__':
    obj = LinuxFileManager(host="192.168.6.16", username="root")
    obj.connect()
    result = obj.is_production_exist("P1000S", "assembly_qc", "P1KSV3620251016A08.csv")
    print(result)