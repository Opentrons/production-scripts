import paramiko
import json
import os,sys

addpathpat = os.path.dirname(__file__)
addpath = os.path.dirname(os.path.dirname(__file__))
addpath2 = os.path.dirname(addpath)
if addpath not in sys.path:
    sys.path.append(addpath)
if addpath2 not in sys.path:
    sys.path.append(addpath2)
if addpathpat not in sys.path:
    sys.path.append(addpathpat)
from tools.inquirer import prompt_raspNo, prompt_openweb

def modify_json_file(host, username, password, json_file_path,key_valune_list):
    # 建立 SSH 连接
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(hostname=host, username=username, password=password)

    # 读取 JSON 文件内容
    sftp_client = ssh_client.open_sftp()
    with sftp_client.open(json_file_path) as file:
        data = json.load(file)

    for ii in key_valune_list:
        # 修改 JSON 文件内容
        data[ii[0]] = ii[1]

    # 写入修改后的 JSON 数据到文件中
    with sftp_client.open(json_file_path, 'w') as file:
        json.dump(data, file, indent=4)

    # 关闭连接
    sftp_client.close()
    ssh_client.close()

def openweb():
    json_file_path=os.path.join(os.getcwd(),"assets","gravapp","addr.json")
    name = prompt_raspNo()
    use_key: str = prompt_openweb()
    try:    
        with open(json_file_path, 'r') as load_f:
            datalis = json.load(load_f)
    except:
        print("openweb.json文件读取失败")

    # 树莓派的 SSH 访问信息
    host = datalis[name][0]
    openweburl = datalis[name][1]
    username = "opentrons"
    password = "opentrons"

    # 要修改的 JSON 文件路径
    json_file_path = "/home/opentrons/openweb.json"
    # 要修改的键和新值

    print(host,openweburl)
    
    if "Y" in use_key.strip().upper():
        opentype = 1
    else:
        opentype = 0
    
    key_to_modify = [["openweb",opentype],["urladdr",openweburl]]
    # 调用函数修改 JSON 文件内容
    modify_json_file(host, username, password, json_file_path, key_to_modify)


if __name__ == "__main__":
    openweb()
    
