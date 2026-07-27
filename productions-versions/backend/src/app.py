from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as api_router
from duro.runtime import duro_browser_token_provider, ensure_duro_remote_chrome_running
from google_driver.proxy_manager import google_proxy_manager
from settings import DURO_TOKEN_AUTO_REFRESH_SECONDS
from workflows.runtime import workflow_scheduler, workflow_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    google_proxy_manager.start()
    ensure_duro_remote_chrome_running()
    if duro_browser_token_provider is not None:
        duro_browser_token_provider.start_auto_refresh(DURO_TOKEN_AUTO_REFRESH_SECONDS)
    workflow_service.initialize()
    workflow_scheduler.start()
    try:
        yield
    finally:
        workflow_scheduler.stop()
        google_proxy_manager.stop()
        if duro_browser_token_provider is not None:
            duro_browser_token_provider.close()


app = FastAPI(
    title="Productions Versions API",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")


@app.get("/")
def read_root() -> dict[str, object]:
    return {
        "message": "Productions Versions API is running",
        "success": True,
    }
