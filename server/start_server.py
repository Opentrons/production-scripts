import uvicorn
from fastapi import FastAPI, APIRouter, status
from server.engine.router import engine_router
from server.testing.router import testing_router
import os
import subprocess

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


def start_server():
    # back end
    uvicorn.run(app, host="127.0.0.1", port=8888)
    # fore end

    # cmd = f'pyinstaller -F --ico="assets/logo.ico"  --name=Productions-{VERSION} production_scripts.py'
    # process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    # while True:
    #     line = process.stdout.readline()
    #     if not line:
    #         break  # 如果没有读取到数据，表示子进程已经结束，退出循环
    #     else:
    #         print(line, end='')  # 实时打印输出
    # process.wait()
    


