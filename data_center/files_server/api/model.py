from pydantic import BaseModel

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