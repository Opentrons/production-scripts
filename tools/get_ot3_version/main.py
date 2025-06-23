import csv
import os
import paramiko
import base64
import io

from paramiko import file

from discover_flex import scan_flex
from PyInquirer import prompt
import json
import requests
from discover_flex import headers, TIME_OUT
from datetime import date

LOAD_KEY_BY_STR = True

key_str = """
LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0NCmIzQmxibk56YUMxclpYa3RkakVBQUFBQUJHNXZibVVBQUFBRWJtOXVaUUFBQUFBQUFBQUJBQUFDRndBQUFBZHpjMmd0Y24NCk5oQUFBQUF3RUFBUUFBQWdFQTBxTm9kUHkzNERQY0NSYW5BcnlxaUJiMEtDbzBhTHlVM1dTZzRWMVQ4WWJ2MVU4Smg3Y2INCjNySHY3a3hDMXdSYlFhUS9Db0tEeVZmbVRXbVZNUnlralp5Y08wSmx4SWFyNjNKc3JHc0g5WjVTT3hhcHVnTVp2UC80L0gNCnV6YVdMcjdRZW1Nd2ZNZjY2NGtpaWtESkdYa1RBNnc1bExwVFZCZDROand4ejJKa3FSaU1sb2lla1p1TTEybThQTWlZN3UNCmQrN2IvRy9kVzVSNEFmZW96MGdGNjZiYUF3Wnc1RURWNTZ5WWZiS3BacnlJeEVMT0VlMFhpVThGRnhWV1kvWXpqbTRiakcNCnQrNHEzb25yOEszaWJuUjArQi80ZGhwMDdUUnBjNGJhYXlXd25jL0hCSGcxeHRDN1JEeWx3RmhrY2t4VTdDUkxTWmNHczgNCmRVR0lTMFhVSkZMVDZ3S1lLTGJiYzA2NmcydFBKNXRDVXdWUmY4THNPc3NqR1FEOE9qOC9FTGFyT2RWMURDaDhvNVVURmoNCjZ6NGV3ZFdTMndRVXl6TTlaVW1pOTY4RnB6TmYzbXJ5dllQeGYxVndxV2pvRldoanNiK3BBUUYwcEpEV2svM3BZNFgyOG4NCklabU9CU0QzSS9PdGdTWnFEK3RubnFuZzBhU0dqSnNwSnFkV0tTUEM3cFJ0QzBVU3dNRDEyNHlITm9yaUZRQXdoMDMxaGsNCmFZbXloU3NQVjlDRTM1dFVHL3V4RzZqcTVwaEF2YkwyZkV4aG5BN0tRZHZSTE9kNUJwZWNEbGsrcWlEYzFKL2xVT252MUENCnFrMG9yaU4vSkdiMi81cGwvUHBDNDRqUEduZnhTS2V2ZFpYQmdXNUlmdUNMMFdNUTMrSXZNeXJ5Mnlmd0pQdDJWbFpIRzUNCjhBQUFkWVc3azltMXU1UFpzQUFBQUhjM05vTFhKellRQUFBZ0VBMHFOb2RQeTM0RFBjQ1JhbkFyeXFpQmIwS0NvMGFMeVUNCjNXU2c0VjFUOFlidjFVOEpoN2NiM3JIdjdreEMxd1JiUWFRL0NvS0R5VmZtVFdtVk1SeWtqWnljTzBKbHhJYXI2M0pzckcNCnNIOVo1U094YXB1Z01adlAvNC9IdXphV0xyN1FlbU13Zk1mNjY0a2lpa0RKR1hrVEE2dzVsTHBUVkJkNE5qd3h6MkprcVINCmlNbG9pZWtadU0xMm04UE1pWTd1ZCs3Yi9HL2RXNVI0QWZlb3owZ0Y2NmJhQXdadzVFRFY1NnlZZmJLcFpyeUl4RUxPRWUNCjBYaVU4RkZ4VldZL1l6am00YmpHdCs0cTNvbnI4SzNpYm5SMCtCLzRkaHAwN1RScGM0YmFheVd3bmMvSEJIZzF4dEM3UkQNCnlsd0Zoa2NreFU3Q1JMU1pjR3M4ZFVHSVMwWFVKRkxUNndLWUtMYmJjMDY2ZzJ0UEo1dENVd1ZSZjhMc09zc2pHUUQ4T2oNCjgvRUxhck9kVjFEQ2g4bzVVVEZqNno0ZXdkV1Myd1FVeXpNOVpVbWk5NjhGcHpOZjNtcnl2WVB4ZjFWd3FXam9GV2hqc2INCitwQVFGMHBKRFdrLzNwWTRYMjhuSVptT0JTRDNJL090Z1NacUQrdG5ucW5nMGFTR2pKc3BKcWRXS1NQQzdwUnRDMFVTd00NCkQxMjR5SE5vcmlGUUF3aDAzMWhrYVlteWhTc1BWOUNFMzV0VUcvdXhHNmpxNXBoQXZiTDJmRXhobkE3S1FkdlJMT2Q1QnANCmVjRGxrK3FpRGMxSi9sVU9udjFBcWswb3JpTi9KR2IyLzVwbC9QcEM0NGpQR25meFNLZXZkWlhCZ1c1SWZ1Q0wwV01RMysNCkl2TXlyeTJ5ZndKUHQyVmxaSEc1OEFBQUFEQVFBQkFBQUNBRXlBSUozc2N2T3dvZ2VDL0tFWDJHK1l0cEFuMCtUK0tLckgNCnMwNW1VT2gxYzRGck5URGZKZllaZGVSOE9nSlJpTHNzWmVEeFNkL0VWdFppdEZhajZuZXNHMm5DVWFld3FadlhjUFNsNHINCndvQmdHRDE1ekJKNFhuQ1l6WmVHMmNDY2VLY2FneSt1aWNrbGd5L25HNkp1d0tNaTE3N1dkUkVqZlB0bG5VbU9tTFI1UUENCllrRkVNWjFXc2U4Y2k1cWlHS1hpVUc4OFNZN0xPMUtybWRtK2RMZ0RYMGFkL2o1SDllZ3dYU201eTZDT2RMV2k5YWk1RFUNClZITjdnTWZkWE1ReWxGZ0NmZG1yWEZKNmtRQldodGhLMzNpR1UvekEyeHFUWUlFZXh4RUhIVUFUaUZwdE5rckE0R0tHREUNClR4VlhuVmt6bzRiRWVMM0ZsSzJaWVdERk9haFdYZzJ6c2R3UzhMbGdFTmdNclBXQkgyQ2pFVE11ZEMrdCtlMjJHS0EyR3ANCjRwT3A1a3laSFBubC9MU0pGbFdyNTVhVXBPbzViUVRydVkvdTRKOGYzcndER09hQ2FCT2NBNDZFd3czQlZXeHU2Q0UrNSsNCnltOXlyaktYdG1Vd1VPYkR1NUxZZmRTUDdTSnJ2WWN3MTY0SytZZjZ1Nk5uazBlSmVpNlJTdE1ISmxYMStaWWNzZGtJVjcNClRrd3FPVHBjbkZLd0NHRkRxc0xhR0RPeFdVdFI0RldHRjNDWjZzcUxmWUw3ZU5BYVFQZlVxU1A4MjRGVitaNGFzZXM1Z1QNCmhTUlBvVXVLQUFkSUlyMGlwd1JUdXhCSmtIcmh2RFBCVlQyMTdNN09aR0V1WlFqSDlMbityVUlMQUVhY1R4ZUJ4NVlqOFANCm1BZ0FOTnhiN3hLbmQ1K0k5eEFBQUJBRnhLNjVKeHUycGdyUnRRKzN3YmNmL21ZM2hHaFRHVHZqanNtVm4zVlpSOXAyeUgNCmxSYWJiRkZhLzlsMTVTTWNMT3JBeldNKzZuNUZPdllCLzdyeC8vYUpLRUozUENhZS9VTGNETVFxdDZTQ0tvbGNuODhuYVQNCnIvM2lwaldIUzA2dXRHR0NmV2UxQlhGT21xc3Q2eXEwd3NPWms3by9ScXBZUFJUdGoraUp5QmZqTmJGNnJYMklsVVExRGwNCmVQKzlUZjBwSjFBQk1BMElTUk9SRFphWTFyQUlyZHhSUFVOdGp4cWFDR2x4eUg2cG1nVlIvZjdqbFg2Ny85NndOMncxeFoNCkVtR3MyUkdZcmVnWko1dUlrd3ZmalVvVzZBZnhvNXJOMUMzMEZDbFVQcjB0SEdEdFJQTzhsZDdFaEJHUXJFNkJLa2h3bXgNCituWXJyZlk1UkViT1ZIVUFBQUVCQVB1RDBtT1VnMlNHM1VzRlhyTzZpSnkwYnRPQ2JLc3p3bFlGN3NoemwrV3BqMGpUcE8NCjZwQ3dQRXNIVkdSZFA0S2hzK2hlM3JqZENJUENFQlQ0SXlpY0ROMVJBSk9mWVd0cWJSYmF0bnJYaFpyNTExMlFsKzZwZ2INClZGMkw5VkczWExBWFUzSzI5TVB2QkNkSHhoMDhoR015QVAxWFdXQzVMWUpXTjZtaWplSGJuZ0k0SWdPKzVkcVFJMFI2eWYNCnRRQ0JmM01KOFBwMC8vWFJlN05kd09SSXFjdnJ5c2dpR0phUHpOL3k5M1hUUlJrR2Nuemo0REg4V2o4eUpOS3RjTzlxb1INClF5R3JCRUVCaFlTV0NDTXlXaFE1ZkhIWFNFc05ndlRKN2RPdDRpWUgzVjJCRGNEUmg2a0FHYzhJWXJWQ2lXOXhET21ySjENCmplMDloTEZTMXM1NnNBQUFFQkFOWmsrMytNZFBwdHdBOUJyQmI0Vjl0MTdsSkZPeEE5MjRqU2NKVVhUOTZrRU1kWEZJZ1ENClVQcU9McHJ5Q3NGS2pUT0xBQ29XS3h1UlZxanQ4WFpTaUtlUDhKZmp1cXpReE1CTFgwS1NJTEtqOFNDMW9sTVU3UGdTTE8NCkhnQ3FxTTJmK0JJN01QekU1TTAzSjdtTm5veVhualNLa1Q3dTFIU0YrWTlpTmxJYk5BTlBnc09FaG5zT01wcTMrK3VUTmgNCnp0YVRxbTlDeWgxc0hibU5lRGdaZlBIU2Q3M1BGRTFub1BEZ0hxZkMvckhWTzlyTU9vN0U1YmI4VFNTMVExOGxKdW03RWINCi9wQzlndnQ5eWxwMmVOM3luSllpY1U4ZE1HSk1MMG5oVEdpUG9sT2wwU3MwRkxtcHFsSEVxRkxUdlVmWnBhaWZhVUM5clkNCklqRG1NcTJZVjkwQUFBQWRZbkpoZVdGdVlXeHRiMjUwWlVCWFV5MURNREpJUkRCWVdsRXdOVTRCQWdNRUJRWT0NCi0tLS0tRU5EIE9QRU5TU0ggUFJJVkFURSBLRVktLS0tLQ0K
"""
test_name_list = ['1.OT3-Diagnostic-QC-Not-Finished',
                  '2.OT3-Diagnostic-QC-Finished',
                  '3.OT3-Stress',
                  '4.OT3-XY-Belt-Calibration',
                  '5.OT3-Protocol-QC']


def select_flex(flex_list):
    questions = [
        {
            'type': 'list',
            'name': 'flex',
            'message': 'Select Flex:',
            'choices': flex_list,
        }
    ]
    answers = prompt(questions)
    return answers['flex']


def select_test_name():
    questions = [
        {
            'type': 'list',
            'name': 'test_name',
            'message': 'Select Test Name:',
            'choices': test_name_list,
        }
    ]
    answers = prompt(questions)
    return answers['test_name']


class GetVersion:
    def __init__(self):
        self.ssh = None
        self.sftp = None

    def connect(self, host, username, password=None, port=22, timeout=10):
        """建立 SSH 和 SFTP 连接"""
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if not password:
                password = input(f"Enter SSH password for {username}@{host} (默认回车无密码) :")
                password = password if password != "" else "None"
            self.ssh.connect(host, port=port, username=username, password=password, timeout=timeout)
            self.sftp = self.ssh.open_sftp()
            print("✅ SSH 连接成功！")
            return True
        except Exception as e:
            if "publickey" in str(e):
                try:
                    print("ssh with publickey...")
                    if LOAD_KEY_BY_STR:
                        key_data = base64.b64decode(key_str.strip())
                        key = paramiko.RSAKey.from_private_key(io.StringIO(key_data.decode("utf-8")))
                    else:
                        key_file = os.path.join(os.getcwd(), 'robot_key').replace('\\', '/')
                        print(f'key path: {key_file}')
                        key = paramiko.RSAKey.from_private_key_file(key_file)

                    self.ssh.connect(host, port=port, username=username, password=password,
                                     timeout=timeout, pkey=key)
                    self.sftp = self.ssh.open_sftp()
                    print("✅ SSH 连接成功！")
                    return True
                except Exception as e:
                    print(f"❌ SSH 密钥连接失败: \n")
                    return False
            else:
                print(f"❌ SSH 连接失败: \n")
                return False

    def remote_file_exists(self, file_path):
        try:
            self.sftp.stat(file_path)
            return True
        except IOError:
            return False

    def read_file(self, file_path):
        """
        read file in remote server
        """
        ret = self.remote_file_exists(file_path)
        if ret:
            with self.sftp.open(file_path, "r") as remote_file:
                content = remote_file.read().decode("utf-8")  # 读取内容并解码
                return content
        else:
            return "file not found"

    def answer_handler(self, answer):
        """
        judge answer
        """
        if "NOT FOUND" in answer:
            ip = input("Please enter your ip address: ").strip()
        else:
            ip = answer.split('-')[1].strip()
        ret = self.connect(ip, 'root')
        if ret:
            test_version = self.read_file('/data/.hardware-testing-description')
            version_str = self.read_file('/etc/VERSION.json')
            if 'file not found' not in version_str:
                version_dict = json.loads(version_str)
            else:
                version_dict = {}
            if 'file not found' not in test_version:
                version_dict.update({"test_version": test_version})
            else:
                version_dict.update({"test_version": 'None'})
        else:
            version_dict = {}

        response = requests.get(f"http://{ip}:31950/health", headers=headers, timeout=TIME_OUT)
        if response.status_code == 200:
            health_message: dict = json.loads(response.text)
            version_dict.update(health_message)
        else:
            print("Get Robot Health Failed, Please Power Cycle Robot (重启机器重新运行！)")
            raise Exception("Get Robot Health Failed")
        for key, value in version_dict.items():
            print(f"{key}: {value}")
        return version_dict

    def is_string_in_csv(self, file_path, target_string):
        with open(file_path, mode='r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            for index, row in enumerate(csv_reader):
                if target_string in row:  # 检查目标字符串是否在当前行
                    return index, row
            return False, False

    def create_report_line(self, test_name):
        line = []
        if 'OT3' in test_name:
            for item in test_name_list:
                if 'OT3' in item:
                    line.append(item)
                    line.extend(['']*5)
        return line


    def save_to_csv(self, version_dict, test_name):
        def replace_next_four_elements(lst, target, replacements):
            try:
                index = lst.index(target)  # 找到目标字符串的索引
                # 确保替换元素不超过列表边界
                end_index = min(index + 6, len(lst))  # index+1到index+4共4个元素
                lst[index + 1:end_index] = replacements[:end_index - index - 1]
                return lst
            except ValueError:
                print(f"'{target}' not found in the list")
                return lst

        def write_specific_row(csv_file, row_index, new_data):
            print("\nwrite to specific row...row_index={}".format(row_index))
            if row_index is None:
                with open(csv_file, 'a', newline='') as f:
                    writer = csv.writer(f)
                    print("new data", new_data)
                    writer.writerow(new_data)
            else:
            # 1. 读取所有行
                with open(csv_file, 'r', newline='') as f:
                    reader = csv.reader(f)
                    print(reader)
                    rows = list(reader)  # 转为列表

                # 2. 检查行索引是否有效
                if row_index < 0 or row_index >= len(rows):
                    raise IndexError("行索引超出范围")

                # 3. 修改指定行
                rows[row_index] = new_data

                # 4. 重新写入整个文件
                with open(csv_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)

        this_date = date.today()
        # list_value = version_dict.values()
        # title = version_dict.keys()

        touch_point = {"robot_name": version_dict.get("name"),
                       "robot_serial": version_dict.get("robot_serial"),
                       "robot_server_version": version_dict.get("api_version"),
                       "fw_version": version_dict.get("fw_version"),
                       "test_version": version_dict.get("test_version"), }
        if "OT3" in test_name:
            file_name = f"VERSION_OT3_{this_date.strftime('%Y%m%d')}.csv"
        else:
            raise

        if os.path.isfile(file_name):
            # check the SN exist
            index1, row1 = self.is_string_in_csv(file_name, touch_point['robot_name'])
            index2, row2 = self.is_string_in_csv(file_name, touch_point['robot_serial'])
            if row1:
                line = row1
                index = index1
            elif row2:
                line = row2
                index = index2
            else:
                line = self.create_report_line(test_name)
                index = None
            # inset to line
            line = replace_next_four_elements(line, test_name, list(touch_point.values()))
            write_specific_row(file_name, index, line)
        else:
            line = self.create_report_line(test_name)
            line = replace_next_four_elements(line, test_name, list(touch_point.values()))
            with open(file_name, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(line)



def main_loop():
    test_name = select_test_name()
    # 获取可用的flex
    flex_group = scan_flex()
    index = 0
    flex_list = []
    for key, value in flex_group.items():
        flex_list.append(f"{index}: {value['name']} - {key}")
        index = index + 1
    flex_list.append("NOT FOUND ? Select Me !")
    result = select_flex(flex_list)
    get_version: GetVersion = GetVersion()
    versions = get_version.answer_handler(result)

    get_version.save_to_csv(versions, test_name)


if __name__ == '__main__':
    main_loop()
