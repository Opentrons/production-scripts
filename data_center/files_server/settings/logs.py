import logging
import logging.config
from pathlib import Path
from files_server.utils.main import require_platform, PlatformInfo

# 所有可用的日志级别（级别数值到名称的映射）
LOG_LEVELS = {
    logging.DEBUG: 'DEBUG',      # 10 - 详细的调试信息
    logging.INFO: 'INFO',        # 20 - 正常的业务操作
    logging.WARNING: 'WARNING',  # 30 - 警告信息，但不影响系统运行
    logging.ERROR: 'ERROR',      # 40 - 错误信息，需要关注
    logging.CRITICAL: 'CRITICAL', # 50 - 严重错误，可能导致系统崩溃
}

LOG_FILE = "logs/app.log" if require_platform() != PlatformInfo.Linux else "/opt/data-center-server/logs/app.log"

def setup_logging():
    """设置日志配置"""
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
            }
        },
        "handlers": {
            "default": {
                "level": "INFO",
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "level": "DEBUG",
                "formatter": "detailed",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": LOG_FILE,
                "maxBytes": 10485760*10,  # 100MB
                "backupCount": 5,
            }
        },
        "loggers": {
            "app": {
                "level": "DEBUG",
                "handlers": ["default", "file"],
                "propagate": False
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["default"],
                "propagate": True
            }
        },
        "root": {
            "level": "INFO",
            "handlers": ["default"]
        }
    }

    # 确保日志目录存在
    Path("logs").mkdir(exist_ok=True)
    logging.config.dictConfig(log_config)


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的logger"""
    return logging.getLogger(f"app.{name}")
