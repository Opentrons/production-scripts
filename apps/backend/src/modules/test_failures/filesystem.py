from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import BinaryIO


def open_source(root: Path, relative: str) -> BinaryIO:
    """Open each component relative to an anchored directory, without symlinks.

    Keeping directory descriptors open closes the check/open race when a source
    path is replaced during a scan or an attachment request.
    """
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(part in {"..", "."} for part in path.parts):
        raise FileNotFoundError("报告路径无效")
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        descriptor = os.open(path.parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise FileNotFoundError("报告附件不是普通文件")
        return os.fdopen(descriptor, "rb")
    finally:
        os.close(directory)


def source_stat(root: Path, relative: str) -> os.stat_result:
    with open_source(root, relative) as handle:
        return os.fstat(handle.fileno())


def stat_signature(info: os.stat_result) -> tuple[int, int, int]:
    return info.st_ino, info.st_size, info.st_mtime_ns


def content_signature(info: os.stat_result) -> tuple[int, int, int, int, int]:
    """Include change time when reusing a recently verified content hash."""
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns
