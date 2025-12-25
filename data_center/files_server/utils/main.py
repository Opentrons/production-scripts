import shutil
import os
from ..types import OS
import time

PROJECT_NAME = 'files_server'


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


def require_platform() -> OS:
    import platform
    _system = platform.system()
    if "Windows" in _system:
        return OS.Windows
    elif "Linux" in _system:
        return OS.Linux
    else:
        return OS.Mac


def delete_zip(zip_path):
    """删除指定的 .zip 文件"""
    if os.path.exists(zip_path):
        os.remove(zip_path)  # 删除文件
    else:
        pass


def get_time_str():
    timestamp = time.time()
    local_time = time.localtime(timestamp)
    formatted_time = time.strftime("%Y-%m-%d-%H-%M-%S", local_time)
    return formatted_time
