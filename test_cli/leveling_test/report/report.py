import os
from typing import Optional
from test_cli.leveling_test.type import TestNameLeveling, Direction
import csv
from typing import Any
from test_cli.leveling_test.config import LevelingSetting
from test_cli.leveling_test.errors import CsvWriteError
from test_cli.leveling_test.retry import retry_locked_file_action
from test_cli.cli import ui
import platform
TITLE_START = "START_TIME"
SYSTEM_PLATFORM = platform.system()


def _pad_row(row: list[Any], length: int = 10) -> list[Any]:
    if len(row) >= length:
        return row
    return row + [""] * (length - len(row))


def _safe_file_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value).strip("_")


def _date_from_start_time(start_time: str) -> str:
    return start_time[:10]


class LevelingCSV:
    REQUIRED_TESTS = (
        TestNameLeveling.Z_Leveling,
        TestNameLeveling.CH8_Leveling,
        TestNameLeveling.CH96_Leveling,
    )
    OPTIONAL_TESTS = (TestNameLeveling.Gripper_Leveling,)
    REPORT_VERSION = "test-cli-leveling-report-v1"

    def __init__(
        self,
        csv_name: str,
        saving_path: str,
        test_name: TestNameLeveling,
        robot_sn: str,
        operator_name: str = "",
    ):
        self.saving_path = saving_path
        self.test_name = test_name
        self.robot_sn = robot_sn
        self.operator_name = operator_name
        safe_robot_sn = _safe_file_name(robot_sn)
        timestamp = self.create_start_time()
        report_date = _date_from_start_time(timestamp)
        if safe_robot_sn:
            self.csv_name = f"{safe_robot_sn}-leveling-report-{report_date}.csv"
        else:
            safe_csv_name = _safe_file_name(os.path.splitext(csv_name)[0]) or "leveling-report"
            self.csv_name = f"{safe_csv_name}-{report_date}.csv"
        self.file_name: Optional[str] = None
        self.format_file_name()
        self.__start_time = timestamp
        self.__title = None
        self.__result_values: list[Any] = []
        self.__slot_pass_results: list[bool] = []
        self.__final_status = "RUNNING"

    def create_csv_path(self):
        try:
            os.makedirs(self.saving_path, exist_ok=True)
        except Exception as e:
            raise CsvWriteError(self.saving_path, f"{type(e).__name__}: {e}") from e

    @classmethod
    def create_start_time(cls) -> str:
        from datetime import datetime
        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d-%H-%M-%S")
        return time_str

    @classmethod
    def create_run_time(cls) -> str:
        from datetime import datetime
        now = datetime.now()
        return now.strftime("run-%y-%m-%d-%H-%M-%S")

    def update_create_time(self):
        self.__start_time = self.create_start_time()

    def format_file_name(self):
        self.file_name = os.path.join(self.saving_path, self.csv_name)
        if "Windows" in SYSTEM_PLATFORM and "/" in self.file_name:
            self.file_name = self.file_name.replace('/', '\\')
        else:
            if "\\" in self.file_name:
                self.file_name = self.file_name.replace('\\', '/')
        abs_file_name = os.path.abspath(self.file_name)
        ui.info(ui.bilingual(f"CSV report path: {abs_file_name}", "CSV 报告路径"))

    def is_file_exist(self) -> bool:
        if os.path.exists(self.file_name) and os.path.isfile(self.file_name):
            return True
        else:
            return False

    def read_rows(self) -> list[list[str]]:
        if not self.is_file_exist():
            return []
        def read_file() -> list[list[str]]:
            with open(self.file_name, 'r', encoding='utf-8-sig', newline='') as file:
                return list(csv.reader(file))
        try:
            return retry_locked_file_action(self.file_name, read_file)
        except OSError as exc:
            raise CsvWriteError(self.file_name, f"{type(exc).__name__}: {exc}") from exc

    def write_line(self, new_line: list[Any]) -> bool:
        def write_file() -> bool:
            with open(self.file_name, 'a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(new_line)
                return True
        try:
            return retry_locked_file_action(self.file_name, write_file)
        except OSError as exc:
            raise CsvWriteError(self.file_name, f"{type(exc).__name__}: {exc}") from exc

    def write_rows(self, rows: list[list[Any]]):
        """
        write rows
        :param rows:
        :return:
        """
        def write_file() -> bool:
            with open(self.file_name, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerows(rows)
                return True
        try:
            return retry_locked_file_action(self.file_name, write_file)
        except OSError as exc:
            raise CsvWriteError(self.file_name, f"{type(exc).__name__}: {exc}") from exc

    def _all_test_names(self) -> tuple[TestNameLeveling, ...]:
        return self.REQUIRED_TESTS + self.OPTIONAL_TESTS

    def _initial_rows(self) -> list[list[Any]]:
        rows: list[list[Any]] = [
            _pad_row([0, "-------", "---", "---", "---", "---", "---", "---", "---", "---"]),
            _pad_row([0, "RESULTS"]),
            _pad_row([0, "overall-result", "PENDING"]),
        ]
        for test_name in self._all_test_names():
            rows.append(_pad_row([0, test_name.value, "NOT_RUN"]))
        rows.extend([
            _pad_row([0.01, "--------"]),
            _pad_row([0.01, "METADATA"]),
            _pad_row([0.01, "test-name", "test-cli-leveling"]),
            _pad_row([0.01, "operator-name", self.operator_name or os.getenv("USER", "")]),
            _pad_row([0.01, "session-id", self.robot_sn]),
            _pad_row([0.01, "robot", self.robot_sn]),
            _pad_row([0.01, "date", self.create_run_time()]),
            _pad_row([0.01, "live"]),
            _pad_row([0.02, "version", self.REPORT_VERSION]),
            _pad_row([0.02, "-------------------"]),
            _pad_row([0.1, "----"]),
            _pad_row([0.1, "TEST"]),
        ])
        return rows

    def _is_results_row(self, row: list[str], result_name: str) -> bool:
        return len(row) > 1 and str(row[0]) == "0" and row[1] == result_name

    def _ensure_base_report(self) -> list[list[Any]]:
        rows = self.read_rows()
        if not rows:
            rows = self._initial_rows()
        result_names = {row[1] for row in rows if len(row) > 1 and str(row[0]) == "0"}
        insert_at = 2
        if "overall-result" not in result_names:
            rows.insert(insert_at, _pad_row([0, "overall-result", "PENDING"]))
            insert_at += 1
        for test_name in self._all_test_names():
            if test_name.value not in result_names:
                rows.insert(insert_at, _pad_row([0, test_name.value, "NOT_RUN"]))
                insert_at += 1
        self._update_metadata(rows)
        return rows

    def _update_metadata(self, rows: list[list[Any]]) -> None:
        metadata_values = {
            "test-name": "test-cli-leveling",
            "operator-name": self.operator_name or os.getenv("USER", ""),
            "session-id": self.robot_sn,
            "robot": self.robot_sn,
            "version": self.REPORT_VERSION,
        }
        found = set()
        for row in rows:
            if len(row) > 2 and row[1] in metadata_values:
                row[2] = metadata_values[row[1]]
                found.add(row[1])
        if found == set(metadata_values):
            return
        insert_at = 0
        for index, row in enumerate(rows):
            if len(row) > 1 and row[1] == "TEST":
                insert_at = index
                break
        for key, value in metadata_values.items():
            if key not in found:
                rows.insert(insert_at, _pad_row([0.01, key, value]))
                insert_at += 1

    def _set_test_status(self, rows: list[list[Any]], test_name: TestNameLeveling, status: str) -> None:
        for row in rows:
            if self._is_results_row(row, test_name.value):
                while len(row) <= 2:
                    row.append("")
                row[2] = status
                return
        rows.insert(3, _pad_row([0, test_name.value, status]))

    def _get_test_status(self, rows: list[list[Any]], test_name: TestNameLeveling) -> str:
        for row in rows:
            if self._is_results_row(row, test_name.value) and len(row) > 2:
                return row[2]
        return "NOT_RUN"

    def _refresh_overall_result(self, rows: list[list[Any]]) -> None:
        statuses = {test_name: self._get_test_status(rows, test_name) for test_name in self._all_test_names()}
        if any(status == "FAIL" for status in statuses.values()):
            overall = "FAIL"
        elif all(statuses[test_name] == "PASS" for test_name in self.REQUIRED_TESTS):
            overall = "PASS"
        else:
            overall = "PENDING"

        for row in rows:
            if self._is_results_row(row, "overall-result"):
                while len(row) <= 2:
                    row.append("")
                row[2] = overall
                return
        rows.insert(2, _pad_row([0, "overall-result", overall]))

    def _test_section_bounds(self, rows: list[list[Any]], test_name: TestNameLeveling) -> Optional[tuple[int, int]]:
        start = None
        for index, row in enumerate(rows):
            if len(row) > 2 and row[1] == "TEST" and row[2] == test_name.value:
                start = index
                break
        if start is None:
            return None
        end = len(rows)
        for index in range(start + 1, len(rows)):
            row = rows[index]
            if len(row) > 2 and row[1] == "TEST":
                end = index
                break
        return start, end

    def _remove_test_section(self, rows: list[list[Any]], test_name: TestNameLeveling) -> list[list[Any]]:
        bounds = self._test_section_bounds(rows, test_name)
        if bounds is None:
            return rows
        start, end = bounds
        return rows[:start] + rows[end:]

    def _render_test_section(self) -> list[list[Any]]:
        title = list(self.__title)
        data = [self.__start_time, self.robot_sn] + self.__result_values
        if len(data) < len(title):
            data.extend([""] * (len(title) - len(data)))
        title.append("RESULT_STATUS")
        data.append(self.__final_status)
        return [
            _pad_row([0.1, "TEST", self.test_name.value]),
            title,
            data,
        ]

    def _replace_test_section(self, rows: list[list[Any]]) -> list[list[Any]]:
        rows = self._remove_test_section(rows, self.test_name)
        rows.extend(self._render_test_section())
        return rows

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
        self.__result_values = []
        self.__slot_pass_results = []
        self.__final_status = "RUNNING"
        rows = self._ensure_base_report()
        rows = self._remove_test_section(rows, self.test_name)
        self._set_test_status(rows, self.test_name, "RUNNING")
        self._refresh_overall_result(rows)
        self.write_rows(rows)

    def write_new_results(self, result: dict, passed: Optional[bool] = None):
        """
        write result to CSv
        :param result:
        :return:
        """
        ui.info(ui.bilingual("Writing to CSV", "正在写入报告"))
        data_list = list(result.values())
        if self.__title is None:
            self.init_title()
        if not os.path.exists(self.file_name):
            raise FileExistsError(f"{self.file_name} should be initialed first !")
        self.__result_values.extend(data_list)
        if passed is not None:
            self.__slot_pass_results.append(passed)
        rows = self._ensure_base_report()
        rows = self._replace_test_section(rows)
        self.write_rows(rows)

    def finish_test(self, passed: Optional[bool] = None):
        if passed is None:
            passed = bool(self.__slot_pass_results) and all(self.__slot_pass_results)
        self.__final_status = "PASS" if passed else "FAIL"
        rows = self._ensure_base_report()
        rows = self._replace_test_section(rows)
        self._set_test_status(rows, self.test_name, self.__final_status)
        self._refresh_overall_result(rows)
        self.write_rows(rows)


if __name__ == '__main__':
    pass
