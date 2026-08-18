from modules.duro.client import DuroClient
from modules.duro.service import DuroService
from core.config import DURO_CACHE_PATH


duro_client = DuroClient()
duro_service = DuroService(duro_client, cache_path=DURO_CACHE_PATH)
