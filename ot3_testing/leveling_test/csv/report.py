import os
import time

from ot3_testing.leveling_test.type import TestNameLeveling
import csv as csv_module
from typing import Any
from ot3_testing.leveling_test.config import LevelingSetting

TITLE_START = "START_TIME"


class LevelingCSV:
    def __init__(self, csv_name: str, saving_path: str, test_name: TestNameLeveling, robot_sn: str):
        self.csv_name = csv_name
        self.saving_path = saving_path
        self.file_name = os.path.join(self.saving_path, self.csv_name)
        self.format_file_name()
        self.test_name = test_name
        self.__start_time = self.__class__.create_start_time()
        self.__title = None
        self.robot_sn = robot_sn

    def create_csv_path(self):
        try:
            os.makedirs(self.saving_path, exist_ok=True)
        except Exception as e:
            print("Failed to create the csv path: \n", e)

    @classmethod
    def create_start_time(cls) -> str:
        from datetime import datetime
        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d-%H-%M-%S")
        return time_str

    def format_file_name(self):
        if '\\' in self.file_name:
            self.file_name = self.file_name.replace('\\', '/')

    def is_file_exist(self) -> bool:
        if os.path.exists(self.file_name) and os.path.isfile(self.file_name):
            return True
        else:
            return False

    def write_line(self, new_line: list[Any]) -> bool:
        while True:
            try:
                with open(self.file_name, 'a', newline='', encoding='utf-8') as file:
                    writer = csv_module.writer(file)
                    writer.writerow(new_line)
                    return True
            except PermissionError as e:
                print("先关闭正在查看的Report !")
                print(e)
                time.sleep(1)

    def write_rows(self, rows: list[list[Any]]):
        """
        write rows
        :param rows:
        :return:
        """
        while True:
            try:
                with open(self.file_name, 'w', newline='', encoding='utf-8') as file:
                    writer = csv_module.writer(file)
                    writer.writerows(rows)
                    return True
            except PermissionError as e:
                print("先关闭正在查看的Report !")
                print(e)
                time.sleep(1)

    def init_title(self) -> None:
        """
        initial the csv title
        :return:
        """
        setting = LevelingSetting[self.test_name]
        # append title
        title_list = [TITLE_START, "ROBOT_SN"]
        for mount, slots in setting.items():
            if slots == {}:
                break
            for slot_name, slots_setting in slots.items():
                for direction, direction_config in slots_setting.items():
                    if direction_config == {}:
                        break
                    channel_definition = direction_config["channel_definition"]
                    channel_list: list[str] = list(channel_definition.keys())
                    _pre_title_str = f"{mount.value}_{slot_name.name}_{direction.value}"
                    _pre_title = list(map(lambda x: (_pre_title_str + "_" + x).upper(), channel_list))
                    _pre_title.append((_pre_title_str + "_result").upper())
                    title_list.extend(_pre_title)
        self.__title = title_list
        if not self.is_file_exist():
            self.write_line(title_list)

    def write_new_results(self, result: dict):
        """
        write result to CSv
        :param result:
        :return:
        """
        print("Writing to CSV \n")
        data_list = list(result.values())
        if not os.path.exists(self.file_name):
            raise FileExistsError(f"{self.file_name} should be initialed first !")
        while True:
            try:
                with open(self.file_name, 'r', encoding='utf-8') as f:
                    reader = csv_module.reader(f)
                    rows = list(reader)
                    last_row = rows[-1]
                    break
            except PermissionError as e:
                print("先关闭正在查看的Report !")
                print(e)
        if last_row is None:
            raise ValueError("Failed to read last row")
        data_length_define = len(self.__title)

        def init_first_result(data: list, init_time: str):
            # init time str
            data.insert(0, init_time)
            data.insert(1, self.robot_sn)
            self.write_line(data)

        if len(last_row) == data_length_define:
            init_first_result(data_list, self.__start_time)
        else:
            time_str = last_row[0]
            if time_str == self.__start_time:
                last_row.extend(data_list)
                rows[-1] = last_row
                self.write_rows(rows)
            else:
                init_first_result(data_list, self.__start_time)


if __name__ == '__main__':
    pass
