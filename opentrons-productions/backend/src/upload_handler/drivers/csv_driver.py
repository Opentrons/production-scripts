import os
from pathlib import Path


class CsvDriver:
    def read_csv_lines(self, path: str):
        rows = []
        with open(path, "rt", encoding="utf-8") as csv_file:
            for line in csv_file:
                if line != "\n":
                    rows.append([line.replace("\n", "").replace("\r", "")])
        return rows

    def read_csv_rows(self, path: str):
        rows = []
        with open(path, "rt", encoding="utf-8") as csv_file:
            for line in csv_file:
                if line != "\n":
                    rows.append([line.replace("\n", "").split(",")])
        return rows

    def find_files(self, path: str, keyword: str):
        matched_files = []
        try:
            for _, _, files in os.walk(path):
                for file_name in files:
                    if str(keyword) in file_name:
                        matched_files.append(str(Path(path) / file_name))
        except Exception as err:
            print(err)
        return matched_files
