
from files_server.remote import build_handler
from fastapi import Depends, FastAPI, HTTPException, APIRouter
from typing import List
from files_server.api.model import *

router = APIRouter()

LOCAL_PATH = '/files_server/data'


@router.post('/download/testing_data', status_code=200)
async def download_testing_data(data: DownloadRequest):
    """
    download files
    :return
    """
    host = data.host
    user_name = data.user_name
    download_path = data.download_path

    dh = build_handler(host, user_name)
    ret = dh.download_dir(download_path, LOCAL_PATH)
    return {
        "success": ret,
        "device": ret["pass"]
    }

@router.get('/discover', status_code=200)
async def flex_discover():
    """
    scan flex
    """
    return {
        "success": True,
        "message": "undo"
    }

@router.post('/update/date', status_code=200)
async def flex_update_date():
    """
    update date of flex
    """
    return {
        "success": True,
        "message": "undo"
    }

@router.post('/run/script', status_code=200)
async def flex_run_script():
    """
    update date of flex
    """
    return {
        "success": True,
        "message": "undo"
    }