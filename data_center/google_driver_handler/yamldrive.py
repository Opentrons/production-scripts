import yaml
import os
import shutil
import platform

MY_PROJECT = "google_driver_handler"
system = platform.system()


def review_filename(path: str, file: str) -> str:
    if MY_PROJECT in path:
        _file = file.split(MY_PROJECT)[-1]
        if "/" in _file:
            _file = _file.split('/')[-1]
        elif '\\' in _file:
            _file = _file.split('\\')
        else:
            pass
        _path = os.path.join(path, _file)
    else:
        _path = os.path.join(path, file)
    if "\\" in _path and system == "Linux":
        _path = _path.replace('\\', "/")
    if "/" in _path and system == "Windows":
        _path = _path.replace('/', "\\")
    return _path


class yamlfunc():
    def __init__(self) -> None:
        pass

    def readyaml(self, failpath, nama):
        # review the file_name

        data = ''
        try:
            self.fullpath = review_filename(failpath, nama)
            # 读取YAML文件
            with open(self.fullpath, "r") as yaml_file:
                data = yaml.load(yaml_file, Loader=yaml.FullLoader)
                #print(data)
            return data
        except Exception as errval:
            print("读取yaml出错", errval)
            return data

    def saveyaml(self, failpath, nama, data):
        """保存 YAML 文件"""
        fullpath = review_filename(failpath, nama)
        with open(fullpath, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    def update_yaml(self, file_path, nama, key_path, new_value, backup=True):
        """
        修改 YAML 文件指定字段并保存
        :param file_path: YAML 文件路径
        :param key_path: 要修改的字段路径（例如 ["settings", "debug"]）
        :param new_value: 新值
        :param backup: 是否先备份原文件（默认 True）
        """
        # 可选：备份
        fullpath = review_filename(file_path, nama)
        if backup:
            shutil.copy(fullpath, fullpath + ".bak")

        # 1. 读取文件
        data = self.readyaml(file_path, nama)

        # 2. 找到并修改目标字段
        ref = data
        for key in key_path[:-1]:
            ref = ref[key]  # 逐层深入
        ref[key_path[-1]] = new_value  # 最后一级修改

        # 3. 保存文件
        self.saveyaml(file_path, nama, data)
        # print(f"✅ 已更新 {file_path} 中 {' → '.join(key_path)} = {new_value}")


if __name__ == "__main__":
    aa = yamlfunc()
    # bb=aa.readyaml("/Users/yew/googledriver/","updata.yaml")
    aa.update_yaml("/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/", "updata.yaml",
                   ["8ch_updata_volume", 0, "movetestfail", "Y2025", "yue_1"], "1111", False)
