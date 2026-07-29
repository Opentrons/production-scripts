from google_driver import GoogleDriver
from settings import SOP_CACHE_PATH
from sop.service import SopService


google_driver = GoogleDriver()
sop_service = SopService(google_driver, cache_path=SOP_CACHE_PATH)
