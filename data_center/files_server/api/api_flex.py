from files_server.remote import build_handler
from fastapi import Depends, FastAPI, HTTPException, APIRouter
from datetime import datetime
from files_server.api.model import *
import subprocess
from fastapi.responses import JSONResponse
import os
from files_server.utils.utils import zip_directory, delete_folder

router = APIRouter()

LOCAL_PATH = '/files_server/datas'


@router.post('/connect', status_code=201)
async def connect(request: RobotRequest):
    """
    connect ot3
    """
    host = request.host
    dh = build_handler(host, 'root')
    ret = dh.connect()
    if ret[0]:
        return {"success": True,
                "message": "连接成功",}
    else:
        return {"success": False,
                "message": "连接失败",}




@router.post('/download/testing_data', status_code=200)
async def download_testing_data(data: DownloadRequest):
    """
    download files
    :return
    """
    host = data.host
    user_name = data.user_name
    download_path = data.download_path
    saved_name = data.saved_name
    local_path = os.path.join(LOCAL_PATH, saved_name)
    if '\\' in local_path:
        local_path = local_path.replace('\\', '/')
    dh = build_handler(host, user_name)
    ret, message = dh.connect()
    if ret:
        ret, message, local_dir = dh.download_dir(download_path, local_path)
        # zip and delete
        zip_directory(local_dir, local_dir)
        delete_folder(local_dir)
        return {
            "success": ret,
            "message": message,
            "dir": local_dir
        }
    else:
        data = {"success": ret, "message": message}
        return JSONResponse(data, status_code=404)


@router.get('/discover', status_code=200)
async def flex_discover():
    """
    scan flex
    """
    from download_report_handler.discover_flex import scan_flex
    flex_group = scan_flex()
    return {
        "success": True,
        "message": "done",
        "flex_group": flex_group
    }


@router.post('/update/date', status_code=200)
async def flex_update_date(robot_request: RobotRequest):
    """
    update date of flex
    """
    host_name = robot_request.host
    dh = build_handler(host_name, 'root')
    ret, message = dh.connect()
    new_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if ret:
        output = dh.update_date(new_time)
        return {
            "success": True,
            "message": "success",
            'date': output
        }
    else:
        data = {
            "success": False,
            "message": message,
            "date": ""
        }
        return JSONResponse(data, status_code=403)


@router.post('/run/script', status_code=200)
async def flex_run_script(script_request: RunScriptResponse):
    """
    update date of flex
    """
    script = script_request.script
    host_name = script_request.host

    dh = build_handler(host_name, 'root')
    ret, message = dh.connect()
    if ret:
        output = dh.run_script(script)
        return {
            "success": True,
            "message": "success",
            "script": output

        }
    else:
        data = {"success": False, "message": message, "script": ""}
        return JSONResponse(data, status_code=403)
