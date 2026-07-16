import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_ROOT.parents[1]
DATA_DIR = Path(os.getenv("PRODUCTIONS_VERSIONS_DATA_DIR", PROJECT_ROOT / "data"))
WORKFLOW_STORE_PATH = DATA_DIR / "workflows.json"
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
GOOGLE_API_TIMEOUT_SECONDS = int(os.getenv("PRODUCTIONS_VERSIONS_GOOGLE_API_TIMEOUT_SECONDS", "180"))
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
SOP_MASTER_CACHE_SECONDS = int(os.getenv("PRODUCTIONS_VERSIONS_SOP_CACHE_SECONDS", "300"))
SOP_PDF_MAX_BYTES = int(os.getenv("PRODUCTIONS_VERSIONS_SOP_PDF_MAX_BYTES", str(30 * 1024 * 1024)))
SOP_PDF_MAX_TEXT_CHARS = int(os.getenv("PRODUCTIONS_VERSIONS_SOP_PDF_MAX_TEXT_CHARS", "500000"))
SOP_PDF_CACHE_SECONDS = int(os.getenv("PRODUCTIONS_VERSIONS_SOP_PDF_CACHE_SECONDS", "1800"))

DURO_BASE_URL = os.getenv("PRODUCTIONS_VERSIONS_DURO_BASE_URL", "https://mfg.duro.app").rstrip("/")
DURO_TOKEN_PATH = Path(
    os.getenv("PRODUCTIONS_VERSIONS_DURO_TOKEN_PATH", PROJECT_ROOT / "auth" / "duro_token.txt")
)
DURO_REQUEST_TIMEOUT_SECONDS = int(os.getenv("PRODUCTIONS_VERSIONS_DURO_TIMEOUT_SECONDS", "60"))
DURO_PRODUCT_CACHE_SECONDS = int(os.getenv("PRODUCTIONS_VERSIONS_DURO_PRODUCT_CACHE_SECONDS", "300"))
