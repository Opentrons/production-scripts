from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.router import router as api_router
from core.lifecycle import lifespan


app = FastAPI(
    title="Productions testing API",
    version="1.0.0",
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
def read_root():
    return {"message": "Productions testing API is running", "success": True}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8090, reload=True)
