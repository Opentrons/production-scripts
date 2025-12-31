from dataclasses import dataclass
from ..this_types import OS, UploadEnv
from ..utils import require_platform

DEBUG: bool = False


@dataclass
class AppSettings:
    debug: bool
    os: OS
    db_url: str
    files_uploads: str
    os: OS
    db_url: str
    files_uploads: str
    saved_data_path: str
    server_ip: str
    default_gateway: str
    remote_data_path: str
    delete_data_after_upload: bool
    server_dir: str
    log_file: str
    upload_env: UploadEnv
    cycle_delay_min: int

    @classmethod
    def build(cls):
        return cls(
            # system setting
            debug=DEBUG,
            os=require_platform(),
            # database
            db_url='mongodb://192.168.50.44:27017/',
            server_ip='192.168.50.44',
            default_gateway='192.168.6.0',
            # download testing data
            remote_data_path='/data/testing_data',
            delete_data_after_upload=True,
            files_uploads='./uploads' if DEBUG else '/data/uploads',
            saved_data_path='./downloads' if DEBUG else '/data/downloads',
            # config server
            server_dir='/opt/data-center-server',
            log_file='/opt/data-center-server/app.log' if require_platform() == OS.Linux else '../app.log',
            upload_env='debug',
            cycle_delay_min=1,
        )


settings = AppSettings.build()
