from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from files_server.api.download_files import router as download_router

api_router = APIRouter()

app = FastAPI()
app.include_router(api_router)
app.include_router(download_router, prefix='/api')

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
    uvicorn.run(app, host='127.0.0.1', port=8080)


if __name__ == '__main__':
    start_sever()
