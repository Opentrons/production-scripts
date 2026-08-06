import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_ROOT.parents[1]


def _load_local_env() -> None:
    """Load the backend .env without overriding explicitly exported values."""

    env_path = PROJECT_ROOT / ".env"
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

DATA_DIR = Path(os.getenv("PRODUCTIONS_VERSIONS_DATA_DIR", PROJECT_ROOT / "data"))
WORKFLOW_STORE_PATH = Path(
    os.getenv("PRODUCTIONS_VERSIONS_WORKFLOW_DB_PATH", DATA_DIR / "workflows.sqlite3")
)
WORKFLOW_LEGACY_STORE_PATH = DATA_DIR / "workflows.json"
SCHEDULER_POLL_SECONDS = float(os.getenv("PRODUCTIONS_VERSIONS_SCHEDULER_POLL_SECONDS", "5"))


def _runtime_directory(
    environment_name: str,
    local_directory: Path,
    fallback_directory: Path,
    marker_name: str,
) -> Path:
    configured = os.getenv(environment_name)
    if configured:
        return Path(configured).expanduser().resolve()
    if (local_directory / marker_name).exists():
        return local_directory
    return fallback_directory


OPENTRONS_BACKEND_ROOT = REPOSITORY_ROOT / "productions-opentrons" / "backend"
GOOGLE_AUTH_DIR = _runtime_directory(
    "PRODUCTIONS_VERSIONS_GOOGLE_AUTH_DIR",
    PROJECT_ROOT / "auth",
    OPENTRONS_BACKEND_ROOT / "auth",
    "token.json",
)
GHELPER_DIR = _runtime_directory(
    "PRODUCTIONS_VERSIONS_GHELPER_DIR",
    PROJECT_ROOT / "ghelper-test",
    OPENTRONS_BACKEND_ROOT / "ghelper-test",
    "skill_config.json",
)
GOOGLE_TOKEN_PATH = Path(os.getenv("PRODUCTIONS_VERSIONS_GOOGLE_TOKEN_PATH", GOOGLE_AUTH_DIR / "token.json"))
GOOGLE_CREDENTIALS_PATH = Path(
    os.getenv("PRODUCTIONS_VERSIONS_GOOGLE_CREDENTIALS_PATH", GOOGLE_AUTH_DIR / "credentials.json")
)
GOOGLE_API_TIMEOUT_SECONDS = int(os.getenv("PRODUCTIONS_VERSIONS_GOOGLE_API_TIMEOUT_SECONDS", "60"))
GOOGLE_PROXY_REFRESH_SECONDS = int(
    os.getenv("PRODUCTIONS_VERSIONS_GOOGLE_PROXY_REFRESH_SECONDS", "300")
)
GOOGLE_INTERACTIVE_AUTH = os.getenv("PRODUCTIONS_VERSIONS_GOOGLE_INTERACTIVE_AUTH", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

SOP_MASTER_SPREADSHEET_ID = os.getenv(
    "PRODUCTIONS_VERSIONS_SOP_SPREADSHEET_ID",
    "1BqkuAT27F_C-0sXlaqy-9AerJH4Er1LX8Llh-NoqOWI",
)
SOP_MASTER_SHEET_GID = int(os.getenv("PRODUCTIONS_VERSIONS_SOP_SHEET_GID", "991624078"))
# Legacy compatibility settings; SOP caches are persistent and refresh manually.
SOP_MASTER_CACHE_SECONDS = int(os.getenv("PRODUCTIONS_VERSIONS_SOP_CACHE_SECONDS", "300"))
SOP_CACHE_PATH = Path(os.getenv("PRODUCTIONS_VERSIONS_SOP_CACHE_PATH", DATA_DIR / "sop_cache.sqlite3"))
SOP_PDF_MAX_BYTES = int(os.getenv("PRODUCTIONS_VERSIONS_SOP_PDF_MAX_BYTES", str(30 * 1024 * 1024)))
SOP_PDF_MAX_TEXT_CHARS = int(os.getenv("PRODUCTIONS_VERSIONS_SOP_PDF_MAX_TEXT_CHARS", "500000"))
SOP_PDF_CACHE_SECONDS = int(os.getenv("PRODUCTIONS_VERSIONS_SOP_PDF_CACHE_SECONDS", "1800"))

# Duro's browser client talks directly to the API origin.  Keep the public
# application host as an explicit override for environments that proxy /v1.
DURO_BASE_URL = os.getenv("PRODUCTIONS_VERSIONS_DURO_BASE_URL", "https://mfgapi.duro.app").rstrip("/")
DURO_API_KEY = os.getenv("DURO_API_KEY", "").strip()
DURO_TOKEN_PATH = Path(
    os.getenv("PRODUCTIONS_VERSIONS_DURO_TOKEN_PATH", PROJECT_ROOT / "auth" / "duro_token.txt")
)
DURO_COOKIES_PATH = Path(
    os.getenv("PRODUCTIONS_VERSIONS_DURO_COOKIES_PATH", PROJECT_ROOT / "auth" / "cookies.txt")
)
DURO_AUTH_URL = os.getenv("PRODUCTIONS_VERSIONS_DURO_AUTH_URL", "https://auth.duro.app").rstrip("/")
DURO_TOKEN_REFRESH_MARGIN_SECONDS = int(
    os.getenv("PRODUCTIONS_VERSIONS_DURO_TOKEN_REFRESH_MARGIN_SECONDS", "60")
)
DURO_REMOTE_CHROME_CDP_URL = os.getenv(
    "PRODUCTIONS_VERSIONS_DURO_REMOTE_CHROME_URL",
    "",
).strip()
DURO_REMOTE_CHROME_APP_URL = os.getenv(
    "PRODUCTIONS_VERSIONS_DURO_REMOTE_CHROME_APP_URL",
    "https://mfg.duro.app/dashboard",
).strip()
DURO_REMOTE_CHROME_TIMEOUT_SECONDS = int(
    os.getenv("PRODUCTIONS_VERSIONS_DURO_REMOTE_CHROME_TIMEOUT_SECONDS", "30")
)
DURO_REMOTE_CHROME_AUTO_START = os.getenv(
    "PRODUCTIONS_VERSIONS_DURO_REMOTE_CHROME_AUTO_START", "true"
).lower() in {"1", "true", "yes", "on"}
DURO_TOKEN_AUTO_REFRESH_SECONDS = int(
    os.getenv("PRODUCTIONS_VERSIONS_DURO_TOKEN_AUTO_REFRESH_SECONDS", "30")
)
DURO_REQUEST_TIMEOUT_SECONDS = int(os.getenv("PRODUCTIONS_VERSIONS_DURO_TIMEOUT_SECONDS", "60"))
# Legacy compatibility setting; Duro SQLite entries no longer expire automatically.
DURO_PRODUCT_CACHE_SECONDS = int(os.getenv("PRODUCTIONS_VERSIONS_DURO_PRODUCT_CACHE_SECONDS", "300"))
DURO_CACHE_PATH = Path(os.getenv("PRODUCTIONS_VERSIONS_DURO_CACHE_PATH", DATA_DIR / "duro_cache.sqlite3"))
