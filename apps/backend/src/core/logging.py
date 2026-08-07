import logging
import os
from logging.handlers import RotatingFileHandler

from core.config import LOG_DIR, LOG_ERROR_FILE, LOG_INFO_FILE, LOG_MAX_SIZE


class InfoLogFilter(logging.Filter):
    """Keep runtime logs out of the error log."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < logging.ERROR


def setup_logging() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if any(getattr(handler, "_production_backend_handler", False) for handler in root_logger.handlers):
        return

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    info_handler = RotatingFileHandler(
        LOG_INFO_FILE,
        maxBytes=LOG_MAX_SIZE,
        backupCount=5,
        encoding="utf-8",
    )
    info_handler.setLevel(logging.INFO)
    info_handler.addFilter(InfoLogFilter())
    info_handler.setFormatter(formatter)
    info_handler._production_backend_handler = True

    error_handler = RotatingFileHandler(
        LOG_ERROR_FILE,
        maxBytes=LOG_MAX_SIZE,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    error_handler._production_backend_handler = True

    root_logger.addHandler(info_handler)
    root_logger.addHandler(error_handler)


_logging_setup = False


def get_logger(name: str) -> logging.Logger:
    global _logging_setup
    if not _logging_setup:
        setup_logging()
        _logging_setup = True
    return logging.getLogger(name)
