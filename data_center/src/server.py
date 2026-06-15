import os
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from .settings import settings
from .this_types import OS
from .api.api_flex import router as flex_router
from .api.api_user import router as user_router
from .api.api_db import router as db_router
from .api.api_files import router as files_router
from .settings.logs import setup_logging
from threading import Thread
from .settings.logs import get_logger
import fastapi
from .services import ServiceHandler
import asyncio

__VERSION__ = '1.0.0'
logger = get_logger("server")

@asynccontextmanager
async def lifespan(_app: fastapi.FastAPI):
    try:
        logger.info(f"setting logger to {settings.log_file}")
        setup_logging()
        logger.info(f"start server")
        logger.info("starting to init lifespan")
        instance = ServiceHandler()
        _app.state.instance = instance
        logger.info("initial instance successful")
        # start cycling
        def run_in_thread():
            asyncio.run(instance.download_and_upload_cycling())
        thread = Thread(target=run_in_thread, daemon=True)
        thread.start()
        yield
        logger.info("shut down server")
        if hasattr(app.state, "instance"):
            app.state.instance.close()
    except Exception as e:
        logger.error(e)
        raise


api_router = APIRouter()
app = FastAPI(lifespan=lifespan,
              title="Opentrons Testing EndPoint",
              version=__VERSION__,
              description="Opentrons Testing EndPoint",)

# 挂载log静态文件
if settings.os == OS.Linux:
    log_dir = settings.log_file
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

@app.get("/version", status_code=201)
async def get_version():
    return {"message": 'connection is OK !',
            "version": __VERSION__,
            "success": True}


def start_sever():
    uvicorn.run(app, host='0.0.0.0', port=8090)


if __name__ == '__main__':
    start_sever()
