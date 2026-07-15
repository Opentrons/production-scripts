import os
import platform
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

IS_WINDOWS = platform.system().lower() == 'windows'
IS_MAC = platform.system().lower() == 'darwin'

PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
RUN_ENV = os.getenv("DATA_HANDLER_RUN_ENV", "dev" if IS_WINDOWS or IS_MAC else "server").lower()
IS_DEV_ENV = RUN_ENV in ("dev", "local", "development")

LOCAL_SERVER_HOST = os.getenv("DATA_HANDLER_LOCAL_SERVER_HOST", "192.168.6.55")
SERVER_ENV_HOST = os.getenv("DATA_HANDLER_SERVER_ENV_HOST", "localhost")
DATA_HANDLER_HOST = os.getenv(
    "DATA_HANDLER_HOST",
    LOCAL_SERVER_HOST if IS_DEV_ENV else SERVER_ENV_HOST,
)
PUSH_REMOTE_HOST = os.getenv("DATA_HANDLER_PUSH_HOST", DATA_HANDLER_HOST)
DATA_HANDLER_PORT = int(os.getenv("DATA_HANDLER_PORT", "8090"))
DATA_CENTER_BASE_URL = os.getenv(
    "DATA_HANDLER_BASE_URL",
    f"http://{DATA_HANDLER_HOST}:{DATA_HANDLER_PORT}",
).rstrip("/")

if IS_WINDOWS or IS_MAC:
    DOWNLOAD_DIR = os.path.join(PROJECT_ROOT, "datas", "temp")
    TESTING_DATA_DIR = os.path.join(PROJECT_ROOT, "datas", "testing_data")
    FILE_RESOURCE_DIR = os.path.join(PROJECT_ROOT, "datas", "file_resources")
    CONFIG_DIR = os.path.join(PROJECT_ROOT, "configs")
else:
    DOWNLOAD_DIR = "/data/temp"
    TESTING_DATA_DIR = "/data/testing_data"
    FILE_RESOURCE_DIR = "/data/file_resources"
    CONFIG_DIR = "/configs"

FILE_RESOURCE_DIR = os.getenv("DATA_HANDLER_FILE_RESOURCE_DIR", FILE_RESOURCE_DIR)

if IS_DEV_ENV:
    GOOGLE_AUTH_DIR = os.path.join(PROJECT_ROOT, "auth")
    ROBOT_KEY_PATH = os.path.join(GOOGLE_AUTH_DIR, "robot_key")
else:
    GOOGLE_AUTH_DIR = "/configs"
    if IS_WINDOWS or IS_MAC:
        ROBOT_KEY_PATH = os.path.join(PROJECT_ROOT, "configs", "robot_key")
    else:
        ROBOT_KEY_PATH = os.path.expanduser("~/robot_key")

ROBOT_KEY_PATH = os.getenv("DATA_HANDLER_ROBOT_KEY_PATH", ROBOT_KEY_PATH)
SLACK_CONFIG_PATH = os.getenv(
    "DATA_HANDLER_SLACK_CONFIG_PATH",
    os.path.join(GOOGLE_AUTH_DIR, "slack.yaml"),
)

if IS_DEV_ENV:
    LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
else:
    LOG_DIR = "/var/log"

LOG_INFO_FILE = os.path.join(LOG_DIR, "data-handler-info.log")
LOG_ERROR_FILE = os.path.join(LOG_DIR, "data-handler-error.log")
LOG_FILE = LOG_INFO_FILE

LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB

MONGO_HOST = os.getenv("DATA_HANDLER_MONGO_HOST", DATA_HANDLER_HOST)
MONGO_URI = os.getenv("DATA_HANDLER_MONGO_URI", "")

# google driver
TOKEN_PATH = os.path.join(GOOGLE_AUTH_DIR, "token.json") 
CREDENTIALS_PATH = os.path.join(GOOGLE_AUTH_DIR, "credentials.json")
SHEET_TOKEN_PATH = os.path.join(GOOGLE_AUTH_DIR, "sheettoken.json")
ENVIRONMENT = "production"  # debug or production
# ENVIRONMENT = "production"  # debug or production
# database
DATA_DB_NAME = "ProductionsData2026"  # 数据库名称
EXPIRE_DAYS = 10  # 数据过期时间，默认1天过期
MESSAGE_COLLECTION = "ProductionsMessage"
DATA_UPLOAD_STATUS_COLLECTION = "data_upload_status"
DATA_UPLOAD_RECORD_COLLECTION = "data_upload_records"
PRODUCT_MANAGEMENT_COLLECTION = "product_management"
UNIT_TRACKER_COLLECTION = "unit_tracker_rows"
ROBOT_SCAN_GATEWAY_COLLECTION = "robot_scan_gateways"
ROBOT_SCAN_CACHE_COLLECTION = "robot_scan_cache"
UPLOAD_FINISH_SETTINGS_COLLECTION = "upload_finish_settings"
FILE_RESOURCE_PROJECTS_COLLECTION = "file_resource_projects"
FILE_RESOURCE_VERSIONS_COLLECTION = "file_resource_versions"

# Robot 设备配置
ROBOT_HEALTH_PORT = 31950
ROBOT_TEST_WORKING_DIRECTORY = os.getenv(
    "DATA_HANDLER_ROBOT_TEST_WORKING_DIRECTORY",
    "/opt/opentrons-robot-server",
).strip() or "/opt/opentrons-robot-server"
ROBOT_SCAN_INTERVAL_SECONDS = int(os.getenv("DATA_HANDLER_ROBOT_SCAN_INTERVAL_SECONDS", "180"))
ROBOT_SCAN_CONNECT_TIMEOUT_SECONDS = float(
    os.getenv("DATA_HANDLER_ROBOT_SCAN_CONNECT_TIMEOUT_SECONDS", "0.5")
)
ROBOT_SCAN_HTTP_TIMEOUT_SECONDS = float(
    os.getenv("DATA_HANDLER_ROBOT_SCAN_HTTP_TIMEOUT_SECONDS", "2")
)
ROBOT_SCAN_MAX_DURATION_SECONDS = int(
    os.getenv("DATA_HANDLER_ROBOT_SCAN_MAX_DURATION_SECONDS", "120")
)
ROBOT_IP_RANGE_START = 100
ROBOT_IP_RANGE_END = 120
ROBOT_IP_PREFIX = "192.168.1."
ROBOT_PROTOCOL_SOURCE_BASES = [
    "/data/opentrons_robot_server/protocols",
    "/var/lib/opentrons-robot-server/protocols",
]



# 确保目录存在
def ensure_directories():
    """确保所有配置目录都存在"""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(FILE_RESOURCE_DIR, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if IS_DEV_ENV:
        os.makedirs(GOOGLE_AUTH_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)


class InfoLogFilter(logging.Filter):
    """Keep runtime logs out of the error log."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < logging.ERROR

def setup_logging():
    """设置全局日志配置"""
    os.makedirs(LOG_DIR, exist_ok=True)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
        
        
    if any(getattr(handler, "_data_handler_handler", False) for handler in root_logger.handlers):
        return

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    info_handler = RotatingFileHandler(
        LOG_INFO_FILE,
        maxBytes=LOG_MAX_SIZE,
        backupCount=5,
        encoding="utf-8",
    )
    info_handler.setLevel(logging.INFO)
    info_handler.addFilter(InfoLogFilter())
    info_handler.setFormatter(formatter)
    info_handler._data_handler_handler = True

    error_handler = RotatingFileHandler(
        LOG_ERROR_FILE,
        maxBytes=LOG_MAX_SIZE,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    error_handler._data_handler_handler = True

    root_logger.addHandler(info_handler)
    root_logger.addHandler(error_handler)

_logging_setup = False

def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志记录器"""
    global _logging_setup
    if not _logging_setup:
        setup_logging()
        _logging_setup = True
    return logging.getLogger(name)

# 自动创建目录
ensure_directories()
