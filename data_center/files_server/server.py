import time
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from files_server.api.api_flex import router as flex_router
from files_server.api.api_google_drive import router as google_drive_router
from files_server.api.api_user import router as user_router
from files_server.api.api_db import router as db_router
from files_server.api.api_files import router as files_router
from files_server.settings.logs import setup_logging
from files_server.services.download_report_handler.download_files import LinuxFileManager
from threading import Thread
from files_server.settings.logs import get_logger
import platform
import  os

# 开启logger
setup_logging()
logger = get_logger("server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # start up
    logger.info("Start Download Cycling")

    def run_in_thread():
        LinuxFileManager.download_load_and_upload_cycling()
        time.sleep(3)

    thread = Thread(target=run_in_thread, daemon=True)
    thread.start()
    yield


api_router = APIRouter()

app = FastAPI(lifespan=lifespan)

if platform.system() == "Linux":
    # 挂载log静态文件
    log_dir = "/opt/data-center-server/logs/"
    if os.path.exists(log_dir) and os.path.isdir(log_dir):
        # 使用更明确的配置
        app.mount(
            "/logs",
            StaticFiles(
                directory=log_dir,
                html=True  # 如果希望显示目录列表
            ),
            name="logs_static"
        )

app.include_router(api_router)
app.include_router(flex_router, prefix='/api/flex')
app.include_router(google_drive_router, prefix='/api/google/drive')
app.include_router(user_router, prefix='/api/user')
app.include_router(db_router, prefix='/api/db')
app.include_router(files_router, prefix='/api/files')

_is_simulate = True

# 添加跨域中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

__VERSION__ = '1.0.0'


@app.get("/version", status_code=201)
async def get_version():
    return {"message": 'connection is OK !',
            "version": __VERSION__,
            "success": True}


def start_sever():
    uvicorn.run(app, host='0.0.0.0', port=8080)


if __name__ == '__main__':
    start_sever()
