import os
import platform
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]
APPS_ROOT = API_ROOT.parent
REPOSITORY_ROOT = APPS_ROOT.parent


def _load_local_env() -> None:
    """Load the API-local .env without replacing exported variables."""

    env_path = API_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            continue
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        os.environ.setdefault(key, value)


_load_local_env()

APP_VERSION_PATH = Path(
    os.getenv("PRODUCTION_PLATFORM_APP_VERSION_PATH", APPS_ROOT / "version.json")
)
DATA_DIR = Path(os.getenv("PRODUCTION_PLATFORM_DATA_DIR", API_ROOT / "data"))
APP_DEPLOYMENT_VERSION_PATH = Path(
    os.getenv("PRODUCTION_PLATFORM_APP_DEPLOYMENT_VERSION_PATH", DATA_DIR / "app-version.json")
)
DB_ROOT = Path(os.getenv("PRODUCTION_PLATFORM_DB_DIR", API_ROOT / "db-storage"))
DB_BUSINESS_DIR = Path(os.getenv("PRODUCTION_PLATFORM_DB_BUSINESS_DIR", DB_ROOT / "business"))
DB_SIMULATING_DIR = Path(
    os.getenv("PRODUCTION_PLATFORM_DB_SIMULATING_DIR", DB_ROOT / "simulating")
)
AUTH_DB_PATH = Path(
    os.getenv("PRODUCTION_PLATFORM_AUTH_DB_PATH", DB_ROOT / "auth" / "auth.sqlite3")
)

IS_WINDOWS = platform.system().lower() == 'windows'
IS_MAC = platform.system().lower() == 'darwin'


def get_active_db_dir() -> Path:
    """Return the sqlite profile directory for the current simulating mode."""
    from core.runtime_mode import is_simulating

    active = DB_SIMULATING_DIR if is_simulating() else DB_BUSINESS_DIR
    active.mkdir(parents=True, exist_ok=True)
    return active


def resolve_sqlite_path(filename: str, *, env_var: str | None = None) -> Path:
    """Resolve a named sqlite file under the active db profile."""
    if env_var:
        configured = os.getenv(env_var, "").strip()
        if configured:
            return Path(configured)
    return get_active_db_dir() / filename


def use_sqlite_persistence() -> bool:
    """Whether Mongo-backed features should use local sqlite instead."""
    from core.runtime_mode import is_simulating

    return is_simulating()


RUN_ENV = os.getenv("PRODUCTION_PLATFORM_RUN_ENV", "dev" if IS_WINDOWS or IS_MAC else "server").lower()
IS_DEV_ENV = RUN_ENV in ("dev", "local", "development")

AUTH_JWT_SECRET = os.getenv("PRODUCTION_PLATFORM_AUTH_JWT_SECRET", "").strip()
AUTH_JWT_ISSUER = os.getenv("PRODUCTION_PLATFORM_AUTH_JWT_ISSUER", "production-platform")
AUTH_JWT_AUDIENCE = os.getenv("PRODUCTION_PLATFORM_AUTH_JWT_AUDIENCE", "production-web")
AUTH_ACCESS_TOKEN_MINUTES = max(
    1, int(os.getenv("PRODUCTION_PLATFORM_AUTH_ACCESS_TOKEN_MINUTES", "20"))
)
AUTH_REFRESH_TOKEN_HOURS = max(
    1, int(os.getenv("PRODUCTION_PLATFORM_AUTH_REFRESH_TOKEN_HOURS", "8"))
)
AUTH_COOKIE_SECURE = os.getenv(
    "PRODUCTION_PLATFORM_AUTH_COOKIE_SECURE",
    "false" if IS_DEV_ENV else "true",
).lower() in {"1", "true", "yes", "on"}
AUTH_ALLOWED_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv("PRODUCTION_PLATFORM_AUTH_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
)

LOCAL_SERVER_HOST = os.getenv("PRODUCTION_PLATFORM_LOCAL_SERVER_HOST", "192.168.6.55")
SERVER_ENV_HOST = os.getenv("PRODUCTION_PLATFORM_SERVER_ENV_HOST", "localhost")
API_HOST = os.getenv(
    "PRODUCTION_PLATFORM_HOST",
    LOCAL_SERVER_HOST if IS_DEV_ENV else SERVER_ENV_HOST,
)

if IS_WINDOWS or IS_MAC:
    DOWNLOAD_DIR = os.path.join(DATA_DIR, "temp")
    TESTING_DATA_DIR = os.path.join(DATA_DIR, "testing_data")
    FILE_RESOURCE_DIR = os.path.join(DATA_DIR, "file_resources")
    CONFIG_DIR = os.path.join(API_ROOT, "configs")
else:
    DOWNLOAD_DIR = "/data/temp"
    TESTING_DATA_DIR = "/data/testing_data"
    FILE_RESOURCE_DIR = "/data/file_resources"
    CONFIG_DIR = "/configs"

FILE_RESOURCE_DIR = os.getenv("PRODUCTION_PLATFORM_FILE_RESOURCE_DIR", FILE_RESOURCE_DIR)
ROBOT_LOG_DOWNLOAD_DIR = os.getenv(
    "PRODUCTION_PLATFORM_ROBOT_LOG_DOWNLOAD_DIR",
    os.path.join(DOWNLOAD_DIR, "robot_logs"),
)

if IS_DEV_ENV:
    GOOGLE_AUTH_DIR = API_ROOT / "auth-files"
    ROBOT_KEY_PATH = os.path.join(GOOGLE_AUTH_DIR, "robot_key")
else:
    GOOGLE_AUTH_DIR = "/configs"
    if IS_WINDOWS or IS_MAC:
        ROBOT_KEY_PATH = os.path.join(API_ROOT, "configs", "robot_key")
    else:
        ROBOT_KEY_PATH = os.path.expanduser("~/robot_key")

ROBOT_KEY_PATH = os.getenv("PRODUCTION_PLATFORM_ROBOT_KEY_PATH", ROBOT_KEY_PATH)
ROBOT_TESTING_DATA_DIR = os.getenv("PRODUCTION_PLATFORM_ROBOT_TESTING_DATA_DIR", "/data/testing_data")
SLACK_CONFIG_PATH = os.getenv(
    "PRODUCTION_PLATFORM_SLACK_CONFIG_PATH",
    os.path.join(GOOGLE_AUTH_DIR, "slack.yaml"),
)

if IS_DEV_ENV:
    LOG_DIR = os.path.join(DATA_DIR, "logs")
else:
    LOG_DIR = "/var/log"

LOG_INFO_FILE = os.path.join(LOG_DIR, "production-backend-info.log")
LOG_ERROR_FILE = os.path.join(LOG_DIR, "production-backend-error.log")
LOG_FILE = LOG_INFO_FILE

LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB

MONGO_HOST = os.getenv("PRODUCTION_PLATFORM_MONGO_HOST", API_HOST)
MONGO_URI = os.getenv("PRODUCTION_PLATFORM_MONGO_URI", "")

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
ROBOT_LOG_DOWNLOAD_COLLECTION = "robot_log_download_records"
ROBOT_SSH_COMMAND_COLLECTION = "robot_ssh_commands"
ROBOT_VERSION_RECORD_COLLECTION = "robot_version_records"
PROTOCOL_MONITOR_ROOM_COLLECTION = "protocol_monitor_rooms"
AGENT_KNOWLEDGE_COLLECTION = "agent_knowledge"

# Version management, Duro, SOP, and workflow persistence.
# Defaults live under db-storage/business; simulating mode can switch via resolve_sqlite_path().
WORKFLOW_STORE_PATH = Path(
    os.getenv(
        "PRODUCTION_PLATFORM_WORKFLOW_DB_PATH",
        DB_BUSINESS_DIR / "workflows.sqlite3",
    )
)
SCHEDULER_POLL_SECONDS = float(os.getenv("PRODUCTION_PLATFORM_SCHEDULER_POLL_SECONDS", "5"))

GHELPER_DIR = Path(os.getenv("PRODUCTION_PLATFORM_GHELPER_DIR", API_ROOT / "ghelper-test"))
GOOGLE_TOKEN_PATH = Path(
    os.getenv("PRODUCTION_PLATFORM_GOOGLE_TOKEN_PATH", Path(GOOGLE_AUTH_DIR) / "token.json")
)
GOOGLE_CREDENTIALS_PATH = Path(
    os.getenv(
        "PRODUCTION_PLATFORM_GOOGLE_CREDENTIALS_PATH",
        Path(GOOGLE_AUTH_DIR) / "credentials.json",
    )
)
GOOGLE_API_TIMEOUT_SECONDS = int(os.getenv("PRODUCTION_PLATFORM_GOOGLE_API_TIMEOUT_SECONDS", "60"))
GOOGLE_PROXY_REFRESH_SECONDS = int(
    os.getenv("PRODUCTION_PLATFORM_GOOGLE_PROXY_REFRESH_SECONDS", "300")
)
GOOGLE_INTERACTIVE_AUTH = os.getenv("PRODUCTION_PLATFORM_GOOGLE_INTERACTIVE_AUTH", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

SOP_MASTER_SPREADSHEET_ID = os.getenv(
    "PRODUCTION_PLATFORM_SOP_SPREADSHEET_ID",
    "1BqkuAT27F_C-0sXlaqy-9AerJH4Er1LX8Llh-NoqOWI",
)
SOP_MASTER_SHEET_GID = int(os.getenv("PRODUCTION_PLATFORM_SOP_SHEET_GID", "991624078"))
SOP_MASTER_CACHE_SECONDS = int(os.getenv("PRODUCTION_PLATFORM_SOP_CACHE_SECONDS", "300"))
SOP_CACHE_PATH = Path(
    os.getenv("PRODUCTION_PLATFORM_SOP_CACHE_PATH", DB_BUSINESS_DIR / "sop_cache.sqlite3")
)
SOP_PDF_MAX_BYTES = int(os.getenv("PRODUCTION_PLATFORM_SOP_PDF_MAX_BYTES", str(30 * 1024 * 1024)))
SOP_PDF_MAX_TEXT_CHARS = int(os.getenv("PRODUCTION_PLATFORM_SOP_PDF_MAX_TEXT_CHARS", "500000"))
SOP_PDF_CACHE_SECONDS = int(os.getenv("PRODUCTION_PLATFORM_SOP_PDF_CACHE_SECONDS", "1800"))

DURO_BASE_URL = os.getenv("PRODUCTION_PLATFORM_DURO_BASE_URL", "https://mfgapi.duro.app").rstrip("/")
DURO_API_KEY = os.getenv("PRODUCTION_PLATFORM_DURO_API_KEY", "").strip()
DURO_TOKEN_PATH = Path(
    os.getenv("PRODUCTION_PLATFORM_DURO_TOKEN_PATH", Path(GOOGLE_AUTH_DIR) / "duro_token.txt")
)
DURO_COOKIES_PATH = Path(
    os.getenv("PRODUCTION_PLATFORM_DURO_COOKIES_PATH", Path(GOOGLE_AUTH_DIR) / "cookies.txt")
)
DURO_AUTH_URL = os.getenv("PRODUCTION_PLATFORM_DURO_AUTH_URL", "https://auth.duro.app").rstrip("/")
DURO_TOKEN_REFRESH_MARGIN_SECONDS = int(
    os.getenv("PRODUCTION_PLATFORM_DURO_TOKEN_REFRESH_MARGIN_SECONDS", "60")
)
DURO_REMOTE_CHROME_CDP_URL = os.getenv("PRODUCTION_PLATFORM_DURO_REMOTE_CHROME_URL", "").strip()
DURO_REMOTE_CHROME_APP_URL = os.getenv(
    "PRODUCTION_PLATFORM_DURO_REMOTE_CHROME_APP_URL",
    "https://mfg.duro.app/dashboard",
).strip()
DURO_REMOTE_CHROME_TIMEOUT_SECONDS = int(
    os.getenv("PRODUCTION_PLATFORM_DURO_REMOTE_CHROME_TIMEOUT_SECONDS", "30")
)
DURO_REMOTE_CHROME_AUTO_START = os.getenv(
    "PRODUCTION_PLATFORM_DURO_REMOTE_CHROME_AUTO_START", "true"
).lower() in {"1", "true", "yes", "on"}
DURO_TOKEN_AUTO_REFRESH_SECONDS = int(
    os.getenv("PRODUCTION_PLATFORM_DURO_TOKEN_AUTO_REFRESH_SECONDS", "30")
)
DURO_REQUEST_TIMEOUT_SECONDS = int(os.getenv("PRODUCTION_PLATFORM_DURO_TIMEOUT_SECONDS", "60"))
DURO_PRODUCT_CACHE_SECONDS = int(os.getenv("PRODUCTION_PLATFORM_DURO_PRODUCT_CACHE_SECONDS", "300"))
DURO_CACHE_PATH = Path(
    os.getenv("PRODUCTION_PLATFORM_DURO_CACHE_PATH", DB_BUSINESS_DIR / "duro_cache.sqlite3")
)

# Robot 设备配置
ROBOT_HEALTH_PORT = 31950
ROBOT_TEST_WORKING_DIRECTORY = os.getenv(
    "PRODUCTION_PLATFORM_ROBOT_TEST_WORKING_DIRECTORY",
    "/opt/opentrons-robot-server",
).strip() or "/opt/opentrons-robot-server"
ROBOT_SCAN_INTERVAL_SECONDS = int(os.getenv("PRODUCTION_PLATFORM_ROBOT_SCAN_INTERVAL_SECONDS", "180"))
ROBOT_SCAN_CONNECT_TIMEOUT_SECONDS = float(
    os.getenv("PRODUCTION_PLATFORM_ROBOT_SCAN_CONNECT_TIMEOUT_SECONDS", "0.5")
)
ROBOT_SCAN_HTTP_TIMEOUT_SECONDS = float(
    os.getenv("PRODUCTION_PLATFORM_ROBOT_SCAN_HTTP_TIMEOUT_SECONDS", "2")
)
ROBOT_SCAN_MAX_DURATION_SECONDS = int(
    os.getenv("PRODUCTION_PLATFORM_ROBOT_SCAN_MAX_DURATION_SECONDS", "120")
)
ROBOT_LOG_DOWNLOAD_MAX_WORKERS = max(
    1,
    min(16, int(os.getenv("PRODUCTION_PLATFORM_ROBOT_LOG_DOWNLOAD_MAX_WORKERS", "8"))),
)
ROBOT_LOG_COMMAND_TIMEOUT_SECONDS = max(
    60,
    int(os.getenv("PRODUCTION_PLATFORM_ROBOT_LOG_COMMAND_TIMEOUT_SECONDS", "900")),
)
ROBOT_LOG_REMOTE_TEMP_ROOT = os.getenv(
    "PRODUCTION_PLATFORM_ROBOT_LOG_REMOTE_TEMP_ROOT",
    "/data",
).rstrip("/") or "/data"
ROBOT_LOG_CLEANUP_RETRY_INTERVAL_SECONDS = max(
    10,
    int(os.getenv("PRODUCTION_PLATFORM_ROBOT_LOG_CLEANUP_RETRY_INTERVAL_SECONDS", "30")),
)
ROBOT_LOG_CLEANUP_RETRY_ATTEMPTS = max(
    1,
    int(os.getenv("PRODUCTION_PLATFORM_ROBOT_LOG_CLEANUP_RETRY_ATTEMPTS", "120")),
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
    os.makedirs(ROBOT_LOG_DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if IS_DEV_ENV:
        os.makedirs(GOOGLE_AUTH_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)


# 自动创建目录
ensure_directories()
