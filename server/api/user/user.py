from fastapi import Depends, FastAPI, HTTPException, APIRouter
from api.user.models import *
from utils import write_local_json, read_local_json
import time
from user.auth import AuthHandler

register_path = 'database/register.json'

router = APIRouter()
auth_handler = AuthHandler()

def _register():
    pass


@router.post('/register', status_code=201)
def register(auth_details: UserMessage):
    auth_details = auth_details.params
    register: dict = read_local_json(register_path)
    users = list(register.values())
    if any(x['username'] == auth_details.username for x in users):
        raise HTTPException(status_code=400, detail='Username is taken')
    hashed_password = auth_handler.get_password_hash(auth_details.password)
    register.update({str(time.time()): {'username': auth_details.username, 'password': hashed_password}})
    write_local_json(register_path, register)
    return {"success": True,
            'message': "register successful"}


@router.post('/login', status_code=201)
def login(params: UserMessage):
    auth_details = params.params
    register: dict = read_local_json(register_path)
    users = list(register.values())
    user = None
    for x in users:
        if x['username'] == auth_details.username:
            user = x
            break
    if (user is None) or (not auth_handler.verify_password(auth_details.password, user['password'])):
        return {"success": False,
                "message": "用户名或密码不存在"}
    token = auth_handler.encode_token(user['username'])
    return {"success": True,
            "message": "登录成功！",
            'token': token}
