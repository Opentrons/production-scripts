from fastapi import Depends, FastAPI, HTTPException, APIRouter
from datetime import datetime
from files_server.api.model import *
from datetime import timedelta
from files_server.utils.token import create_access_token


router = APIRouter()

@router.post('/login', status_code=200)
async def login(login_form: UserLoginRequest):
    # TODO：临时账户密码验证，应该用数据验证账户
    user_name = login_form.username
    password = login_form.password
    if user_name == '12345678' and password == '12345678':
        # 2. 生成 Token
        access_token_expires = timedelta(minutes=120)
        access_token = create_access_token(
            data={"sub": user_name},  # sub 是 JWT 标准字段
            expires_delta=access_token_expires
        )
        return {
            "user": user_name,
            "access_token": access_token,
            "token_type": "bearer",
            "success": True,
            "message": "success"
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="用户名或密码错误"
        )







