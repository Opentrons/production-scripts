import paramiko
import json
import os,sys

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

if __name__ == "__main__":
    json_file_path=os.path.join(os.path.dirname(sys.argv[0]),"addr.json")
    name = input("请输入要打开的机台编号(GRAV1):")
    try:    
        with open(json_file_path, 'r') as load_f:
            datalis = json.load(load_f)
    except:
        print("openweb.json文件读取失败")



    # 树莓派的 SSH 访问信息
    host = datalis[name][0]
    username = "opentrons"
    password = "opentrons"

    # 要修改的 JSON 文件路径
    json_file_path = "/home/opentrons/openweb.json"
    # 要修改的键和新值
    key_to_modify = [["openweb",222],["urladdr","www.163.com"]]
    # 调用函数修改 JSON 文件内容
    modify_json_file(host, username, password, json_file_path, key_to_modify)
