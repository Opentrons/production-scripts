from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as api_router
from workflows.runtime import workflow_scheduler, workflow_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    workflow_service.initialize()
    workflow_scheduler.start()
    try:
        yield
    finally:
        workflow_scheduler.stop()


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
