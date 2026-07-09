import os
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from settings import CREDENTIALS_PATH, SHEET_TOKEN_PATH

SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from upload_handler.utils import runtime_config


def get_skill_config():
    return runtime_config.load_skill_config_module()


def get_proxied_request():
    proxy_url = runtime_config.get_proxy_url()
    skill_config = get_skill_config()
    if proxy_url and skill_config is not None:
        return skill_config.build_google_auth_request(proxy_url=proxy_url)
    return Request()


def get_proxied_flow(credentials_path, scopes):
    """创建带代理的 OAuth flow"""
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
    proxy_url = runtime_config.get_proxy_url()
    skill_config = get_skill_config()
    if proxy_url and skill_config is not None:
        skill_config.apply_oauth_flow_proxy(flow, proxy_url=proxy_url)
    return flow


def build_sheet_service(credentials):
    proxy_url = runtime_config.get_proxy_url()
    skill_config = get_skill_config()
    if proxy_url and skill_config is not None:
        return skill_config.build_google_service("sheets", "v4", credentials, proxy_url=proxy_url)
    return build("sheets", "v4", credentials=credentials)


class SheetDriver:
    def __init__(self) -> None:
        self.credentials_path = CREDENTIALS_PATH
        self.sheet_token_path = SHEET_TOKEN_PATH
        self.sheet_service_client = None
        self.sheet_service = None
        self.connect()

    def connect(self):
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = None
        try:
            if os.path.exists(self.sheet_token_path):
                creds = Credentials.from_authorized_user_file(self.sheet_token_path, scopes)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(get_proxied_request())
                else:
                    print("No valid sheet credentials found, or they are expired, try to login...")
                    flow = get_proxied_flow(self.credentials_path, scopes)
                    creds = flow.run_local_server(port=0)
                with open(self.sheet_token_path, 'w') as token:
                    token.write(creds.to_json())
            self.sheet_service_client = build_sheet_service(creds)
            self.sheet_service = self.sheet_service_client.spreadsheets()
            print("Sheet drive created!")
            return self.sheet_service_client
        except Exception as err:
            print("获取sheet api 出错:{}".format(err))
            return self.sheet_service_client

    def get_sheet_drive(self):
        return self.connect()

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
            print(f"已创建新表格，ID为{spreadsheet_id}")
            return spreadsheet_id
        except Exception as e:
            print("创建表格失败：{}".format(e))
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
            print("获取数据失败{}".format(err))
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
            print("已读取完所有数据。")
            return value_
        except Exception as err:
            print("获取Excel表格数据出错:{}".format(err))
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
            print("更新数据失败{}".format(errval))

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

                print(request)
            return True

        except Exception as errval:
            print("更新数据失败{}".format(errval))
            return False

    def check_sheet_exists(self, spreadsheet_id, sheet_name):
        """
        检查工作表是否存在
        """
        try:
            spreadsheet = self.sheet_service.get(spreadsheetId=spreadsheet_id).execute()
            sheets = spreadsheet.get('sheets', [])

            for sheet in sheets:
                if sheet['properties']['title'] == sheet_name:
                    return True
            return False

        except Exception as e:
            print(f"❌ 检查工作表存在性失败: {e}")
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

                    self.sheet_service.batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=body
                    ).execute()

                    print(f"✅ 已创建新工作表: '{sheet_name}'")
                    return True

                except Exception as e:
                    print(f"❌ 创建工作表失败: {e}")
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

        print(f"📤 准备写入数据到: {range_name}")
        print(f"  总行数: {len(data)}")
        print(f"  总列数: {len(data[0]) if data else 0}")

        body = {
            'values': data
        }

        # 写入数据
        result = self.sheet_service.values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()

        print(f"✅ 成功写入 {result.get('updatedCells')} 个单元格")
        print(f"🎉 数据已成功导入到工作表 '{sheet_name}'")

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

            print(request)
            return True

        except Exception as errval:
            print("更新数据失败{}".format(errval))
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
                request = self.sheet_service_client.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=full_range,
                    valueInputOption=value_input_option,
                    body={'values': new_values}
                ).execute()

            # 情况 2：多个范围
            elif isinstance(ranges, list):
                data = []
                for r, v in zip(ranges, new_values):
                    data.append({
                        "range": f"{sheet_name}{r}",
                        "values": v
                    })

                body = {
                    "valueInputOption": value_input_option,
                    "data": data
                }
                request = self.sheet_service_client.spreadsheets().values().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body=body
                ).execute()
            else:
                raise TypeError("参数 ranges 必须是 str 或 list 类型")

            print("更新成功:", request)
            return True

        except Exception as err:
            print(f"更新数据失败: {err}")
            return False

    def copy_sheet_excel(self, source_spreadsheet_id, target_spreadsheet_id, sheet_id):
        """
        复制工作表
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

            print(f"工作表已复制到目标文件，ID为:{copied_sheet_id}，名称为:{copied_sheet_title}")

            return copied_sheet_title, copied_sheet_id


        except Exception as err:
            print("复制sheet 出错{}".format(err))
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
            print(f"获取工作表信息时出错: {error}")
            return None
