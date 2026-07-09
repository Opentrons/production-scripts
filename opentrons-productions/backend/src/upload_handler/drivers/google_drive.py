import io
import importlib.util
import os
import sys
import threading
from pathlib import Path

import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from settings import CREDENTIALS_PATH, TOKEN_PATH, get_logger
from upload_handler.utils import runtime_config

DOWNLOAD_DIR = runtime_config.DOWNLOAD_DIR
PROJECT_ROOT = runtime_config.PROJECT_ROOT

SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

logger = get_logger(__name__)
GOOGLE_API_TIMEOUT_SECONDS = int(os.getenv("GOOGLE_API_TIMEOUT_SECONDS", "180"))
GOOGLE_PROXY_TEST_URL = os.getenv(
    "GOOGLE_PROXY_TEST_URL",
    "https://www.googleapis.com/discovery/v1/apis/drive/v3/rest",
)
GHELPER_REFRESH_THREADS = int(os.getenv("GHELPER_MONITOR_THREADS", "25"))

DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.appdata",
    "https://www.googleapis.com/auth/drive.file",
]


def get_skill_config():
    skill_config = runtime_config.load_skill_config_module()
    if skill_config is None:
        raise RuntimeError("ghelper-test/skill_config.py is missing")
    return skill_config


def refresh_best_proxy_config() -> bool:
    node_test_path = Path(PROJECT_ROOT) / "ghelper-test" / "node_test.py"
    if not node_test_path.exists():
        logger.warning("Proxy refresh skipped; node_test.py not found at %s", node_test_path)
        return False

    try:
        spec = importlib.util.spec_from_file_location("ghelper_node_test", node_test_path)
        if spec is None or spec.loader is None:
            return False
        node_test_module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = node_test_module
        spec.loader.exec_module(node_test_module)
        best_node, best_proxy_url = node_test_module.get_best_proxy_and_update_config(
            max_threads=GHELPER_REFRESH_THREADS,
            update_subscription=True,
            test_url=GOOGLE_PROXY_TEST_URL,
        )
        runtime_config.reload_proxy_config()
        if best_proxy_url:
            logger.info("Proxy refresh selected node: %s", getattr(best_node, "name", "unknown"))
            return True
    except Exception as exc:
        logger.error("Proxy refresh failed: %s", exc)
    return False


def current_proxy_url() -> str | None:
    return runtime_config.get_proxy_url()


def test_google_api_proxy(proxy_url: str) -> bool:
    try:
        response = requests.get(
            GOOGLE_PROXY_TEST_URL,
            proxies=runtime_config.proxies_from_url(proxy_url),
            timeout=10,
        )
        response.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("Proxy test to Google API failed for %s: %s", runtime_config.get_proxy_label(), exc)
        return False


def select_google_proxy_url() -> str | None:
    proxy_url = current_proxy_url()
    if proxy_url and test_google_api_proxy(proxy_url):
        return proxy_url

    if runtime_config.USE_PROXY:
        logger.info("Refreshing proxy config before Google service init")
        if refresh_best_proxy_config():
            refreshed_proxy_url = current_proxy_url()
            if refreshed_proxy_url and (
                refreshed_proxy_url != proxy_url or test_google_api_proxy(refreshed_proxy_url)
            ):
                return refreshed_proxy_url

    if proxy_url:
        logger.warning(
            "Current Google proxy is unavailable and refresh did not provide a usable replacement; "
            "trying direct Google connection"
        )

    return None


def build_google_services(credentials):
    proxy_url = select_google_proxy_url()
    if proxy_url:
        logger.info("Using Google proxy node: %s", runtime_config.get_proxy_label())
        skill_config = get_skill_config()
        return (
            skill_config.build_google_service("drive", "v3", credentials, proxy_url=proxy_url),
            skill_config.build_google_service("sheets", "v4", credentials, proxy_url=proxy_url),
        )

    return (
        build("drive", "v3", credentials=credentials),
        build("sheets", "v4", credentials=credentials),
    )


def get_proxied_request():
    """创建带代理的 Request 对象"""
    proxy_url = select_google_proxy_url()
    if proxy_url:
        return get_skill_config().build_google_auth_request(proxy_url=proxy_url)
    return Request()


def get_proxied_flow(credentials_path, scopes):
    """创建带代理的 OAuth flow"""
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
    proxy_url = select_google_proxy_url()
    if proxy_url:
        get_skill_config().apply_oauth_flow_proxy(flow, proxy_url=proxy_url)
    return flow


class GoogleDriveDriver:
    _service_lock = threading.RLock()
    _shared_creds = None
    _shared_google_service = None
    _shared_sheet_service_client = None
    _shared_spreadsheets = None
    _refresh_thread: threading.Thread | None = None
    _stop_refresh_event = threading.Event()
    _refresh_interval = 300

    def __init__(self) -> None:
        self.token_path = TOKEN_PATH
        self.credentials_path = CREDENTIALS_PATH
        self.creds = None
        self.sheet_service_client = None
        self.spreadsheets = None
        self.google_service = None
        self.auto_refresh_stopped = False
        self.check_interval = self._refresh_interval
        self.get_drive_service_threading()

    @classmethod
    def _auto_refresh_thread(cls):
        """后台定时检查token是否过期并刷新"""
        while not cls._stop_refresh_event.wait(cls._refresh_interval):
            try:
                creds = cls._shared_creds
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(get_proxied_request())
                    cls._save_credentials_token(creds)
                    logger.info("后台自动刷新 token 完成。")
            except Exception as e:
                logger.info(f"自动刷新 token 失败: {e}")

    def _save_token(self):
        """保存token到文件"""
        self._save_credentials_token(self.creds, self.token_path)

    @classmethod
    def _save_credentials_token(cls, creds, token_path: str = TOKEN_PATH):
        if creds is None:
            return
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

    def _load_credentials(self, scopes):
        """加载或刷新凭证"""
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # 自动刷新 token
                creds.refresh(get_proxied_request())
                logger.info("自动刷新 token 成功。")
            else:
                # 无有效token，重新授权
                logger.info("未找到有效 token,开始授权...")
                flow = get_proxied_flow(self.credentials_path, scopes)
                creds = flow.run_local_server(port=0)
                logger.info("授权成功。")
            # 保存新token
            self.creds = creds
            self._save_token()
        else:
            self.creds = creds

    def _attach_shared_services(self):
        self.creds = self._shared_creds
        self.google_service = self._shared_google_service
        self.sheet_service_client = self._shared_sheet_service_client
        self.spreadsheets = self._shared_spreadsheets

    @classmethod
    def _start_refresh_thread_locked(cls):
        if cls._refresh_thread and cls._refresh_thread.is_alive():
            return
        cls._stop_refresh_event.clear()
        cls._refresh_thread = threading.Thread(
            target=cls._auto_refresh_thread,
            name="google-token-refresh",
            daemon=True,
        )
        cls._refresh_thread.start()

    def get_drive_service_threading(self):
        """初始化Google Drive和Sheets服务,并启动后台token刷新"""
        try:
            with self._service_lock:
                if self._shared_google_service and self._shared_sheet_service_client:
                    self._attach_shared_services()
                    self._start_refresh_thread_locked()
                    return self.google_service, self.sheet_service_client, self.spreadsheets

                scopes = [
                    "https://www.googleapis.com/auth/drive",
                    "https://www.googleapis.com/auth/spreadsheets",
                ]
                # 加载/刷新凭证
                self._load_credentials(scopes)

                self.google_service, self.sheet_service_client = build_google_services(self.creds)

                self.google_service._http.timeout = GOOGLE_API_TIMEOUT_SECONDS
                self.sheet_service_client._http.timeout = GOOGLE_API_TIMEOUT_SECONDS
                self.spreadsheets = self.sheet_service_client.spreadsheets()
                self.__class__._shared_creds = self.creds
                self.__class__._shared_google_service = self.google_service
                self.__class__._shared_sheet_service_client = self.sheet_service_client
                self.__class__._shared_spreadsheets = self.spreadsheets
                # 启动唯一后台刷新线程
                self._start_refresh_thread_locked()
            logger.info(
                "Google Drive & Sheets 服务初始化成功! timeout=%ss",
                GOOGLE_API_TIMEOUT_SECONDS,
            )
            return self.google_service, self.sheet_service_client, self.spreadsheets
        except Exception as e:
            raise RuntimeError(f"初始化 Google 服务失败: {e}")

    def stop_auto_refresh(self):
        """手动停止后台自动刷新"""
        self.auto_refresh_stopped = True
        self.shutdown_shared_services()
        logger.info("已停止后台自动刷新。")

    @classmethod
    def shutdown_shared_services(cls):
        """Stop shared Google refresh work and release service references."""
        cls._stop_refresh_event.set()
        refresh_thread = cls._refresh_thread
        if refresh_thread and refresh_thread.is_alive() and refresh_thread is not threading.current_thread():
            refresh_thread.join(timeout=2)
        with cls._service_lock:
            cls._refresh_thread = None
            cls._shared_creds = None
            cls._shared_google_service = None
            cls._shared_sheet_service_client = None
            cls._shared_spreadsheets = None

    def get_drive_service(self):
        """
        获取 Google Drive 和 Google Sheets 服务对象。
        自动刷新 token,如无 token 则自动弹出授权。
        """
        try:
            creds = None
            # ① 尝试读取本地 token 文件
            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, DRIVE_SCOPES)
            # ② 检查 token 是否有效
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    # 自动刷新 token
                    creds.refresh(get_proxied_request())
                    logger.info("Token 已自动刷新")
                else:
                    # 没有 token 或刷新失败，重新走 OAuth 授权
                    logger.info("正在打开浏览器进行 Google 授权...")
                    flow = get_proxied_flow(self.credentials_path, DRIVE_SCOPES)
                    creds = flow.run_local_server(port=0)
                    logger.info("授权完成")

                # ③ 保存（更新）token.json 文件
                with open(self.token_path, "w") as token_file:
                    token_file.write(creds.to_json())

            # ④ 创建 Google Drive 与 Sheets 服务
            self.google_service, self.sheet_service_client = build_google_services(creds)
            self.google_service._http.timeout = GOOGLE_API_TIMEOUT_SECONDS
            self.sheet_service_client._http.timeout = GOOGLE_API_TIMEOUT_SECONDS
            self.spreadsheets = self.sheet_service_client.spreadsheets()

            logger.info(
                "Google Drive 与 Sheets 服务初始化完成, timeout=%ss",
                GOOGLE_API_TIMEOUT_SECONDS,
            )
            return self.google_service, self.sheet_service_client, self.spreadsheets

        except Exception as e:
            logger.error(f"获取 Google 服务失败: {e}")
            return False

    def upload_to_drive(self, file_path, folder_id):
        """
        上传文件到网盘
        param file_path : 要上传的文件路径
        param folder_id : google网盘文件夹ID
        return upfailid
        """
        uploaded_file_id = ""
        logger.info(f"Trying to Upload file {file_path} to {folder_id}")
        try:
            # Set metadata for the new file
            file_metadata = {
                'name': os.path.basename(file_path),
                'parents': [folder_id]
            }
            # Upload the file to the folder
            media = MediaFileUpload(file_path,
                                    mimetype='application/octet-stream',
                                    resumable=True)
            uploaded_file = self.google_service.files().create(
                body=file_metadata,
                media_body=media,
                supportsAllDrives=True,
                fields='id',
            ).execute()

            uploaded_file_id = uploaded_file.get('id')
            return uploaded_file_id
        except Exception as err:
            logger.error("上传元数据文件失败")
            logger.error(err)
            return False

    def download_file(self, fileid, newname=''):
        """从谷歌网盘下载文件  Excel world文件不适合
        param fileid 网盘ID
        param newname 保存文件的名称，空则为下载名称
        return name,path
        """
        # 文件ID
        file_id = fileid
        # 下载文件
        try:
            if newname == '':
                file = self.google_service.files().get(fileId=file_id).execute()
                file_name = file['name']
            else:
                file_name = newname
            save_fail_path = os.path.join(DOWNLOAD_DIR, file_name)
            request = self.google_service.files().get_media(fileId=file_id)
            file = io.BytesIO()
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                logger.info(F'Download {int(status.progress() * 100)}.')
            # 将文件内容保存到本地磁盘
            with open(save_fail_path, 'wb') as f:
                f.write(file.getvalue())
            logger.info(f"文件已下载到本地磁盘，文件名：{file_name},路径{save_fail_path}")
            return file_name, save_fail_path
        except HttpError as error:
            logger.info(f"发生错误：{error}")
            return None, None

    def execute_file(self, fileid, extype='xlsx', newname=''):
        """导出Google Workspace 文档 like world Excel
        param fileid 要导出的文件ID
        param extype 需要保存的文件格式
        param newname 新文件的名称
        return name,path
        """
        MIMEDICT = {
            "csv": "text/csv",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pdf": "application/pdf",
            "txt": "text/plain",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "json": "application/vnd.google-apps.script+json",
            "jpg": "image/jpeg",

        }
        # 要导出的 Google Drive 文件的 ID 以及导出格式（Excel 文件为 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'）
        file_id = fileid
        file = self.google_service.files().get(fileId=file_id).execute()
        if newname == '':
            file_name = file['name']
        else:
            file_name = newname
        mimetypeval = MIMEDICT[extype]
        excutepath = os.path.join(DOWNLOAD_DIR, str(file_name) + "." + str(extype))
        try:
            request = self.google_service.files().export_media(fileId=file_id, mimeType=mimetypeval)
            file = io.BytesIO()
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                logger.info(F'Download {int(status.progress() * 100)}.')

            with open(excutepath, 'wb') as f:
                f.write(file.getvalue())
            logger.info(f"文件已下载到本地磁盘，文件名:{file_name},路径:{excutepath}")
            return file_name, excutepath
        except HttpError as error:
            logger.info(f'导出文件出错: {error}')
            return None, None

    def get_folder_data(self, folder_id):
        """
        获取网盘文件夹内的文件 名称 ID
        param folder_id : google网盘文件夹ID
        return 文件名 ID
        """
        itemlist = []
        try:
            query = f"'{folder_id}' in parents and trashed=false"
            results = self.google_service.files().list(q=query,
                                                      fields="nextPageToken, files(id, name, mimeType)").execute()
            items = results.get('files', [])
            # logger.info out the names and IDs of all files in the folder
            if not items:
                logger.info("No files found.")
            else:
                logger.info("Files:")
                for item in items:
                    itemlist.append([item["name"], item["id"]])
                    # logger.info("{0} ({1})".format(item["name"], item["id"]))
            return itemlist
        except Exception as err:
            logger.info("上传文件失败{}".format(err))
            return itemlist

    def get_folder_data_share(self, folder_id, name):
        """
        获取共享网盘文件夹内的文件名称ID
        param folder_id : google网盘文件夹ID
        return 文件名 ID
        """
        itemlist = []
        try:
            query = "sharedWithMe = true and mimeType != 'application/vnd.google-apps.folder'"
            results = self.google_service.files().list(q=query, fields="nextPageToken, files({}, {})".format(folder_id,name)).execute()
            items = results.get('files', [])
            if not items:
                logger.info("No files found.")
            else:
                logger.info("Files:")
                for item in items:
                    itemlist.append([item["name"], item["id"]])
                    # logger.info("{0} ({1})".format(item["name"], item["id"]))
            # 列出与你共享的所有文件
            results = self.google_service.files().list(
                q="sharedWithMe=true",
                orderBy="modifiedTime desc",
                fields="nextPageToken, files(id, name, mimeType, owners)"
            ).execute()

            if not results['files']:
                logger.info('没有与你共享的文件。')
            else:
                logger.info('与你共享的文件：')
                for file in results['files']:
                    logger.info(f"{file['name']} ({file['id']})")
            return itemlist
        except Exception as err:
            logger.info("上传文件失败{}".format(err))
            return itemlist

    def copy_file(self, old_file_id, new_file_name):
        """
        复制文件夹内的文件
        param old_file_id :要复制的文件ID
        param new_file_name : 复制后文件的名称
        """
        # 构造请求体并发送请求
        try:
            logger.info(f"coping file {old_file_id} to {new_file_name}")
            request_body = {
                "name": new_file_name
            }
            # origin_file = self.google_service.files().get(fileId=old_file_id).execute()
            response = self.google_service.files().copy(
                fileId=old_file_id,
                body=request_body,
                supportsAllDrives=True
            ).execute()
            # logger.info(f"{response.get('name')} copied to {response.get('id')}.")
            newname = response.get('name')
            newid = response.get('id')
            # logger.info(f'复制文件成功 name:{newname} id{newid}')
            return newname, newid
        except Exception as err:
            logger.info("复制文件出错: {}".format(err))

    def create_folders(self, newname, parentfolderid=""):
        """
        在文件夹内创建新的文件夹
        param newname : 要创建的新文件夹名称
        param parent_folder_id : 父文件夹名称 不输入则在根目录创建
        """
        folder_id = ''
        try:
            # 创建新文件夹
            folder_name = newname
            parent_folder_id = parentfolderid
            # 构建文件夹元数据
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_folder_id],
                # 如果目标位置是共享驱动器（Team Drive）需要添加以下参数
                'driveId': parent_folder_id,
                'supportsAllDrives': True
            }
            # 执行创建操作
            folder = self.google_service.files().create(
                body=file_metadata,
                fields='id, name, webViewLink',
                supportsAllDrives=True  # 必须开启此参数
            ).execute()
            folder_id = folder['id']
            # 打印新文件夹的ID
            # logger.info(f"已创建新文件夹，ID为{folder_id}")
            return folder_id
        except Exception as err:
            logger.info("创建文件夹出错：{}".format(err))
            return folder_id

    def show_shared_files(self, sharedfileid):
        """列出共享文件夹内文件"""
        nameidlist = []
        folder_id = sharedfileid  # '共享文件夹的ID'  # 替换为共享文件夹的ID
        # 查询共享文件夹中的文件
        query = f"'{folder_id}' in parents and trashed = false"
        results = self.google_service.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name)",
            supportsAllDrives=True,  # 如果是共享驱动器需启用
            includeItemsFromAllDrives=True
        ).execute()
        items = results.get('files', [])
        if not items:
            logger.info('No files found.')
        else:
            logger.info('Files:')
            for item in items:
                logger.info(f"{item['name']} ({item['id']})")
                nameidlist.append({"name": item['name'], 'id': item['id']})
        return nameidlist

    def move_files(self, moveitemid, dest_folder_id):
        """移动文件"""
        logger.info(f"Trying to move file to {dest_folder_id}")
        try:
            result = self.google_service.files().get(
                fileId=dest_folder_id,
                fields='id, name, mimeType, parents',
                supportsAllDrives=True
            ).execute()
            # 获取当前父文件夹
            current_parents = ",".join(result.get('parents', []))
            logger.info(f"Current folder: {dest_folder_id}")
            # 更新父文件夹
            updated_file = self.google_service.files().update(
                fileId=moveitemid,
                addParents=dest_folder_id,
                removeParents=current_parents,
                fields='id, parents',
                supportsAllDrives=True
            ).execute()
            logger.info(f"Moving file {moveitemid}")
            if moveitemid == updated_file["id"]:
                return True
            else:
                return False
        except HttpError as error:
            logger.error(f"Error moving {moveitemid}: {error}")
            return False

    def move_file_multi_level(self, file_id, dest_folder_id):
        """
        安全移动文件到目标文件夹，支持个人盘和共享盘（跨级移动）。
        
        :param file_id: 要移动的文件ID
        :param dest_folder_id: 目标文件夹ID
        :return: dict {'file_id', 'success', 'parents', 'error'}
        """
        logger.info(f"Trying to move file to {dest_folder_id}")
        result_item = {
            'file_id': file_id,
            'success': "False",
            'parents': None,
            'error': None
        }

        try:
            # 获取文件当前父文件夹
            file_metadata = self.google_service.files().get(
                fileId=file_id,
                fields='parents, name',
                supportsAllDrives=True
            ).execute()

            current_parents = file_metadata.get('parents', [])
            file_name = file_metadata.get('name', '')
            logger.info(f"Current folder: {current_parents[0]}")
            # 如果文件已经在目标文件夹，不做任何操作
            if dest_folder_id in current_parents and len(current_parents) == 1:
                result_item['success'] = "True"
                result_item['parents'] = current_parents
                return result_item

            # 对共享盘文件，保证至少有一个父文件夹
            # 1. 如果文件在共享盘且父文件夹数量为1，只移除非目标文件夹
            # 2. 如果父文件夹数量 >1，移除所有非目标父文件夹
            parents_to_remove = [p for p in current_parents if p != dest_folder_id]

            updated_file = self.google_service.files().update(
                fileId=file_id,
                addParents=dest_folder_id,
                removeParents=",".join(parents_to_remove) if parents_to_remove else None,
                fields='id, parents, name',
                supportsAllDrives=True
            ).execute()

            result_item['success'] = "True"
            result_item['parents'] = updated_file.get('parents', [])
            logger.info(f"Moving: {file_name} success")

        except Exception as err:
            result_item['error'] = str(err)
            logger.error(f"Error moving {file_id}: {err}")

        return result_item

    def rename(self, file_id, new_name):
        result = self.verify_file(file_id)
        if not result:
            logger.info(f"{file_id} not found.")
            return None
        try:
            # 构建更新请求
            body = {
                'name': new_name
            }

            # 更新文件元数据
            result = self.google_service.files().update(
                fileId=file_id,
                body=body,
                fields='id, name',
                supportsAllDrives=True
            ).execute()

            # logger.info(f"✅ 成功将文件重命名为: '{result.get('name')}'")
            # logger.info(f"📄 文件ID: {result.get('id')}")
            return True
        except HttpError as err:
            logger.info("rename 失败: {}".format(err))
            return None

    def verify_file(self, _id):
        try:
            file_info = self.google_service.files().get(
                fileId=_id,
                fields='id, name, mimeType',
                supportsAllDrives=True
            ).execute()
            return True
        except HttpError as err:
            return False

    @staticmethod
    def parse_drive_file_id(url_or_id: str) -> str | None:
        """Extract a Google Drive file/folder ID from a URL or raw ID."""
        value = str(url_or_id or "").strip()
        if not value or value in {"N/A", "NA", "http:xx"}:
            return None
        if "/" not in value and "?" not in value:
            return value

        for marker in ("/d/", "/folders/"):
            if marker in value:
                file_id = value.split(marker, 1)[1]
                return file_id.split("/", 1)[0].split("?", 1)[0]

        if "id=" in value:
            return value.split("id=", 1)[1].split("&", 1)[0]
        return None

    def trash_file(self, file_id: str) -> bool:
        """Move a Drive file or folder to trash."""
        file_id = str(file_id or "").strip()
        if not file_id:
            return False
        try:
            self.google_service.files().update(
                fileId=file_id,
                body={"trashed": True},
                supportsAllDrives=True,
            ).execute()
            logger.info("Moved Drive resource to trash: %s", file_id)
            return True
        except HttpError as error:
            logger.error("Trash Drive resource failed file_id=%s error=%s", file_id, error)
            return False

    def delete_file(self, file_id: str) -> bool:
        """Permanently delete a Drive file or folder."""
        file_id = str(file_id or "").strip()
        if not file_id:
            return False
        try:
            if not self.verify_file(file_id):
                logger.warning("Skip permanent delete because resource not found: %s", file_id)
                return False
            self.google_service.files().delete(
                fileId=file_id,
                supportsAllDrives=True,
            ).execute()
            logger.info("Permanently deleted Drive resource: %s", file_id)
            return True
        except HttpError as error:
            logger.error("Delete Drive resource failed file_id=%s error=%s", file_id, error)
            return False

    def delete_drive_resource(self, file_id: str, *, permanent: bool = False) -> bool:
        """Trash or permanently delete a Drive resource by file ID."""
        if permanent:
            return self.delete_file(file_id)
        return self.trash_file(file_id)

    def delete_drive_resource_by_url(self, url: str, *, permanent: bool = False) -> bool:
        """Trash or permanently delete a Drive resource parsed from a URL."""
        file_id = self.parse_drive_file_id(url)
        if not file_id:
            logger.warning("Skip Drive delete because URL is invalid: %s", url)
            return False
        return self.delete_drive_resource(file_id, permanent=permanent)

    def delete_drive_resources_by_urls(
        self,
        urls: list[str],
        *,
        permanent: bool = False,
    ) -> dict:
        """Batch trash or permanently delete Drive resources referenced by URLs."""
        deleted: list[dict[str, str]] = []
        failed: list[dict[str, str]] = []
        skipped: list[str] = []

        for url in urls:
            file_id = self.parse_drive_file_id(url)
            if not file_id:
                skipped.append(url)
                continue
            if self.delete_drive_resource(file_id, permanent=permanent):
                deleted.append({"url": url, "file_id": file_id})
            else:
                failed.append({"url": url, "file_id": file_id})

        logger.info(
            "Drive cleanup finished: deleted=%s failed=%s skipped=%s permanent=%s",
            len(deleted),
            len(failed),
            len(skipped),
            permanent,
        )
        return {
            "deleted": deleted,
            "failed": failed,
            "skipped": skipped,
            "permanent": permanent,
        }

    def check_rename_permission(self, file_id):
        """
        检查是否具有重命名文件的权限

        返回:
        bool - 是否有重命名权限
        dict - 权限详细信息
        """
        file_id.strip()
        if '.' in file_id:
            file_id = file_id.replace('.', '')
        try:
            # 1. 首先获取文件的基本信息
            file_info = self.google_service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, capabilities/canRename',
                supportsAllDrives=True
            ).execute()

            logger.info(f"📄 文件: {file_info.get('name')}")

            # 2. 检查文件的canRename能力
            capabilities = file_info.get('capabilities', {})
            if capabilities.get('canRename'):
                logger.info("✅ 文件支持重命名")
            else:
                logger.info("❌ 文件不支持重命名（可能是只读文件）")
                return False, {}

            # 3. 获取详细的权限信息
            permissions = self.google_service.permissions().list(
                fileId=file_id,
                fields='permissions(id, emailAddress, role, type, displayName)',
                supportsAllDrives=True
            ).execute()

            service_account_email = self.creds.service_account_email
            logger.info(f"👤 当前服务账号: {service_account_email}")

            # 4. 检查服务账号的权限
            has_rename_permission = False
            permission_details = {}

            logger.info("\n🔍 权限列表:")
            for perm in permissions.get('permissions', []):
                perm_email = perm.get('emailAddress', '')
                perm_role = perm.get('role', '')
                perm_type = perm.get('type', '')

                logger.info(f"   - {perm_email}: {perm_role} ({perm_type})")

                if perm_email == service_account_email:
                    has_rename_permission = perm_role in ['owner', 'writer']
                    permission_details = perm
                    break

            if has_rename_permission:
                logger.info(f"✅ 有重命名权限: {permission_details.get('role')}")
            else:
                logger.info("❌ 没有重命名权限")
                logger.info("💡 需要的权限: writer 或 owner")

            return has_rename_permission, permission_details

        except HttpError as err:
            logger.info(f"❌ 检查权限时发生HTTP错误: {err}")
            if err.resp.status == 403:
                logger.info("💡 错误403: 没有查看权限的权限")
            return False, {}
        except Exception as err:
            logger.info(f"❌ 检查权限时发生错误: {err}")
            return False, {}

    ###########以下为谷歌表格相关###########
    def create_excel(self, excelname, parentf_older_id):
        """
        创建新表格
        param excelname 要创建的文件名称
        param parentf_older_id 父文件夹ID  为空则在根目录创建
        return spreadsheet_id
        """
        # 创建新表格
        spreadsheet_id = ''
        try:
            file_metadata = {
                "name": excelname,
                "parents": [parentf_older_id],
                "mimeType": "application/vnd.google-apps.spreadsheet"
            }

            response = self.sheet_service_client.spreadsheets().create(
                body=file_metadata
            ).execute()

            # 打印新表格的ID
            spreadsheet_id = response['spreadsheetId']
            logger.info(f"已创建新表格，ID为{spreadsheet_id}")
            return spreadsheet_id
        except Exception as e:
            logger.info("创建表格失败：{}".format(e))
            return spreadsheet_id

    def get_excel_sheet(self, spreadsheetId, range, majorDimensionval='ROWS'):
        # Call the Sheets API
        """
        获取表格全部数据内容
        param spreadsheetId : 表格的ID
        param range : 表格的sleep名称
        param majorDimensionval : 检索模式 ROWS COLUMNS
        return 返回数据内容 list
        """
        values = []
        try:
            sheet = self.sheet_service_client.spreadsheets()
            result = sheet.values().get(
                spreadsheetId=spreadsheetId,
                range=range,
                majorDimension=majorDimensionval,
            ).execute()
            values = result.get('values', [])
            return values
        except Exception as err:
            logger.info("获取数据失败{}".format(err))
            return values

    def get_excel_sheet_page(self, spreadsheetId, range, majorDimensionval='ROWS',
                             page_size=["!A1:A1000", "!B1:B1000"]):
        # Call the Sheets API
        """
        获取表格某个区域的数据内容 分段获取 (超1000行必须使用这个分段获取)
        param spreadsheetId : 表格的ID
        param range : 表格的sleep名称
        param majorDimensionval : 检索模式 ROWS COLUMNS
        return 返回数据内容 list
        """
        # 遍历每一页并读取数据

        value_ = []
        try:
            for page in page_size:
                rangesval = range + page
                # Pip1!A1:E1
                # Pip1!A1:E1
                # 发送分页请求
                result = self.sheet_service_client.spreadsheets().values().batchGet(
                    spreadsheetId=spreadsheetId,
                    ranges=rangesval,
                    majorDimension=majorDimensionval
                ).execute()
                for value_range in result["valueRanges"]:
                    values = value_range.get("values", [])
                    value_.append(values)
            # 处理响应结果
            logger.info(f"Getting raw data in {spreadsheetId}")
            return value_
        except Exception as err:
            logger.info(f"获取Excel表格数据出错于{spreadsheetId}")
            logger.info(err)
            return value_

    def update_excel_sheet(self, spreadsheet_id, range_name, range, new_values, value_input_option='RAW'):
        """
        更新表格数据内容
        param spreadsheet_id : 表格的ID
        param range_name : 表格的sleep名称
        param range : 更新的范围 [!A1:A1000]
        param value_input_option 确定应如何解释输入数据 (RAW 系统将不会解析用户输入的值，并会按原样存储这些值。 USER_ENTERED 系统会解析这些值，就像用户在界面中输入这些值一样。数字会保留为数字，但字符串可能会转换为与通过 Google 表格界面在单元格中输入文本时适用的规则相同的数字、日期等。)
        param new_values : 更新的数据 []
        return 返回数据内容 list
        """
        # Update the cells with the new values
        rangeval = str(range_name) + str(range)
        try:
            request = self.sheet_service_client.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=rangeval,
                valueInputOption=value_input_option,
                body={
                    'values': new_values
                }
            ).execute()
            response = request.execute()

            return response

        except Exception as errval:
            logger.info("更新数据失败{}".format(errval))

    def update_excel_sheet_page_list(self, spreadsheet_id, range_name, rangelist, new_values,
                                     value_input_option='USER_ENTERED'):
        """
        分页更新表格数据内容(数据超1000 多段式）  list
        param spreadsheet_id : 表格的ID
        param range_name : 表格的sheet名称
        param rangelist : 更新的范围 [!A1:A1000,!B1:B1000]
        param value_input_option 确定应如何解释输入数据 (RAW 系统将不会解析用户输入的值，并会按原样存储这些值。 USER_ENTERED 系统会解析这些值，就像用户在界面中输入这些值一样。数字会保留为数字，但字符串可能会转换为与通过 Google 表格界面在单元格中输入文本时适用的规则相同的数字、日期等。)
        param new_values : 更新的数据 [,]
        return 返回数据内容 list
        """
        try:
            for ii, r in enumerate(rangelist):
                rangeval = str(range_name) + str(r)
                request = self.sheet_service_client.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=rangeval,
                    valueInputOption=value_input_option,
                    body={
                        'values': new_values[ii]
                    }
                ).execute()
                # response = request.execute()

                logger.info(request)
            return True

        except Exception as errval:
            logger.info("更新数据失败{}".format(errval))
            return False

    def check_sheet_exists(self, spreadsheet_id, sheet_name):
        """
        检查工作表是否存在
        """
        try:
            spreadsheet = self.spreadsheets.get(spreadsheetId=spreadsheet_id).execute()
            sheets = spreadsheet.get('sheets', [])

            for sheet in sheets:
                if sheet['properties']['title'] == sheet_name:
                    return True
            return False

        except Exception as e:
            logger.info(f"❌ 检查工作表存在性失败: {e}")
            return False

    def copy_df_to_sheet(self, clean_df, spreadsheet_id, sheet_name, start_cell='A1'):
        def create_sheet_if_not_exists(_spreadsheet_id, _sheet_name):
            """
            如果工作表不存在，则创建它
            """
            if not self.check_sheet_exists(_spreadsheet_id, _sheet_name):
                try:
                    body = {
                        'requests': [{
                            'addSheet': {
                                'properties': {
                                    'title': sheet_name
                                }
                            }
                        }]
                    }

                    self.spreadsheets.batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=body
                    ).execute()

                    logger.info(f"✅ 已创建新工作表: '{sheet_name}'")
                    return True

                except Exception as e:
                    logger.info(f"❌ 创建工作表失败: {e}")
                    return False
            return True

        def format_range_name(sheet_name, cell_range):
            """
            格式化范围名称，处理特殊字符
            """
            # 如果工作表名称包含空格或特殊字符，需要加单引号
            if any(char in sheet_name for char in [' ', '-', "'", '"']):
                return f"'{sheet_name}'!{cell_range}"
            else:
                return f"{sheet_name}!{cell_range}"

        if not create_sheet_if_not_exists(spreadsheet_id, sheet_name):
            return False
        range_name = format_range_name(sheet_name, start_cell)

        # 清理数据（处理NaN值等）
        data = [clean_df.columns.tolist()]  # 表头
        data.extend(clean_df.values.tolist())  # 数据行

        logger.info(f"📤 准备写入数据到: {range_name}")
        logger.info(f"  总行数: {len(data)}")
        logger.info(f"  总列数: {len(data[0]) if data else 0}")

        body = {
            'values': data
        }

        # 写入数据
        result = self.spreadsheets.values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()

        logger.info(f"✅ 成功写入 {result.get('updatedCells')} 个单元格")
        logger.info(f"🎉 数据已成功导入到工作表 '{sheet_name}'")

        return True

    def update_excel_sheet_page(self, spreadsheet_id, range_name, range, new_values, value_input_option='USER_ENTERED'):
        """
        更新表格数据内容  list
        param spreadsheet_id : 表格的ID
        param range_name : 表格的sleep名称
        param rangelist : 更新的范围 [!A1:A1000,!B1:B1000]
        param value_input_option 确定应如何解释输入数据 (RAW 系统将不会解析用户输入的值，并会按原样存储这些值。 USER_ENTERED 系统会解析这些值，就像用户在界面中输入这些值一样。数字会保留为数字，但字符串可能会转换为与通过 Google 表格界面在单元格中输入文本时适用的规则相同的数字、日期等。)
        param new_values : 更新的数据 [,]
        return 返回数据内容 list
        """
        # Update the cells with the new values
        rangeval = f"{range_name}{range}"
        try:
            request = self.sheet_service_client.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=rangeval,
                valueInputOption=value_input_option,
                body={
                    'values': new_values
                }
            ).execute()
            # response = request.execute()

            logger.info(request)
            return True

        except Exception as errval:
            logger.info("更新数据失败{}".format(errval))
            return False

    def update_excel_sheet_page_batch(self, spreadsheet_id, sheet_name, ranges, new_values,
                                      value_input_option='USER_ENTERED'):
        """
        更新 Google 表格数据内容（支持单个或多个范围）

        :param spreadsheet_id: 表格ID
        :param sheet_name: 工作表名称（如 "Gravimetric Raw Data"）
        :param ranges: 更新的范围（字符串或列表） 如 '!A1:D1000' 或 ['!A1:D1000','!A1001:D1696']
        :param new_values: 更新的数据（二维数组或二维数组列表）
        :param value_input_option: USER_ENTERED / RAW
        """
        try:
            # 情况 1：单个范围
            if isinstance(ranges, str):
                full_range = f"{sheet_name}{ranges}"
                row_count = len(new_values) if new_values else 0
                logger.info(
                    "Writing sheet range 1/1: spreadsheet=%s sheet=%s range=%s rows=%s",
                    spreadsheet_id,
                    sheet_name,
                    full_range,
                    row_count,
                )
                self.sheet_service_client.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=full_range,
                    valueInputOption=value_input_option,
                    body={'values': new_values}
                ).execute()
                logger.info(
                    "Finished sheet range 1/1: spreadsheet=%s sheet=%s range=%s",
                    spreadsheet_id,
                    sheet_name,
                    full_range,
                )

            # 情况 2：多个范围
            elif isinstance(ranges, list):
                total_ranges = len(ranges)
                if total_ranges != len(new_values):
                    raise ValueError(
                        f"ranges and new_values length mismatch: {total_ranges} != {len(new_values)}"
                    )

                for index, (sheet_range, values) in enumerate(zip(ranges, new_values), start=1):
                    full_range = f"{sheet_name}{sheet_range}"
                    row_count = len(values) if values else 0
                    logger.info(
                        "Writing sheet range %s/%s: spreadsheet=%s sheet=%s range=%s rows=%s",
                        index,
                        total_ranges,
                        spreadsheet_id,
                        sheet_name,
                        full_range,
                        row_count,
                    )
                    self.sheet_service_client.spreadsheets().values().update(
                        spreadsheetId=spreadsheet_id,
                        range=full_range,
                        valueInputOption=value_input_option,
                        body={'values': values}
                    ).execute()
                    logger.info(
                        "Finished sheet range %s/%s: spreadsheet=%s sheet=%s range=%s",
                        index,
                        total_ranges,
                        spreadsheet_id,
                        sheet_name,
                        full_range,
                    )
            else:
                raise TypeError("参数 ranges 必须是 str 或 list 类型")

            logger.info(f"Updated {sheet_name} in {spreadsheet_id}")
            return True

        except Exception as err:
            logger.info(f"Update {sheet_name} in {spreadsheet_id}")
            logger.info(err)
            return False

    def copy_sheet_excel(self, source_spreadsheet_id, target_spreadsheet_id, sheet_id):
        """
        复制工作表更新成功
        param source_spreadsheet_id 源文件ID
        param target_spreadsheet_id 目标文件ID
        param sheet_id 要复制的工作表ID
        return title,copied_sheet_id
        """
        try:
            # 获取源和目标文件的ID
            SOURCE_SPREADSHEET_ID = source_spreadsheet_id
            TARGET_SPREADSHEET_ID = target_spreadsheet_id
            sheet_id_ = sheet_id  # 要复制的工作表ID

            # 复制工作表
            request_body = {
                "destinationSpreadsheetId": TARGET_SPREADSHEET_ID,
            }
            response = self.sheet_service_client.spreadsheets().sheets().copyTo(
                spreadsheetId=SOURCE_SPREADSHEET_ID,
                sheetId=sheet_id_,
                body=request_body
            ).execute()

            # 打印复制后的工作表信息
            copied_sheet_id = response['sheetId']
            copied_sheet_title = response['title']

            # logger.info(f"工作表已复制到目标文件，ID为:{copied_sheet_id}，名称为:{copied_sheet_title}")

            return copied_sheet_title, copied_sheet_id


        except Exception as err:
            logger.info("复制sheet 出错{}".format(err))
            return False

    def get_sheet_info(self, spreadsheet_id):
        """
        获取在线excel文件内的所有工作表名称及其ID
        """
        try:
            spreadsheet = self.sheet_service_client.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheets = spreadsheet.get('sheets', [])
            sheets_info = []
            for sheet in sheets:
                properties = sheet.get('properties', {})
                sheet_info = {
                    'sheet_id': properties.get('sheetId'),  # 这就是工作表的ID
                    'title': properties.get('title'),  # 工作表名称
                    'index': properties.get('index'),  # 工作表索引位置
                    'grid_properties': properties.get('gridProperties', {}),  # 网格属性
                    'sheet_type': properties.get('sheetType', 'GRID')  # 工作表类型
                }
                sheets_info.append(sheet_info)

            return sheets_info
        except HttpError as error:
            logger.info(f"获取工作表信息时出错: {error}")
            return None

    def get_sheet_gid_map(self, spreadsheet_id):
        """
        获取 Google Sheet 中所有工作表名称与 gid 对应关系
        
        Args:
            spreadsheet_id (str): Google 表格的 ID（URL 中的 /d/.../ 部分）
        
        Returns:
            dict: {工作表名称: gid} 的映射字典
        """
        try:
            # service = build('sheets', 'v4', credentials=creds)
            spreadsheet = self.sheet_service_client.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheets = spreadsheet.get("sheets", [])

            sheet_gid_map = {}
            for sheet in sheets:
                title = sheet["properties"]["title"]
                gid = sheet["properties"]["sheetId"]
                sheet_gid_map[title] = gid

            return sheet_gid_map

        except Exception as e:
            logger.error("获取 sheet gid 失败：", e)
            return None


if __name__ == "__main__":
    pass
