import os
import time
from typing import Optional
from ot3_testing.leveling_test.type import TestNameLeveling, Direction
import csv
from typing import Any
from ot3_testing.leveling_test.config import LevelingSetting
import platform
TITLE_START = "START_TIME"
SYSTEM_PLATFORM = platform.system()


class LevelingCSV:
    def __init__(self, csv_name: str, saving_path: str, test_name: TestNameLeveling, robot_sn: str):
        self.csv_name = csv_name
        self.saving_path = saving_path
        self.file_name: Optional[str] = None
        self.format_file_name()
        self.test_name = test_name
        self.__start_time = self.__class__.create_start_time()
        self.__title = None
        self.robot_sn = robot_sn

    def create_csv_path(self):
        try:
            os.makedirs(self.saving_path, exist_ok=True)
        except Exception as e:
            print("Failed to create the report path: \n", e)

    @classmethod
    def create_start_time(cls) -> str:
        from datetime import datetime
        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d-%H-%M-%S")
        return time_str

    def update_create_time(self):
        self.__start_time = self.create_start_time()

    def format_file_name(self):
        self.file_name = os.path.join(self.saving_path, self.csv_name)
        if "Windows" in SYSTEM_PLATFORM and "/" in self.file_name:
            self.file_name = self.file_name.replace('/', '\\')
        else:
            if "\\" in self.file_name:
                self.file_name = self.file_name.replace('\\', '/')
        print("CSV PATH: ", self.file_name)

    def is_file_exist(self) -> bool:
        if os.path.exists(self.file_name) and os.path.isfile(self.file_name):
            return True
        else:
            return False

    def write_line(self, new_line: list[Any]) -> bool:
        while True:
            try:
                with open(self.file_name, 'a', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
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
                    writer = csv.writer(file)
                    writer.writerows(rows)
                    return True
            except PermissionError as e:
                print("先关闭正在查看的Report !")
                print(e)
                time.sleep(1)

    def init_title(self) -> None:
        """
        initial the report title
        :return:
        """
        setting = LevelingSetting[self.test_name]
        # append title
        title_list = [TITLE_START, "ROBOT_SN"]
        dir_y_list = {}
        dir_x_list = {}
        dir_z_list = {}
        for mount, slots in setting.items():
            if slots == {}:
                break
            for slot_name, slots_setting in slots.items():
                dir_y = {slot_name: slots_setting[Direction.Y]}
                dir_x = {slot_name: slots_setting[Direction.X]}
                dir_z = {slot_name: slots_setting[Direction.Z]}
                if dir_x[slot_name] != {}:
                    dir_x_list.update(dir_x)
                if dir_y[slot_name] != {}:
                    dir_y_list.update(dir_y)
                if dir_z[slot_name] != {}:
                    dir_z_list.update(dir_z)

            def extend_title(**directions):
                for direction, direction_value in directions.items():
                    for _slot_name, direction_config in direction_value.items():
                        channel_definition = direction_config["channel_definition"]
                        channel_list: list[str] = list(channel_definition.keys())
                        _pre_title_str = f"{mount.value}_{_slot_name.name}_{direction}"
                        _pre_title = list(map(lambda x: (_pre_title_str + "_" + x).upper(), channel_list))
                        _pre_title.append((_pre_title_str + "_result").upper())
                        title_list.extend(_pre_title)
            if self.test_name == TestNameLeveling.CH96_Leveling:
                directions_list = {Direction.Y.value: dir_y_list, Direction.X.value: dir_x_list,
                                   Direction.Z.value: dir_z_list}
            else:
                directions_list = {Direction.X.value: dir_x_list, Direction.Y.value: dir_y_list,
                                   Direction.Z.value: dir_z_list}
            extend_title(**directions_list)


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
                    reader = csv.reader(f)
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
