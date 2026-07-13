from contextlib import asynccontextmanager
import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as api_router
from api.services.robots import shutdown_robot_service
from api.services.upload import shutdown_upload_service
from database.mongodb import mongodb
from settings import get_logger
from upload_handler.drivers.google_drive import GoogleDriveDriver, refresh_best_proxy_config
from upload_handler.utils import runtime_config
import uvicorn

logger = get_logger(__name__)


def should_refresh_proxy_on_startup() -> bool:
    raw_value = os.getenv("DATA_HANDLER_REFRESH_PROXY_ON_STARTUP", "true")
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongodb.connect()
    if runtime_config.USE_PROXY and should_refresh_proxy_on_startup():
        try:
            await asyncio.to_thread(refresh_best_proxy_config)
        except Exception as exc:
            logger.warning("Startup proxy refresh failed: %s", exc)
    try:
        yield
    finally:
        shutdown_robot_service()
        shutdown_upload_service()
        GoogleDriveDriver.shutdown_shared_services()
        mongodb.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "FastAPI server is running",
    "success": True}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8090, reload=True)
