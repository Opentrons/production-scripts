import shutil
import os
from ..this_types import OS
import time
from typing import Optional

PROJECT_NAME = 'src'


def zip_directory(src_dir, output_path=None):
    """
    将目录打包成 ZIP 文件
    :param src_dir: 要压缩的目录路径（如 "./my_folder"）
    :param output_path: 输出的 ZIP 文件路径（如 "./output.zip"）
    """
    if output_path is None:
        output_path = src_dir+ '.zip'
    shutil.make_archive(
        base_name=output_path.replace(".zip", ""),  # 去掉后缀，函数会自动添加
        format="zip",  # 支持 zip/tar/gztar 等
        root_dir=src_dir,
    )
    return output_path


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


def contact_path(base_path: str, name: str) -> str:
    result = os.path.join(base_path, name)
    if require_platform() is OS.Windows:
        result = result.replace("/", "\\")
    else:
        result = result.replace("\\", "/")
    return result


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


def get_base_name(file_path: str) -> Optional[str]:
    """
    基于文件路径，获取文件所在的完整文件夹目录路径

    Args:
        file_path: 文件完整路径

    Returns:
        str: 文件所在的文件夹目录路径
        None: 如果输入为空或无效

    Examples:
        >>> get_base_name("/data/testing_data/folder1/file.txt")
        '/data/testing_data/folder1'

        >>> get_base_name("C:\\downloads\\folder2\\test.py")
        'C:\\downloads\\folder2'

        >>> get_base_name("file.txt")
        ''  # 空字符串表示当前目录

        >>> get_base_name("/just_file.txt")
        '/'  # 根目录
    """
    if not file_path or not isinstance(file_path, str):
        return None

    try:
        # 使用os.path.dirname直接获取目录路径
        dir_path = os.path.dirname(file_path)

        # 处理不同情况
        if not dir_path:
            # 当前目录
            return ''
        elif dir_path == file_path:
            # 已经是目录，没有文件名
            return file_path
        else:
            return dir_path

    except Exception as e:
        print(f"获取文件夹目录路径失败 {file_path}: {e}")
        return None


def normalize_path(path: str) -> str:
    """标准化路径格式"""
    if not path:
        return ''

    # 替换反斜杠为正斜杠
    path = path.replace('\\', '/')

    # 移除重复的斜杠
    while '//' in path:
        path = path.replace('//', '/')

    return path

def match_pattern(filename: str, pattern: str) -> bool:
        """检查文件名是否匹配模式"""
        if pattern == "*":
            return True

        if pattern.startswith("*."):
            extension = pattern[1:]  # 去掉*
            return filename.endswith(extension)

        # 简单的通配符匹配
        import fnmatch
        return fnmatch.fnmatch(filename, pattern)

def format_bytes(size: int) -> str:
        """格式化字节大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"