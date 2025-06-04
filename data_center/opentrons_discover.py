import os
import platform
import subprocess
import ipaddress
import socket
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
import json
import requests

headers = {
    "Content-Type": "application/json",
    "Opentrons-Version": "3"
}

TimeOut = 30


class ScanIP:
    def __init__(self):
        pass

    def get_default_gateway(self):
        """获取默认网关地址（兼容Windows/Linux/macOS）"""
        try:
            if platform.system() == "Windows":
                # 方法1: 使用route命令
                result = subprocess.run(
                    ["route", "print", "0.0.0.0"],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                for line in result.stdout.splitlines():
                    if "0.0.0.0" in line and "On-link" not in line:
                        parts = [p for p in line.split() if p]
                        if len(parts) >= 3 and parts[0] == "0.0.0.0":
                            return parts[2]

                # 方法2: 使用ipconfig作为备选
                result = subprocess.run(
                    ["ipconfig"],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                for line in result.stdout.splitlines():
                    if "Default Gateway" in line:
                        return line.split(":")[-1].strip()

            elif platform.system() == "Linux":
                # 方法1: 读取/proc/net/route
                with open("/proc/net/route") as f:
                    for line in f:
                        fields = line.strip().split()
                        if len(fields) >= 3 and fields[1] == '00000000':
                            return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))

                # 方法2: 使用ip命令作为备选
                result = subprocess.run(
                    ["ip", "route"],
                    capture_output=True,
                    text=True
                )
                for line in result.stdout.splitlines():
                    if "default via" in line:
                        return line.split()[2]

            elif platform.system() == "Darwin":
                # macOS方法
                result = subprocess.run(
                    ["netstat", "-rn"],
                    capture_output=True,
                    text=True
                )
                for line in result.stdout.splitlines():
                    if "default" in line:
                        return line.split()[1]

        except Exception as e:
            print(f"[警告] 获取网关时出错: {str(e)}")
        return None

    def ping_ip(self, ip):
        """Ping检测IP是否在线"""
        try:
            param = "-n" if platform.system().lower() == "windows" else "-c"
            timeout = "-w" if platform.system().lower() == "windows" else "-W"
            timeout_val = "1000" if platform.system().lower() == "windows" else "1"

            command = ["ping", param, "1", timeout, timeout_val, str(ip)]
            if platform.system().lower() == "linux":
                command = ["ping", "-c", "1", "-W", "1", str(ip)]

            with open(os.devnull, 'w') as devnull:
                response = subprocess.run(
                    command,
                    stdout=devnull,
                    stderr=devnull,
                    creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
                )
            return response.returncode == 0
        except Exception:
            return False

    def scan_network(self, gateway, subnet_mask="24"):
        """扫描指定网络"""
        try:
            if not gateway:
                raise ValueError("网关地址不能为空")

            network = ipaddress.IPv4Network(f"{gateway}/{subnet_mask}", strict=False)
            print(f"\n[信息] 正在扫描网络: {network} (共 {network.num_addresses - 2} 个IP)")

            online_ips = []
            lock = threading.Lock()

            def check_ip(ip):
                """内部函数：检查单个IP"""
                if self.ping_ip(ip):
                    with lock:
                        online_ips.append(str(ip))
                        print(f"[发现] 在线设备: {ip}")

            # 修复点：明确传递IP参数给线程
            with ThreadPoolExecutor(max_workers=100) as executor:
                # 使用network.hosts()生成的所有IP作为参数
                executor.map(check_ip, [str(host) for host in network.hosts()])

            return sorted(online_ips, key=lambda x: list(map(int, x.split('.'))))

        except Exception as e:
            print(f"[错误] 扫描失败: {str(e)}")
            return []

    def scan(self):
        gateway = self.get_default_gateway()
        if gateway:
            print(f"[成功] 自动检测到网关: {gateway}")
        else:
            print("[警告] 无法自动检测网关，使用默认网关 192.168.6.1")
            gateway = '192.168.6.1'
        subnet = '24'  # 默认掩码值
        online_devices = self.scan_network(gateway, subnet)
        print(f"\n共发现 {len(online_devices)} 台在线设备")
        return online_devices


class HttpClient:
    Domain = ""

    def __init__(self, addr: str):
        HttpClient.Domain = f"http://{addr}:31950"

    def get(self, api, params=None):
        """
        get method
        :param api:
        :param params:
        :return:
        """
        _url = f"{HttpClient.Domain}{api}"
        response = requests.get(_url, headers=headers, params=params, timeout=TimeOut)
        code = response.status_code
        text = response.text
        return code, json.loads(text)

    def get_flex_info(self):
        try:
            code, data =  self.get('/health')
            print(data['name'])
            return data
        except Exception as e:
            return None


if __name__ == "__main__":
    scan_ip = ScanIP()
    online_devices = scan_ip.scan()
    data_list = []
    for ip in online_devices:
        client = HttpClient(ip)
        data = client.get_flex_info()
        if data:
            data_list.append(data)
    print(f"find {len(data_list)} 个在线设备")
