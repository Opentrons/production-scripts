from pydantic import BaseModel

class DownloadRequest(BaseModel):
    host: str
    user_name: str
    download_path: str