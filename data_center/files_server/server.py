from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from files_server.api.api_flex import router as flex_router
from files_server.api.api_google_drive import router as google_drive_router
from files_server.api.api_user import router as user_router

api_router = APIRouter()

app = FastAPI()
app.include_router(api_router)
app.include_router(flex_router, prefix='/api/flex')
app.include_router(google_drive_router, prefix='/api/google/drive')
app.include_router(user_router, prefix='/api/user')

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
