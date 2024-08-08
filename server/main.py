from fastapi import FastAPI, APIRouter
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from server.user.auth import AuthHandler
from server.api.user import user
from server.api.hardware import hardware
from server.api.device import device
from server.api.tests import tests
from server.api.files import files

api_router = APIRouter()

api_router.include_router(user.router, prefix='/user')
api_router.include_router(hardware.router, prefix='/device')
api_router.include_router(device.router, prefix='/device')
api_router.include_router(tests.router, prefix='/tests')
api_router.include_router(files.router, prefix='/files')

app = FastAPI()
app.include_router(api_router)

# 添加跨域中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/connection", status_code=201)
async def say_hi():
    return {"message": 'connection is OK !',
            "success": True}


def start_sever():
    uvicorn.run(app, host='127.0.0.1', port=8080)


if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8080)
