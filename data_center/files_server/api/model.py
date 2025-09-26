from pydantic import BaseModel
from typing import List


# flex
class DownloadRequest(BaseModel):
    host: str
    user_name: str
    download_path: str
    saved_name: str

class RobotRequest(BaseModel):
    host: str

class RunScriptResponse(BaseModel):
    host: str
    script: str


# user

class UserLoginRequest(BaseModel):
    username: str
    password: str
    rememberMe: bool


# db

class ReadDocumentRequest(BaseModel):
    db_name: str
    document_name: str
    limit: int

class InsertDocumentRequest(BaseModel):
    db_name: str
    document_name: str
    collections: dict


# file server

class FetchFileListRequest(BaseModel):
    db_name: str

class FileDownloadRequest(BaseModel):
    url: str
    file_name: str

# google Drive
class FileUploadRequest(BaseModel):
    product_name: str
    quarter_name: str
    sn: str
    test_name: str
    files_list: dict
    finished: bool
