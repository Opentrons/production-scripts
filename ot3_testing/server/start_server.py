import uvicorn
from fastapi import FastAPI, APIRouter, status
from server.engine.router import engine_router
from server.testing.router import testing_router

api_router = APIRouter()

api_router.include_router(engine_router, prefix="/engine")
api_router.include_router(testing_router, prefix="/testing")

app = FastAPI()
app.include_router(api_router, prefix='/api')

@app.get(
    "/system/info",
    summary="Get system information",
    description="get versions and author",
    responses={
        status.HTTP_200_OK: {"message": "OK"},
        status.HTTP_403_FORBIDDEN: {"message": "FORBIDDEN"},
    },
)
async def get_system_info():
    return {"version": "2024-1-30-A01",
            "contact": "andy.hu@opentrons.com"}


if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=8888)
