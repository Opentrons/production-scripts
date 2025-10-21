from fastapi import APIRouter
from files_server.api.model import *
from google_driver_handler.upload_to_googledrive.base import UploadToGoogleDrive
from google_driver_handler.upload_to_googledrive.data_center_utils import get_sheet_name_by_testname

router = APIRouter()


@router.post('/upload/report', status_code=200)
async def google_drive_update_data(_request: FileUploadRequest):
    """
    update data
    """
    try:
        product_name = _request.product_name
        quarter = _request.quarter_name
        sn = _request.sn
        file_list = _request.files_list
        test_name = _request.test_name
        test_name_list = []
        finished = _request.finished
        sheet_name = get_sheet_name_by_testname(test_name, finished)
        if isinstance(test_name, str):
            test_name_list.append(test_name)
        else:
            test_name_list = test_name
        ug = UploadToGoogleDrive(product_name)
        error = ug.error
        if error is None:
            for test_name in test_name_list:
                file_path_list = file_list[test_name]
                for file_path in file_path_list:
                    ug.upload_production_data(quarter, sn, file_path, sheet_name)
            _message = "success"
            success = True
        else:
            success = False
            _message = error
    except Exception as e:
        _message = _message
        success = False

    return {
        "success": success,
        "message": _message,
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
