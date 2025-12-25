from files_server.remote import build_handler
from fastapi import HTTPException, APIRouter
from datetime import datetime
from files_server.api.model import *
from fastapi.responses import JSONResponse, FileResponse
import os
from files_server.utils.main import zip_directory, delete_folder
import platform
from files_server.services.download_report_handler.download_files import get_time_str

router = APIRouter()
system = platform.system().lower()

if system == 'linux':
    LOCAL_PATH = '/files_server/datas'
else:
    LOCAL_PATH = './data'


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
                "message": "连接成功", }
    else:
        return {"success": False,
                "message": "连接失败", }


@router.post('/download/testing_data', status_code=200)
async def download_testing_data(data: DownloadRequest):
    """
    Download files as a stream
    Returns:
        StreamingResponse: The ZIP file as a downloadable stream
    """
    host = data.host
    user_name = data.user_name
    download_path = data.download_path
    saved_name = data.saved_name

    local_path = os.path.join(LOCAL_PATH, saved_name).replace('\\', '/')

    dh = build_handler(host, user_name)
    ret, message = dh.connect()

    if not ret:
        raise HTTPException(status_code=404, detail=message)
    try:
        ret, message, local_dir = dh.download_dir(download_path, local_path)
        rename_dir = local_dir + "_" + get_time_str()
        dh.re_name_dir(local_path, rename_dir)

        if not ret:
            raise HTTPException(status_code=404, detail=message)
        dh.close()
        # Zip the directory
        zip_path = f"{rename_dir}.zip"
        zip_directory(local_dir, zip_path)
        delete_folder(local_dir)
        if '\\' in zip_path:
            zip_path = zip_path.replace('\\', '/')
        saved_name = zip_path.split('/')[-1]
        # Return the file as a stream
        if os.path.exists(zip_path):
            # Method 1: Using FileResponse (simpler)
            return FileResponse(
                zip_path,
                filename=saved_name,
                media_type='application/zip',
                headers={'Content-Disposition': f'attachment; filename="{saved_name}"',
                         "Access-Control-Expose-Headers": "Content-Disposition"}
            )
        else:
            raise HTTPException(status_code=404, detail="ZIP file not found")
    except HTTPException as e:
        raise HTTPException(status_code=404, detail=e)


@router.get('/discover', status_code=200)
async def flex_discover():
    """
    scan flex
    """
    from files_server.services.flex_communications.discover_flex import scan_flex
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
