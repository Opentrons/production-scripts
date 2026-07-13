import os
import shutil
import stat
import zipfile
from pathlib import Path
from time import mktime

from settings import get_logger
from upload_handler.parsers import extract_csv
from upload_handler.parsers.csv_common import (
    extract_meta_data_from_csv,
    extract_model_from_sn,
    parse_numeric_value,
)

logger = get_logger(__name__)


def unzip_file(zip_path, extract_to=".", encoding="utf-8", overwrite=False):
    zip_path = os.path.abspath(zip_path)
    extract_to = os.path.abspath(extract_to)

    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"ZIP文件未找到: {zip_path}")

    extracted_files = []
    extracted_dirs = set()

    try:
        with zipfile.ZipFile(zip_path, "r", allowZip64=True) as zip_ref:
            corrupt_file = zip_ref.testzip()
            if corrupt_file is not None:
                raise zipfile.BadZipFile(f"损坏的文件: {corrupt_file}")

            for file_info in zip_ref.infolist():
                try:
                    original_name = file_info.filename
                    decoded_name = original_name.encode("cp437").decode(encoding)
                except (UnicodeEncodeError, UnicodeDecodeError):
                    decoded_name = file_info.filename
                file_info.filename = decoded_name

                file_path = os.path.normpath(os.path.join(extract_to, decoded_name))
                target_path = Path(file_path)

                if file_info.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                    extracted_dirs.add(str(target_path))
                    continue

                if target_path.exists():
                    if overwrite:
                        try:
                            target_path.chmod(stat.S_IWRITE)
                            target_path.unlink()
                        except Exception as exc:
                            raise RuntimeError(f"无法覆盖文件 {target_path}: {str(exc)}") from exc
                    else:
                        logger.info(f"跳过已存在文件: {decoded_name}")
                        continue

                target_path.parent.mkdir(parents=True, exist_ok=True)
                with zip_ref.open(file_info) as source, open(target_path, "wb") as target:
                    shutil.copyfileobj(source, target)

                if os.name != "nt" and file_info.external_attr:
                    unix_perm = (file_info.external_attr >> 16) & 0o777
                    target_path.chmod(unix_perm)

                timestamp = mktime(file_info.date_time + (0, 0, 0))
                os.utime(target_path, (timestamp, timestamp))
                extracted_files.append(str(target_path))
                logger.info(f"已解压: {decoded_name}")

        return extracted_files + list(extracted_dirs)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError) as exc:
        logger.error(f"解压失败: {str(exc)}")
        if extracted_files or extracted_dirs:
            logger.info("正在清理已解压内容...")
            cleanup_extracted_files(extracted_files + list(extracted_dirs))
        raise


def cleanup_extracted_files(path_list):
    for path in sorted(path_list, key=len, reverse=True):
        try:
            item = Path(path)
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                item.rmdir()
        except Exception as exc:
            logger.warning(f"清理失败 {path}: {str(exc)}")


_cleanup_extracted_files = cleanup_extracted_files
_parse_numeric_value = parse_numeric_value
