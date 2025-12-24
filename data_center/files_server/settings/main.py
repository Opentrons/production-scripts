from dataclasses import dataclass
from ..types import OS
from ..utils import require_platform


@dataclass
class AppSettings:
    os: OS
    db_url: str
    files_uploads: str
    saved_data_path: str
    server_ip: str

    @classmethod
    def build(cls):
        return cls(
            os=require_platform(),
            db_url='mongodb://192.168.50.44:27017/',
            files_uploads='/files_server/uploads',
            saved_data_path='/files_server/datas',
            server_ip='192.168.50.44'
        )

settings = AppSettings.build()
