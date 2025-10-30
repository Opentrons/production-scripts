import shutil
import os
import json
from typing import Any

PROJECT_NAME = 'files_server'
from enum import Enum

class PlatformInfo(Enum):
    Windows = "Windows"
    Linux = "Linux"
    Mac = "Mac"

def zip_directory(src_dir, output_path):
    """
    将目录打包成 ZIP 文件
    :param src_dir: 要压缩的目录路径（如 "./my_folder"）
    :param output_path: 输出的 ZIP 文件路径（如 "./output.zip"）
    """
    shutil.make_archive(
        base_name=output_path.replace(".zip", ""),  # 去掉后缀，函数会自动添加
        format="zip",  # 支持 zip/tar/gztar 等
        root_dir=src_dir,
    )


def unzip_file(zip_path, extract_dir):
    """
    解压 ZIP 文件到指定目录
    """
    shutil.unpack_archive(zip_path, extract_dir, format="zip")
    print(f"已解压到: {extract_dir}")


def delete_folder(folder_path):
    """删除文件夹及其所有内容"""
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
    else:
        pass

def require_platform():
    import platform
    system_ = platform.system()
    if "Windows" in system_:
        return PlatformInfo.Windows
    elif "Linux" in system_:
        return PlatformInfo.Linux
    else:
        return PlatformInfo.Mac

def delete_zip(zip_path):
    """删除指定的 .zip 文件"""
    if os.path.exists(zip_path):
        os.remove(zip_path)  # 删除文件
    else:
        pass

def require_config() -> dict[str: Any]:
    """
    获取当前config
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_path = current_dir.split(PROJECT_NAME)[0]
    config_file = os.path.join(root_path, PROJECT_NAME, 'server_config.json')
    if '\\' in config_file:
        config_file = config_file.replace('\\', '/')
    with open(config_file) as f:
        data = json.load(f)
    return data



