import os,sys
import zipfile
import shutil
import stat
from time import mktime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def unzip_file(zip_path, extract_to='.', encoding='utf-8', overwrite=False):
    """
    兼容 Python <3.11 的解压函数
    """
    zip_path = os.path.abspath(zip_path)
    extract_to = os.path.abspath(extract_to)

    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"ZIP文件未找到: {zip_path}")

    extracted_files = []
    extracted_dirs = set()

    try:
        with zipfile.ZipFile(zip_path, 'r', allowZip64=True) as zip_ref:
            # 检查ZIP完整性
            corrupt_file = zip_ref.testzip()
            if corrupt_file is not None:
                raise zipfile.BadZipFile(f"损坏的文件: {corrupt_file}")

            for file_info in zip_ref.infolist():
                # 处理文件名编码（兼容旧版本）
                try:
                    original_name = file_info.filename
                    decoded_name = original_name.encode('cp437').decode(encoding)
                except (UnicodeEncodeError, UnicodeDecodeError):
                    decoded_name = original_name  # 回退到原始名称
                file_info.filename = decoded_name  # 重写文件名

                # 处理路径
                file_path = os.path.normpath(os.path.join(extract_to, decoded_name))
                target_path = Path(file_path)

                # 跳过目录条目
                if file_info.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                    extracted_dirs.add(str(target_path))
                    continue

                # 处理文件覆盖
                if target_path.exists():
                    if overwrite:
                        try:
                            target_path.chmod(stat.S_IWRITE)
                            target_path.unlink()
                        except Exception as e:
                            raise RuntimeError(f"无法覆盖文件 {target_path}: {str(e)}")
                    else:
                        logger.info(f"跳过已存在文件: {decoded_name}")
                        continue

                # 创建父目录
                parent_dir = target_path.parent
                parent_dir.mkdir(parents=True, exist_ok=True)

                # 提取文件
                with zip_ref.open(file_info) as source, open(target_path, 'wb') as target:
                    shutil.copyfileobj(source, target)

                # 保留权限（Unix）
                if os.name != 'nt' and file_info.external_attr:
                    unix_perm = (file_info.external_attr >> 16) & 0o777
                    target_path.chmod(unix_perm)

                # 保留修改时间
                timestamp = mktime(file_info.date_time + (0, 0, 0))
                os.utime(target_path, (timestamp, timestamp))

                extracted_files.append(str(target_path))
                logger.info(f"已解压: {decoded_name}")

        return extracted_files + list(extracted_dirs)

    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError) as e:
        logger.error(f"解压失败: {str(e)}")
        if extracted_files or extracted_dirs:
            logger.info("正在清理已解压内容...")
            _cleanup_extracted_files(extracted_files + list(extracted_dirs))
        raise

def _cleanup_extracted_files(path_list):
    """安全清理已解压内容"""
    for path in sorted(path_list, key=len, reverse=True):
        try:
            p = Path(path)
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
        except Exception as e:
            logger.warning(f"清理失败 {path}: {str(e)}")



if __name__ == "__main__":
    try:
        # 使用示例
        base_path = os.path.abspath(sys.argv[0])
        base_path2 = os.path.abspath(".")
        upfilepath = os.path.join(base_path2,"upload/function/1ch/run-25-04-23-14-22-40.zip")
        extracted = unzip_file(
            zip_path=upfilepath,
            extract_to="./"+str(),
            encoding='gbk',  # 处理中文文件名
            overwrite=True
        )
        print(f"成功解压 {len(extracted)} 个文件")
        
    except:
        pass
