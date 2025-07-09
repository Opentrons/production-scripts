from files_server.remote import build_handler
from fastapi import Depends, FastAPI, HTTPException, APIRouter
from typing import List
from files_server.api.model import *

router = APIRouter()

@router.post('/create/folder', status_code=200)
async def google_drive_create_folder():
    """
    update date of flex
    """
    return {
        "success": True,
        "message": "undo"
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