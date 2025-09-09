import os
import paramiko
import base64
import io
from typing import Optional

key_str = """
LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0NCmIzQmxibk56YUMxclpYa3RkakVBQUFBQUJHNXZibVVBQUFBRWJtOXVaUUFBQUFBQUFBQUJBQUFDRndBQUFBZHpjMmd0Y24NCk5oQUFBQUF3RUFBUUFBQWdFQTBxTm9kUHkzNERQY0NSYW5BcnlxaUJiMEtDbzBhTHlVM1dTZzRWMVQ4WWJ2MVU4Smg3Y2INCjNySHY3a3hDMXdSYlFhUS9Db0tEeVZmbVRXbVZNUnlralp5Y08wSmx4SWFyNjNKc3JHc0g5WjVTT3hhcHVnTVp2UC80L0gNCnV6YVdMcjdRZW1Nd2ZNZjY2NGtpaWtESkdYa1RBNnc1bExwVFZCZDROand4ejJKa3FSaU1sb2lla1p1TTEybThQTWlZN3UNCmQrN2IvRy9kVzVSNEFmZW96MGdGNjZiYUF3Wnc1RURWNTZ5WWZiS3BacnlJeEVMT0VlMFhpVThGRnhWV1kvWXpqbTRiakcNCnQrNHEzb25yOEszaWJuUjArQi80ZGhwMDdUUnBjNGJhYXlXd25jL0hCSGcxeHRDN1JEeWx3RmhrY2t4VTdDUkxTWmNHczgNCmRVR0lTMFhVSkZMVDZ3S1lLTGJiYzA2NmcydFBKNXRDVXdWUmY4THNPc3NqR1FEOE9qOC9FTGFyT2RWMURDaDhvNVVURmoNCjZ6NGV3ZFdTMndRVXl6TTlaVW1pOTY4RnB6TmYzbXJ5dllQeGYxVndxV2pvRldoanNiK3BBUUYwcEpEV2svM3BZNFgyOG4NCklabU9CU0QzSS9PdGdTWnFEK3RubnFuZzBhU0dqSnNwSnFkV0tTUEM3cFJ0QzBVU3dNRDEyNHlITm9yaUZRQXdoMDMxaGsNCmFZbXloU3NQVjlDRTM1dFVHL3V4RzZqcTVwaEF2YkwyZkV4aG5BN0tRZHZSTE9kNUJwZWNEbGsrcWlEYzFKL2xVT252MUENCnFrMG9yaU4vSkdiMi81cGwvUHBDNDRqUEduZnhTS2V2ZFpYQmdXNUlmdUNMMFdNUTMrSXZNeXJ5Mnlmd0pQdDJWbFpIRzUNCjhBQUFkWVc3azltMXU1UFpzQUFBQUhjM05vTFhKellRQUFBZ0VBMHFOb2RQeTM0RFBjQ1JhbkFyeXFpQmIwS0NvMGFMeVUNCjNXU2c0VjFUOFlidjFVOEpoN2NiM3JIdjdreEMxd1JiUWFRL0NvS0R5VmZtVFdtVk1SeWtqWnljTzBKbHhJYXI2M0pzckcNCnNIOVo1U094YXB1Z01adlAvNC9IdXphV0xyN1FlbU13Zk1mNjY0a2lpa0RKR1hrVEE2dzVsTHBUVkJkNE5qd3h6MkprcVINCmlNbG9pZWtadU0xMm04UE1pWTd1ZCs3Yi9HL2RXNVI0QWZlb3owZ0Y2NmJhQXdadzVFRFY1NnlZZmJLcFpyeUl4RUxPRWUNCjBYaVU4RkZ4VldZL1l6am00YmpHdCs0cTNvbnI4SzNpYm5SMCtCLzRkaHAwN1RScGM0YmFheVd3bmMvSEJIZzF4dEM3UkQNCnlsd0Zoa2NreFU3Q1JMU1pjR3M4ZFVHSVMwWFVKRkxUNndLWUtMYmJjMDY2ZzJ0UEo1dENVd1ZSZjhMc09zc2pHUUQ4T2oNCjgvRUxhck9kVjFEQ2g4bzVVVEZqNno0ZXdkV1Myd1FVeXpNOVpVbWk5NjhGcHpOZjNtcnl2WVB4ZjFWd3FXam9GV2hqc2INCitwQVFGMHBKRFdrLzNwWTRYMjhuSVptT0JTRDNJL090Z1NacUQrdG5ucW5nMGFTR2pKc3BKcWRXS1NQQzdwUnRDMFVTd00NCkQxMjR5SE5vcmlGUUF3aDAzMWhrYVlteWhTc1BWOUNFMzV0VUcvdXhHNmpxNXBoQXZiTDJmRXhobkE3S1FkdlJMT2Q1QnANCmVjRGxrK3FpRGMxSi9sVU9udjFBcWswb3JpTi9KR2IyLzVwbC9QcEM0NGpQR25meFNLZXZkWlhCZ1c1SWZ1Q0wwV01RMysNCkl2TXlyeTJ5ZndKUHQyVmxaSEc1OEFBQUFEQVFBQkFBQUNBRXlBSUozc2N2T3dvZ2VDL0tFWDJHK1l0cEFuMCtUK0tLckgNCnMwNW1VT2gxYzRGck5URGZKZllaZGVSOE9nSlJpTHNzWmVEeFNkL0VWdFppdEZhajZuZXNHMm5DVWFld3FadlhjUFNsNHINCndvQmdHRDE1ekJKNFhuQ1l6WmVHMmNDY2VLY2FneSt1aWNrbGd5L25HNkp1d0tNaTE3N1dkUkVqZlB0bG5VbU9tTFI1UUENCllrRkVNWjFXc2U4Y2k1cWlHS1hpVUc4OFNZN0xPMUtybWRtK2RMZ0RYMGFkL2o1SDllZ3dYU201eTZDT2RMV2k5YWk1RFUNClZITjdnTWZkWE1ReWxGZ0NmZG1yWEZKNmtRQldodGhLMzNpR1UvekEyeHFUWUlFZXh4RUhIVUFUaUZwdE5rckE0R0tHREUNClR4VlhuVmt6bzRiRWVMM0ZsSzJaWVdERk9haFdYZzJ6c2R3UzhMbGdFTmdNclBXQkgyQ2pFVE11ZEMrdCtlMjJHS0EyR3ANCjRwT3A1a3laSFBubC9MU0pGbFdyNTVhVXBPbzViUVRydVkvdTRKOGYzcndER09hQ2FCT2NBNDZFd3czQlZXeHU2Q0UrNSsNCnltOXlyaktYdG1Vd1VPYkR1NUxZZmRTUDdTSnJ2WWN3MTY0SytZZjZ1Nk5uazBlSmVpNlJTdE1ISmxYMStaWWNzZGtJVjcNClRrd3FPVHBjbkZLd0NHRkRxc0xhR0RPeFdVdFI0RldHRjNDWjZzcUxmWUw3ZU5BYVFQZlVxU1A4MjRGVitaNGFzZXM1Z1QNCmhTUlBvVXVLQUFkSUlyMGlwd1JUdXhCSmtIcmh2RFBCVlQyMTdNN09aR0V1WlFqSDlMbityVUlMQUVhY1R4ZUJ4NVlqOFANCm1BZ0FOTnhiN3hLbmQ1K0k5eEFBQUJBRnhLNjVKeHUycGdyUnRRKzN3YmNmL21ZM2hHaFRHVHZqanNtVm4zVlpSOXAyeUgNCmxSYWJiRkZhLzlsMTVTTWNMT3JBeldNKzZuNUZPdllCLzdyeC8vYUpLRUozUENhZS9VTGNETVFxdDZTQ0tvbGNuODhuYVQNCnIvM2lwaldIUzA2dXRHR0NmV2UxQlhGT21xc3Q2eXEwd3NPWms3by9ScXBZUFJUdGoraUp5QmZqTmJGNnJYMklsVVExRGwNCmVQKzlUZjBwSjFBQk1BMElTUk9SRFphWTFyQUlyZHhSUFVOdGp4cWFDR2x4eUg2cG1nVlIvZjdqbFg2Ny85NndOMncxeFoNCkVtR3MyUkdZcmVnWko1dUlrd3ZmalVvVzZBZnhvNXJOMUMzMEZDbFVQcjB0SEdEdFJQTzhsZDdFaEJHUXJFNkJLa2h3bXgNCituWXJyZlk1UkViT1ZIVUFBQUVCQVB1RDBtT1VnMlNHM1VzRlhyTzZpSnkwYnRPQ2JLc3p3bFlGN3NoemwrV3BqMGpUcE8NCjZwQ3dQRXNIVkdSZFA0S2hzK2hlM3JqZENJUENFQlQ0SXlpY0ROMVJBSk9mWVd0cWJSYmF0bnJYaFpyNTExMlFsKzZwZ2INClZGMkw5VkczWExBWFUzSzI5TVB2QkNkSHhoMDhoR015QVAxWFdXQzVMWUpXTjZtaWplSGJuZ0k0SWdPKzVkcVFJMFI2eWYNCnRRQ0JmM01KOFBwMC8vWFJlN05kd09SSXFjdnJ5c2dpR0phUHpOL3k5M1hUUlJrR2Nuemo0REg4V2o4eUpOS3RjTzlxb1INClF5R3JCRUVCaFlTV0NDTXlXaFE1ZkhIWFNFc05ndlRKN2RPdDRpWUgzVjJCRGNEUmg2a0FHYzhJWXJWQ2lXOXhET21ySjENCmplMDloTEZTMXM1NnNBQUFFQkFOWmsrMytNZFBwdHdBOUJyQmI0Vjl0MTdsSkZPeEE5MjRqU2NKVVhUOTZrRU1kWEZJZ1ENClVQcU9McHJ5Q3NGS2pUT0xBQ29XS3h1UlZxanQ4WFpTaUtlUDhKZmp1cXpReE1CTFgwS1NJTEtqOFNDMW9sTVU3UGdTTE8NCkhnQ3FxTTJmK0JJN01QekU1TTAzSjdtTm5veVhualNLa1Q3dTFIU0YrWTlpTmxJYk5BTlBnc09FaG5zT01wcTMrK3VUTmgNCnp0YVRxbTlDeWgxc0hibU5lRGdaZlBIU2Q3M1BGRTFub1BEZ0hxZkMvckhWTzlyTU9vN0U1YmI4VFNTMVExOGxKdW03RWINCi9wQzlndnQ5eWxwMmVOM3luSllpY1U4ZE1HSk1MMG5oVEdpUG9sT2wwU3MwRkxtcHFsSEVxRkxUdlVmWnBhaWZhVUM5clkNCklqRG1NcTJZVjkwQUFBQWRZbkpoZVdGdVlXeHRiMjUwWlVCWFV5MURNREpJUkRCWVdsRXdOVTRCQWdNRUJRWT0NCi0tLS0tRU5EIE9QRU5TU0ggUFJJVkFURSBLRVktLS0tLQ0K
"""


class FlexConnector:
    def __init__(self, host_name):
        self.ssh: Optional[paramiko.SSHClient, None] = None
        self.sftp: Optional[paramiko.SFTP, None] = None
        self.ip = host_name

    def connect(self, password=None, port=22, timeout=10):
        """建立 SSH 和 SFTP 连接"""
        username = 'root'
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if not password:
                # password = input(f"Enter SSH password for {username}@{host} (默认回车无密码) :")
                password = "None"
            self.ssh.connect(self.ip, port=port, username=username, password=password, timeout=timeout)
            self.sftp = self.ssh.open_sftp()
            print("✅ SSH 连接成功！")
            return True
        except paramiko.AuthenticationException:
            print("连接失败：尝试用密钥连接")
            if os.path.exists("./robot_key"):
                key_file = os.path.join(os.getcwd(), 'robot_key').replace('\\', '/')
                key = paramiko.RSAKey.from_private_key_file(key_file)
            else:
                key_data = base64.b64decode(key_str.strip())
                key = paramiko.RSAKey.from_private_key(io.StringIO(key_data.decode("utf-8")))
            self.ssh.connect(self.ip, port=port, username=username, password=password, timeout=timeout, pkey=key)
            self.sftp = self.ssh.open_sftp()
            print("✅ SSH 连接成功！")
            return True
        except Exception as e:
            print(f"❌ SSH 密钥连接失败: \n")
            print(e)
            return False
