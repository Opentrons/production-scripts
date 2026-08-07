import platform
import os
from concurrent.futures import ThreadPoolExecutor
import subprocess
import socket, struct
import ipaddress
import json
import requests

headers = {
    "Content-Type": "application/json",
    "Opentrons-Version": "3"
}

TIME_OUT = 2


def get_default_gateway():
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


def check_ip(gateway, subnet_mask='24'):
    network = ipaddress.IPv4Network(f"{gateway}/{subnet_mask}", strict=False)
    print(f"\n[信息] 正在扫描网络: {network} (共 {network.num_addresses - 2} 个IP)")

    def ping_ip(ip):
        if platform.system() == "Windows":
            response = os.system(f"ping -n 1 -w 1000 {ip} > nul")  # Windows
        else:
            response = os.system(f"ping -c 1 -W 1 {ip} > /dev/null 2>&1")  # Linux/Mac
        if response == 0:
            return ip
        else:
            return None

    with ThreadPoolExecutor(max_workers=100) as executor:  # 调整max_workers控制并发数
        results = executor.map(ping_ip, [str(host) for host in network.hosts()])
        reachable_ips = [ip for ip in results if ip is not None]
    return reachable_ips


def scan_ip():
    gateway = get_default_gateway()
    ip_list = check_ip(gateway)
    print(f"发现{len(ip_list)} 个在线IP")
    return ip_list


"""
scan flex
"""


def check_flex(ip):
    try:
        response = requests.get(f"http://{ip}:31950/health", headers=headers, timeout=TIME_OUT)
        if response.status_code == 200:
            return {ip: json.loads(response.text)}
    except Exception as e:
        return None


def scan_flex():
    ip_list = scan_ip()
    with ThreadPoolExecutor(max_workers=100) as executor:  # 调整max_workers控制并发数
        results = executor.map(check_flex, ip_list)
        reachable_ips = {}
        [reachable_ips.update(ip) for ip in results if ip is not None]
    print(f"发现{len(reachable_ips)}个在线Flex")
    return reachable_ips

if __name__ == '__main__':
    flex_group = scan_flex()
    for key, value in flex_group.items():
        print(f'ip: {key}, name: {value["name"]}, app_version: {value["api_version"]}, fw_version: {value["fw_version"]}')
