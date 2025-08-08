from pydantic import BaseModel


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


