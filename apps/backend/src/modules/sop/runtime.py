from core.google import GoogleDriver
from core.config import SOP_CACHE_PATH
from modules.sop.service import SopService


google_driver = GoogleDriver()
sop_service = SopService(google_driver, cache_path=SOP_CACHE_PATH)
