from fastapi import HTTPException, APIRouter, UploadFile, File
from starlette.responses import FileResponse

from files_server.api.model import *
import platform
system = platform.system()

import os
from typing import List, Dict
import mimetypes
import time
from files_server.services.download_report_handler.testing_data_ana import Ana
from files_server.utils.main import require_config

__config = require_config()

UPLOAD_DIR = __config["files_uploads"]
UPLOAD_DIR_TestingData = __config["files_saving"]

def check_system_dir_call_back():
    global UPLOAD_DIR
    global UPLOAD_DIR_TestingData
    try:
        if system == "Linux":
            upload_dir = '/files_server/uploads'
            upload_dir_testing_data = '/files_server/datas/testing_data'
        else:
            upload_dir = './data'
            upload_dir_testing_data = './datas/testing_data'
        if os.path.exists(upload_dir):
            pass
        else:
            os.makedirs(upload_dir)
        if os.path.exists(upload_dir_testing_data):
            pass
        else:
            os.makedirs(upload_dir_testing_data)
        UPLOAD_DIR = upload_dir
        UPLOAD_DIR_TestingData = upload_dir_testing_data
        return UPLOAD_DIR, UPLOAD_DIR_TestingData
    except Exception as e:
        raise e
    

def get_file_info(directory: str = UPLOAD_DIR) -> List[Dict[str, str]]:
    """
    获取目录下所有文件信息

    Args:
        directory: 要扫描的目录路径

    Returns:
        List[Dict]: 包含文件信息的字典列表
    """
    file_list = []

    # 确保目录存在
    if not os.path.exists(directory):
        raise FileNotFoundError(f"Directory not found: {directory}")

    # 遍历目录
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)

        # 只处理文件，忽略子目录
        if os.path.isfile(file_path):
            # 获取文件状态
            stat = os.stat(file_path)

            # 获取MIME类型
            mime_type, _ = mimetypes.guess_type(filename)

            # 构造文件信息字典
            file_info = {
                "name": filename,
                "url": f"{UPLOAD_DIR}/{filename}",  # 替换为你的实际URL前缀
                "size": stat.st_size,
                "type": mime_type if mime_type else "application/octet-stream",
                "modified": time.strftime("%Y-%m-%d", time.localtime(stat.st_mtime))
            }

            file_list.append(file_info)

    return file_list


router = APIRouter()

@router.get(path='/fetch/filelist')
def fetch_filelist():
    ret = get_file_info()
    if not ret:
        return HTTPException(status_code=404, detail="File not found")
    else:
        return {
          "success": True,
          "message": "successful",
          "files": ret
        }


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    单文件上传接口
    """
    try:
        # 保存文件到本地
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())

        return {
            "status": "success",
            "file_path": file_path,
            "filename": file.filename,
            "size": file.size,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload/testing_data")
async def upload_file(file: UploadFile = File(...)):
    """
    文件上传接口
    """
    check_system_dir_call_back()
    try:
        # 保存文件到本地
        file_path = os.path.join(UPLOAD_DIR_TestingData, file.filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        ana = Ana(file_path)
        files_list = ana.ana_testing_data_zip()
        return {
            "status": "success",
            "files_list": files_list,
            "filename": file.filename,
            "size": file.size,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/download")
async def download_file(download_request:FileDownloadRequest):
    url = download_request.url
    file_name = download_request.file_name
    print(url)
    if os.path.exists(url):
        # Method 1: Using FileResponse (simpler)
        return FileResponse(
            url,
            filename=file_name,
            media_type='application/zip',
            headers={'Content-Disposition': f'attachment; filename="{file_name}"',
                     "Access-Control-Expose-Headers": "Content-Disposition"}
        )
    else:
        raise HTTPException(status_code=500, detail="file not found")

@router.post("/delete")
async def delete_file(download_request:FileDownloadRequest):
    url = download_request.url
    file_name = download_request.file_name
    print(url)
    if os.path.exists(url):
        os.remove(url)  # 删除文件
        return {
            "status_code": 200,
            "message": f"文件 {download_request.file_name} 已删除"
        }
    else:
        raise HTTPException(status_code=500, detail="file not found")





