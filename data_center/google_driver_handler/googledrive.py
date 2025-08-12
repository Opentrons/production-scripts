import os,sys
import io
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.http import MediaIoBaseDownload
from globalconfig import DOWNLOAD_DIR
codepath = os.path.dirname(__file__)
addpath = os.path.dirname(os.path.dirname(__file__))
addpath2 = os.path.dirname(addpath)
if addpath not in sys.path:
    sys.path.append(addpath)
if addpath2 not in sys.path:
    sys.path.append(addpath2)

class googledrive():
    def __init__(self) -> None:
        # # Replace with the path of your client secret file
        # self.CLIENT_SECRET_PATH = 'credentials.json'
        # # Replace with the ID of the folder you want to upload to
        # self.UPLOAD_FOLDER_ID = '1hGwqcTVyG_beQ3qRoTnmKFGYyuZKqFyO'
        # # Replace with the file path of the file you want to upload
        # self.FILE_PATH = 'token.json'
        #self.googleservice = None
        self.tokenpath = os.path.join(codepath,'token.json')
        self.credentialspath = os.path.join(codepath,'credentials.json')
        self.get_drive_service()
    def get_drive_service(self):
    
        SCOPES = [
        'https://www.googleapis.com/auth/drive','https://www.googleapis.com/auth/drive.appdata','https://www.googleapis.com/auth/drive.file']
        creds = None
        #'https://www.googleapis.com/auth/drive.metadata.readonly','https://www.googleapis.com/auth/drive.file','https://www.googleapis.com/auth/drive.appdata'
        if os.path.exists(self.tokenpath):
            creds = Credentials.from_authorized_user_file(self.tokenpath, SCOPES)

        
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentialspath, SCOPES)
            creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open(self.tokenpath, 'w') as token:
                token.write(creds.to_json())
        # Create an authorized Drive API client
        self.googleservice = build('drive', 'v3', credentials=creds)
        return self.googleservice
    
    def upload_to_drive(self,file_path, folder_id):
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
            print('File ID: {}'.format(file.get('id')))
            return upfileid
        except Exception as err:
            print("上传文件失败{}".format(err))
            return upfileid    
    
    def dowload_fail_drive(self,fileid,newname=''):
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
            
            save_fail_path = os.path.join(DOWNLOAD_DIR,file_name)
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
            return file_name,save_fail_path
        except HttpError as error:
            print(f"发生错误：{error}")
            return None,None
    
    def execute_file(self,fileid,extype='xlsx',newname=''):
        """导出Google Workspace 文档 like world Excel
        param fileid 要导出的文件ID
        param extype 需要保存的文件格式
        param newname 新文件的名称
        return name,path
        """

        MIMEDICT = {
            "csv":"text/csv",
            "docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pdf":"application/pdf",
            "txt":"text/plain",
            "xlsx":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "pptx":"application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "json":"application/vnd.google-apps.script+json",
            "jpg":"image/jpeg",

        }
        # 要导出的 Google Drive 文件的 ID 以及导出格式（Excel 文件为 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'）
        file_id = fileid
       
        file = self.googleservice.files().get(fileId=file_id).execute()
        if newname == '':
                
                file_name = file['name']
        else:
            file_name = newname
        
        mimetypeval = MIMEDICT[extype]

        excutepath = os.path.join(DOWNLOAD_DIR,str(file_name)+"."+str(extype))

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
            return file_name,excutepath
        except HttpError as error:
            print(f'导出文件出错: {error}')
            return None,None

    def get_folder_data(self,folder_id):
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
            results = self.googleservice.files().list(q=query, fields="nextPageToken, files(id, name, mimeType)").execute()
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

    def get_folder_data_share(self,folder_id,name):
        """
        获取共享网盘文件夹内的文件名称ID
        param folder_id : google网盘文件夹ID
        return 文件名 ID
        """
        itemlist = []
        try:
            query = "sharedWithMe = true and mimeType != 'application/vnd.google-apps.folder'"
            results = self.googleservice.files().list(q=query, fields="nextPageToken, files({}, {})".format(folder_id,name)).execute()
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

    def get_coppy_file(self,old_file_id,new_file_name):
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
            #origin_file = self.googleservice.files().get(fileId=old_file_id).execute()
            response = self.googleservice.files().copy(
                fileId=old_file_id,
                body=request_body,
                supportsAllDrives=True
            ).execute()
            #print(f"{response.get('name')} copied to {response.get('id')}.")
            newname = response.get('name')
            newid = response.get('id')
            print(f'复制文件成功 name:{newname} id{newid}')
            return newname,newid
        except Exception as err:
            print("复制文件出错: {}".format(err))
    
    def creat_Folders(self,newname,parentfolderid=""):
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
            folder =  self.googleservice.files().create(
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
    def show_shared_files(self,sharedfileid):
        """列出共享文件夹内文件"""

        nameidlist = []
        folder_id = sharedfileid #'共享文件夹的ID'  # 替换为共享文件夹的ID
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
                nameidlist.append({"name":item['name'],'id':item['id']})
        return nameidlist

   
    def move_files(self, moveitemid,dest_folder_id):
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
        except HttpError as error:
            print(f"Error moving {moveitemid}: {error}")

if __name__ == "__main__":
    aa = googledrive()
    #https://drive.google.com/file/d/1wNysMbZp9X_bkzPwwYL43bYqzg7VHopI/view?usp=share_link
    #aa.dowload_fail_drive("1wNysMbZp9X_bkzPwwYL43bYqzg7VHopI","")
    #aaa,bbb=aa.execute_file("17Y6-PDvR9NcVjj-9gegbej7yuEtmDftIMBCP3zX3oVs","xlsx")
    #aa.get_folder_data_share("19GUr0JdUFE8CqSrTgR_baYzlwA9DsePY","GEN3 1CH PIPETTE - DVT - LIFE TESTING-SZ")
    # aaaa = aa.get_folder_data("1BXVEz7RjofiwuDNi3UsQdBUgi7q1loSs")
    # aa.creat_excel("testcreatflo","1myDqYlCuxK7TGBUD53RIxDaRZ_B062lg")
    #aa.get_coppy_file("1p_Z_eVt5fouws_gBYR0INqEejncHodFJad9dh1YBlpw","csssss")
    #aa.show_shared_files("193bdhoabDdf4wGnet-lRdTyM-j2BQHWd")
    #aa.creat_Folders("cs","17o2ZbcHkbDl_DFcEYDqN0OHqGR9W0X1I")
    #aa.upload_to_drive("/Users/yew/googledriver/upload/function/1ch/gravimetric-ot3-p1000-single_run-25-04-23-14-22-40_CSVReport-P1KSV3620250415M05-qc.csv","1FHXTa-vhujNoy33WjbbqqKu3F8e2stcH")
    aa.creat_Folders("测试","1FHXTa-vhujNoy33WjbbqqKu3F8e2stcH")
    #aa.get_coppy_file("1f8e7X_u3807OIFOC6-6BWXBryKO2bnr2DNsCxq3Piek","cs")
