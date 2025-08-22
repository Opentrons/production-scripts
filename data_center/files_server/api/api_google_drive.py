from files_server.remote import build_handler
from fastapi import Depends, FastAPI, HTTPException, APIRouter
from typing import List
from files_server.api.model import *
from google_driver_handler.upload_to_googledrive.base import UploadToGoogleDrive

router = APIRouter()


@router.post('/upload/report', status_code=200)
async def google_drive_update_data(_request: FileUploadRequest):
    """
    update data
    """
    product_name = _request.product_name
    quarter = _request.quarter_name
    sn = _request.sn
    file_list = _request.files_list
    test_name = _request.test_name
    test_name_list = []
    if isinstance(test_name, str):
        test_name_list.append(test_name)
    else:
        test_name_list = test_name
    ug = UploadToGoogleDrive(product_name)
    for test_name in test_name_list:
        file_path_list = file_list[test_name]
        for file_path in file_path_list:
            ug.upload_production_data(quarter, sn, file_path, test_name)

    return {
        "success": True,
        "message": "success",
    }


@router.post('/copy/file', status_code=200)
async def google_drive_copy_file():
    """
    update date of flex
    """
    return {
        "success": True,
        "message": "undo"
    }


@router.post('/delete/file', status_code=200)
async def google_drive_delete_file():
    """
    update date of flex
    """
    return {
        "success": True,
        "message": "undo"
    }


@router.post('/fill/cell', status_code=200)
async def google_drive_fill_cell():
    """
    update date of flex
    """
    return {
        "success": True,
        "message": "undo"
    }
