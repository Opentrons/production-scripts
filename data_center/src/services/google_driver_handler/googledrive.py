import os, sys
import io
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.http import MediaIoBaseDownload
import platform
from ...settings import settings
system = platform.system()
from src.services.google_driver_handler.globalconfig import DOWNLOAD_DIR

codepath = os.path.dirname(__file__)
addpath = os.path.dirname(os.path.dirname(__file__))
addpath2 = os.path.dirname(addpath)
if addpath not in sys.path:
    sys.path.append(addpath)
if addpath2 not in sys.path:
    sys.path.append(addpath2)

if system == "Linux":
    BaseURL = '/src/'
else:
    BaseURL = codepath
token_path = os.path.join(BaseURL, 'token.json') if settings.debug else '/files_server/token.json'
credentialspath = os.path.join(BaseURL, 'credentials.json') if settings.debug else '/files_server/credentials.json'

class googledrive():
    def __init__(self) -> None:
        self.tokenpath = token_path
        self.credentialspath = credentialspath
        self.creds = None
        self.get_drive_service()

    def get_drive_service(self):
        try:

            SCOPES = [
                'https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/drive.appdata',
                'https://www.googleapis.com/auth/drive.file']
            if os.path.exists(self.tokenpath):
                self.creds = Credentials.from_authorized_user_file(self.tokenpath, SCOPES)

            if not self.creds or not self.creds.valid:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentialspath, SCOPES)
                self.creds = flow.run_local_server(port=0)

                # Save the credentials for the next run
                with open(self.tokenpath, 'w') as token:
                    token.write(self.creds.to_json())
            # Create an authorized Drive API client
            self.googleservice = build('drive', 'v3', credentials=self.creds)
        except Exception as e:
            raise e

    def upload_to_drive(self, file_path, folder_id):
        """
        上传文件到网盘
        param file_path : 要上传的文件路径
        param folder_id : google网盘文件夹ID
        return upfailid
        """
        upfileid = ""
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
            file = self.googleservice.files().create(body=file_metadata,
                                                     media_body=media,
                                                     supportsAllDrives=True,  # 如果是共享驱动器需启用
                                                     fields='id').execute()

            upfileid = file.get('id')
            print('update File ID: {}'.format(file.get('id')))
            return upfileid
        except Exception as err:
            print("上传文件失败{}".format(err))
            return upfileid

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
                file = self.googleservice.files().get(fileId=file_id).execute()
                file_name = file['name']
            else:
                file_name = newname

            save_fail_path = os.path.join(DOWNLOAD_DIR, file_name)
            request = self.googleservice.files().get_media(fileId=file_id)
            file = io.BytesIO()
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                print(F'Download {int(status.progress() * 100)}.')

            # 将文件内容保存到本地磁盘
            with open(save_fail_path, 'wb') as f:
                f.write(file.getvalue())

            print(f"文件已下载到本地磁盘，文件名：{file_name},路径{save_fail_path}")
            return file_name, save_fail_path
        except HttpError as error:
            print(f"发生错误：{error}")
            return None, None

    def execute_file(self, fileid, extype='xlsx', newname=''):
        """导出Google Workspace 文档 like world Excel
        param fileid 要导出的文件ID
        param extype 需要保存的文件格式
        param newname 新文件的名称
        return name,path
        """

        MIMEDICT = {
            "report": "text/report",
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

        file = self.googleservice.files().get(fileId=file_id).execute()
        if newname == '':

            file_name = file['name']
        else:
            file_name = newname

        mimetypeval = MIMEDICT[extype]

        excutepath = os.path.join(DOWNLOAD_DIR, str(file_name) + "." + str(extype))

        try:

            request = self.googleservice.files().export_media(fileId=file_id,
                                                              mimeType=mimetypeval)
            file = io.BytesIO()
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                print(F'Download {int(status.progress() * 100)}.')

            with open(excutepath, 'wb') as f:
                f.write(file.getvalue())
            print(f"文件已下载到本地磁盘，文件名:{file_name},路径:{excutepath}")
            return file_name, excutepath
        except HttpError as error:
            print(f'导出文件出错: {error}')
            return None, None

    def get_folder_data(self, folder_id):
        """
        获取网盘文件夹内的文件 名称 ID
        param folder_id : google网盘文件夹ID
        return 文件名 ID
        """
        itemlist = []
        try:
            # # Define search parameters to find files in the folder
            # query = "'{}' in parents and trashed = false".format(folder_id)

            # # Use the Drive API to find files in the folder
            # results = self.googleservice.files().list(q=query,
            #                             fields="nextPageToken, files(id, name)").execute()
            # items = results.get("files", [])
            query = f"'{folder_id}' in parents and trashed=false"
            results = self.googleservice.files().list(q=query,
                                                      fields="nextPageToken, files(id, name, mimeType)").execute()
            items = results.get('files', [])

            # Print out the names and IDs of all files in the folder
            if not items:
                print("No files found.")
            else:
                print("Files:")
                for item in items:
                    itemlist.append([item["name"], item["id"]])
                    print("{0} ({1})".format(item["name"], item["id"]))

            return itemlist
        except Exception as err:
            print("上传文件失败{}".format(err))
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
            results = self.googleservice.files().list(q=query, fields="nextPageToken, files({}, {})".format(folder_id,
                                                                                                            name)).execute()
            items = results.get('files', [])
            # results = self.googleservice.files().list(q=query, fields="nextPageToken, files(id, name)").execute()
            # items = results.get('files', [])
            if not items:
                print("No files found.")
            else:
                print("Files:")
                for item in items:
                    itemlist.append([item["name"], item["id"]])
                    print("{0} ({1})".format(item["name"], item["id"]))

            # 列出与你共享的所有文件
            results = self.googleservice.files().list(
                q="sharedWithMe=true",
                orderBy="modifiedTime desc",
                fields="nextPageToken, files(id, name, mimeType, owners)"
            ).execute()

            if not results['files']:
                print('没有与你共享的文件。')
            else:
                print('与你共享的文件：')
                for file in results['files']:
                    print(f"{file['name']} ({file['id']})")

            return itemlist
        except Exception as err:
            print("上传文件失败{}".format(err))
            return itemlist

    def get_coppy_file(self, old_file_id, new_file_name):
        """
        复制文件夹内的文件
        param old_file_id :要复制的文件ID
        param new_file_name : 复制后文件的名称
        """

        # 构造请求体并发送请求
        try:
            request_body = {
                "name": new_file_name
            }
            # origin_file = self.googleservice.files().get(fileId=old_file_id).execute()
            response = self.googleservice.files().copy(
                fileId=old_file_id,
                body=request_body,
                supportsAllDrives=True
            ).execute()
            # print(f"{response.get('name')} copied to {response.get('id')}.")
            newname = response.get('name')
            newid = response.get('id')
            print(f'复制文件成功 name:{newname} id{newid}')
            return newname, newid
        except Exception as err:
            print("复制文件出错: {}".format(err))

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
            folder = self.googleservice.files().create(
                body=file_metadata,
                fields='id, name, webViewLink',
                supportsAllDrives=True  # 必须开启此参数
            ).execute()

            folder_id = folder['id']

            # 打印新文件夹的ID
            print(f"已创建新文件夹，ID为{folder_id}")
            return folder_id
        except Exception as err:
            print("创建文件夹出错：{}".format(err))
            return folder_id

    def show_shared_files(self, sharedfileid):
        """列出共享文件夹内文件"""

        nameidlist = []
        folder_id = sharedfileid  # '共享文件夹的ID'  # 替换为共享文件夹的ID
        # results = self.googleservice.files().list(
        #     q=f"'{folder_id}' in parents",  # 查询条件：列出该文件夹下的文件
        #     fields="files(id, name)"
        # ).execute()
        # items = results.get('files', [])

        # 查询共享文件夹中的文件
        query = f"'{folder_id}' in parents and trashed = false"
        results = self.googleservice.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name)",
            supportsAllDrives=True,  # 如果是共享驱动器需启用
            includeItemsFromAllDrives=True
        ).execute()
        items = results.get('files', [])

        if not items:
            print('No files found.')
        else:
            print('Files:')
            for item in items:
                print(f"{item['name']} ({item['id']})")
                nameidlist.append({"name": item['name'], 'id': item['id']})
        return nameidlist

    def move_files(self, moveitemid, dest_folder_id):
        """移动文件"""
        # 移动每个文件

        try:
            # 获取当前父文件夹
            # file = self.googleservice.files().get(
            #     fileId=moveitemid,
            #     fields='parents'
            # ).execute()

            result = self.googleservice.files().get(
                fileId=dest_folder_id,
                fields='id, name, mimeType, parents',
                supportsAllDrives=True
            ).execute()
            # 获取当前父文件夹
            current_parents = ",".join(result.get('parents', []))
            # 更新父文件夹
            updated_file = self.googleservice.files().update(
                fileId=moveitemid,
                addParents=dest_folder_id,
                removeParents=current_parents,
                fields='id, parents',
                supportsAllDrives=True
            ).execute()
            print(f"Moved: {moveitemid}")
            if moveitemid == updated_file["id"]:
                return True
            else:
                return False
        except HttpError as error:
            print(f"Error moving {moveitemid}: {error}")
            return False

    def move_file_Multi_level(self, file_id, dest_folder_id):
        """
        安全移动文件到目标文件夹，支持个人盘和共享盘（跨级移动）。
        
        :param file_id: 要移动的文件ID
        :param dest_folder_id: 目标文件夹ID
        :return: dict {'file_id', 'success', 'parents', 'error'}
        """
        result_item = {
            'file_id': file_id,
            'success': "False",
            'parents': None,
            'error': None
        }

        try:
            # 获取文件当前父文件夹
            file_metadata = self.googleservice.files().get(
                fileId=file_id,
                fields='parents, name',
                supportsAllDrives=True
            ).execute()

            current_parents = file_metadata.get('parents', [])
            file_name = file_metadata.get('name', '')

            # 如果文件已经在目标文件夹，不做任何操作
            if dest_folder_id in current_parents and len(current_parents) == 1:
                result_item['success'] = "True"
                result_item['parents'] = current_parents
                return result_item

            # 对共享盘文件，保证至少有一个父文件夹
            # 1. 如果文件在共享盘且父文件夹数量为1，只移除非目标文件夹
            # 2. 如果父文件夹数量 >1，移除所有非目标父文件夹
            parents_to_remove = [p for p in current_parents if p != dest_folder_id]

            updated_file = self.googleservice.files().update(
                fileId=file_id,
                addParents=dest_folder_id,
                removeParents=",".join(parents_to_remove) if parents_to_remove else None,
                fields='id, parents, name',
                supportsAllDrives=True
            ).execute()

            result_item['success'] = "True"
            result_item['parents'] = updated_file.get('parents', [])
            print(f"Moved: {file_name} ({file_id})")

        except Exception as err:
            result_item['error'] = str(err)
            print(f"Error moving {file_id}: {err}")

        return result_item

    def rename(self, file_id, new_name):
        result = self.verify_file(file_id)
        if not result:
            print(f"{file_id} not found.")
            return None
        try:
            # 构建更新请求
            body = {
                'name': new_name
            }

            # 更新文件元数据
            result = self.googleservice.files().update(
                fileId=file_id,
                body=body,
                fields='id, name',
                supportsAllDrives=True
            ).execute()

            print(f"✅ 成功将文件重命名为: '{result.get('name')}'")
            print(f"📄 文件ID: {result.get('id')}")
            return True
        except HttpError as err:
            print("rename 失败: {}".format(err))
            return None

    def verify_file(self, _id):
        try:
            file_info = self.googleservice.files().get(
                fileId=_id,
                fields='id, name, mimeType',
                supportsAllDrives=True
            ).execute()
            print(f"✅ 文件存在: {file_info.get('name')}")
            return True
        except HttpError as err:
            return False

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
            file_info = self.googleservice.files().get(
                fileId=file_id,
                fields='id, name, mimeType, capabilities/canRename',
                supportsAllDrives=True
            ).execute()

            print(f"📄 文件: {file_info.get('name')}")

            # 2. 检查文件的canRename能力
            capabilities = file_info.get('capabilities', {})
            if capabilities.get('canRename'):
                print("✅ 文件支持重命名")
            else:
                print("❌ 文件不支持重命名（可能是只读文件）")
                return False, {}

            # 3. 获取详细的权限信息
            permissions = self.googleservice.permissions().list(
                fileId=file_id,
                fields='permissions(id, emailAddress, role, type, displayName)',
                supportsAllDrives=True
            ).execute()

            service_account_email = self.creds.service_account_email
            print(f"👤 当前服务账号: {service_account_email}")

            # 4. 检查服务账号的权限
            has_rename_permission = False
            permission_details = {}

            print("\n🔍 权限列表:")
            for perm in permissions.get('permissions', []):
                perm_email = perm.get('emailAddress', '')
                perm_role = perm.get('role', '')
                perm_type = perm.get('type', '')

                print(f"   - {perm_email}: {perm_role} ({perm_type})")

                if perm_email == service_account_email:
                    has_rename_permission = perm_role in ['owner', 'writer']
                    permission_details = perm
                    break

            if has_rename_permission:
                print(f"✅ 有重命名权限: {permission_details.get('role')}")
            else:
                print("❌ 没有重命名权限")
                print("💡 需要的权限: writer 或 owner")

            return has_rename_permission, permission_details

        except HttpError as err:
            print(f"❌ 检查权限时发生HTTP错误: {err}")
            if err.resp.status == 403:
                print("💡 错误403: 没有查看权限的权限")
            return False, {}
        except Exception as err:
            print(f"❌ 检查权限时发生错误: {err}")
            return False, {}


if __name__ == "__main__":
    aa = googledrive()
    print(aa.check_rename_permission("1vpZ6x2PZvdih1brnz6SOEPNpBJG1YuLo6CCNnSoROok"))
