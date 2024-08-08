from fastapi import Depends, FastAPI, HTTPException, APIRouter
from fastapi.responses import FileResponse
from typing import List
from server.api.device.models import *
from server.ot_type import Mount, Point
import os
from server.api.files.models import *
from server.utils import create_id
from fastapi import File, UploadFile

router = APIRouter()
files_path = './server/server_files/'


@router.post("/uploadfile/")
async def create_upload_file(file: UploadFile = File(...)):
    print(file)
    if not os.path.exists('uploaded_files'):
        os.mkdir('uploaded_files')
    with open(f"uploaded_files/{file.filename}", "wb") as f:
        f.write(await file.read())
    return {"filename": file.filename}


@router.post("/scp/robot")
async def scp_robot(content: contentParams):
    content_detail = content.params


@router.get("/download/{filename}", summary="download files")
async def download_file(filename: str):
    file_path = os.path.join(files_path, filename)
    print(file_path)
    return FileResponse(file_path, media_type="application/octet-stream", filename=filename)
