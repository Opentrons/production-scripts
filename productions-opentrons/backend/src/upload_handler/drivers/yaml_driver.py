import os
import platform
import shutil

import yaml

PROJECT_NAME = "upload_handler"
SYSTEM_NAME = platform.system()


def resolve_file_path(path: str, file_name: str) -> str:
    if PROJECT_NAME in path:
        normalized_file_name = file_name.split(PROJECT_NAME)[-1]
        if "/" in normalized_file_name:
            normalized_file_name = normalized_file_name.split("/")[-1]
        elif "\\" in normalized_file_name:
            normalized_file_name = normalized_file_name.split("\\")[-1]
        file_path = os.path.join(path, normalized_file_name)
    else:
        file_path = os.path.join(path, file_name)

    if "\\" in file_path and SYSTEM_NAME == "Linux":
        file_path = file_path.replace("\\", "/")
    if "/" in file_path and SYSTEM_NAME == "Windows":
        file_path = file_path.replace("/", "\\")
    return file_path


class YamlDriver:
    def read_yaml(self, file_path: str, file_name: str):
        data = ""
        full_path = resolve_file_path(file_path, file_name)
        encodings = ["utf-8", "gbk", "gb2312", "latin1"]

        try:
            for encoding in encodings:
                try:
                    with open(full_path, "r", encoding=encoding) as yaml_file:
                        return yaml.load(yaml_file, Loader=yaml.FullLoader)
                except UnicodeDecodeError:
                    continue

            raise ValueError(f"Failed to decode YAML file with encodings: {encodings}")
        except Exception as err:
            print("读取yaml出错", err)
            return data

    def save_yaml(self, file_path: str, file_name: str, data):
        full_path = resolve_file_path(file_path, file_name)
        with open(full_path, "w", encoding="utf-8") as yaml_file:
            yaml.dump(data, yaml_file, allow_unicode=True, sort_keys=False)

    def update_yaml(self, file_path: str, file_name: str, key_path, new_value, backup=True):
        full_path = resolve_file_path(file_path, file_name)
        if backup:
            shutil.copy(full_path, full_path + ".bak")

        data = self.read_yaml(file_path, file_name)
        ref = data
        for key in key_path[:-1]:
            ref = ref[key]
        ref[key_path[-1]] = new_value

        self.save_yaml(file_path, file_name, data)
