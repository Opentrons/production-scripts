import requests
import json
from typing import Any
import os
from enum import Enum

url = 'http://192.168.0.125:8080/'
testing_data_path = "/root/testing_data_2025-08-14-16-52-59.zip"

class Production(Enum):
    Robot = "Robot"


def _post(api: str, payload: dict[str, Any]):
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url+ api, data=json.dumps(payload), headers=headers)
    state_code = response.status_code
    text = response.json()
    return state_code, text


def upload_testing_data(api: str, file_path: str, ):
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 准备文件数据
        with open(file_path, 'rb') as f:
            files = {
                'file': (os.path.basename(file_path), f, 'application/octet-stream')
            }

            # 发送POST请求
            response = requests.post(url+ api, files=files)

        # 检查响应状态
        response.raise_for_status()

        # 返回JSON响应
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"请求错误: {e}")
        return {"status": "error", "detail": str(e)}
    except Exception as e:
        print(f"其他错误: {e}")
        return {"status": "error", "detail": str(e)}

def upload_to_google_drive(api: str, production: Production , test_name, file_list, sn=""):
    _data = {
        "product_name": production.value,
        "quarter_name": "2025-Q3",
        "sn": sn,
        "files_list": file_list,
        "test_name": test_name,
        "finished": False
    }
    status_code, response = _post(api, _data)
    print(f"status_code: {status_code}, response: {response}")

if __name__ == '__main__':
    datas =  upload_testing_data('api/files/upload/testing_data', testing_data_path)
    formatted_json = json.dumps(datas, indent=4, ensure_ascii=False, sort_keys=True)
    print(formatted_json)
    file_list = datas['files_list']
    test_name = "robot-assembly-qc-ot3"
    sn = ""  # ""代表会上传里面所有的文件
    upload_to_google_drive("api/google/drive/upload/report", Production.Robot, test_name, file_list, sn=sn)

