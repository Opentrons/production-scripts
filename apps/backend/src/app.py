from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core import config
from core.lifecycle import lifespan
from api.router import router as api_router


app = FastAPI(
    title="Productions testing API",
    version="1.0.0",
    lifespan=lifespan,
)

if config.AUTH_ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.AUTH_ALLOWED_ORIGINS),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )

app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Productions testing API is running", "success": True}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8090, reload=True)
