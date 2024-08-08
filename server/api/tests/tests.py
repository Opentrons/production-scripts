from fastapi import Depends, FastAPI, HTTPException, APIRouter
from typing import List
from api.tests.models import *
from ot_type import Mount, Point
from utils import Utils, create_id
from utils import write_local_json, read_local_json

router = APIRouter()

database_path = 'database/tests.json'


@router.get('/get/runs', status_code=200)
async def get_runs(type):
    """
    get run
    :return:
    """
    ret = read_local_json(database_path)
    form_list = ret[type]
    return {
        "success": True,
        "data": form_list
    }


@router.post('/create/run', status_code=200)
async def create_run(create_detail: newRunCommandParam):
    """
    test online
    :param test_online:
    :return:
    """
    create_detail = create_detail.params
    production = create_detail.production
    detail = {
        "date": create_detail.date,
        "auth": create_detail.auth,
        "robot_name": create_detail.robot_name,
        "device_ip": create_detail.device_ip,
        "use_key": create_detail.use_key,
        "description": create_detail.description,
        "cmd": create_detail.cmd,
        "type": create_detail.type,
        "params": create_detail.params,
        "id": create_id()
    }
    ret = read_local_json(database_path)
    ret[production].append(detail)
    write_local_json(database_path, ret)
    return ({
        "success": True,
        "message": "新建成功",
        "detail": detail
    })
