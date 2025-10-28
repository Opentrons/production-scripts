import os
import zipfile
from typing import List
import re
from datetime import datetime

TEST_NAME_SETTING = {
    "Robot": {
        "assembly_qc": "",
        "gantry_stress": "",
        "xy_belt_calibration": ""
    },
    "P200CH96": {
        "assembly_qc"
    },
    "P1000CH96": {
        "assembly_qc"
    },
    "P50S": {
        "assembly_qc": "pipette-assembly-qc-ot3",
        "speed_current_test": "pipette-current-speed-ot3",
        "grav_test": ""
    },

}


def get_time_str():
    # 获取当前时间
    now = datetime.now()
    time_str1 = now.strftime("%Y-%m-%d-%H-%M-%S")
    return time_str1

class Ana:
    def __init__(self, testing_data):
        self.testing_data_zip = testing_data

    def extract_and_list_zip(self, extract_to: str = None):
        """
        解压ZIP文件并返回所有内容的完整路径
        :param extract_to: 解压目录（默认解压到ZIP文件所在目录的同名文件夹）
        :return: 包含所有文件和文件夹路径的列表
        """
        # 设置默认解压目录
        zip_path = self.testing_data_zip
        # 设置默认解压目录
        if extract_to is None:
            base_dir = os.path.dirname(zip_path)
            zip_name = os.path.splitext(os.path.basename(zip_path))[0]
            clean_name = re.sub(r"_\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}", "", zip_name)
            extract_to = os.path.join(base_dir, clean_name+ '-' + get_time_str())
        # 确保解压目录存在
        os.makedirs(extract_to, exist_ok=True)
        all_paths = []
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # 解压所有文件
            zip_ref.extractall(extract_to)

            for item in os.listdir(extract_to):
                item_path = os.path.join(extract_to, item)
                if os.path.isdir(item_path):
                    all_paths.append(item)
        # os.remove(self.testing_data_zip)
        return extract_to, all_paths

    def judge_paths(self, test_name_list: List[str], _path: str, files_list: List[str]):
        """
        判断解压目录符合测试的路径
        """
        data_path_list = []
        for test_name in test_name_list:
            data_path = None
            for file in files_list:
                if test_name in file:
                    data_path = os.path.join(_path, file)
                    break
            data_path_list.append(data_path)
        return data_path_list

    def get_test_data(self, test_data_path: str):
        files_list = []
        for run_datas_dir in [os.path.join(test_data_path, run_data_dir) for run_data_dir in
                              os.listdir(test_data_path)]:
            for file in os.listdir(run_datas_dir):
                files_list.append(os.path.join(run_datas_dir, file))
        return files_list

    def ana_testing_data_zip(self):
        """
        分析testing_data, 返回测试报告路径
        Example:
            {'belt-calibration-ot3': ['C:\\Users\\22192\\production-scripts\\data_center\\files_server\\data\\
            testing_data\\belt-calibration-ot3\\run-25-08-11-00-40-18\\belt-calibration-ot3_run-25-08-11-00-40-
            18_CSVReport-FLXA3020250805002.csv'], 'robot-assembly-qc-ot3': ['C:\\Users\\22192\\production-script
            s\\data_center\\files_server\\data\\testing_data\\robot-assembly-qc-ot3\\run-25-08-08-00-35-41\\robo
            t-assembly-qc-ot3_run-25-08-08-00-35-41_CSVReport-FLXA3020250805002.csv', 'C:\\Users\\22192\\producti
            on-scripts\\data_center\\files_server\\data\\testing_data\\robot-assembly-qc-ot3\\run-25-08-08-08-17-
            15\\robot-assembly-qc-ot3_run-25-08-08-08-17-15_CSVReport-FLXA3020250805002.csv', 'C:\\Users\\22192\\
            production-scripts\\data_center\\files_server\\data\\testing_data\\robot-assembly-qc-ot3\\run-25-08-1
            1-07-43-19\\robot-assembly-qc-ot3_run-25-08-11-07-43-19_CSVReport-FLXS3020250808002.csv', 'C:\\Users\\
            22192\\production-scripts\\data_center\\files_server\\data\\testing_data\\robot-assembly-qc-ot3\\run-2
            5-08-11-07-48-04\\robot-assembly-qc-ot3_run-25-08-11-07-48-04_CSVReport-FLXS3020250808002.csv', 'C:\\Us
            ers\\22192\\production-scripts\\data_center\\files_server\\data\\testing_data\\robot-assembly-qc-ot3\\
            run-25-08-11-07-55-40\\robot-assembly-qc-ot3_run-25-08-11-07-55-40_CSVReport-FLXS3020250808002.csv']}

        """
        test_files = {}
        root_path, files = self.extract_and_list_zip()
        test_name_path_list = self.judge_paths(files, root_path, files)
        for test_name_path in test_name_path_list:
            if '\\' in test_name_path:
                test_name_path_split = test_name_path.replace('\\', '/')
            else:
                test_name_path_split = test_name_path
            test_name = test_name_path_split.split('/')[-1]
            if test_name_path is None:
                test_files.update({test_name: None})
                continue
            else:
                file_list = self.get_test_data(test_name_path)
                test_files.update({test_name: file_list})
        return test_files


if __name__ == '__main__':
    a = Ana(
        "C:\\Users\\22192\\production-scripts\\data_center\\files_server\\data\\testing_data_2025-08-14-13-12-19.zip")
    res = a.ana_testing_data_zip()
    print(res)
