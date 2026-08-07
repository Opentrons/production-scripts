import subprocess
import json

def load_config():
    with open('skill_config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def test_curl_with_proxy(proxy):
    url = "https://www.google.com"
    cmd = [
        'curl',
        '-x', proxy,
        '-I',
        '--connect-timeout', '10',
        url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        print("=== curl 测试结果 ===")
        print(f"命令: {' '.join(cmd)}")
        print(f"\n标准输出:\n{result.stdout}")
        print(f"错误输出:\n{result.stderr}")
        print(f"返回码: {result.returncode}")
        
        if result.returncode == 0:
            print("\n✅ curl 访问成功！")
        else:
            print("\n❌ curl 访问失败")
    except subprocess.TimeoutExpired:
        print("❌ 请求超时")
    except Exception as e:
        print(f"❌ 发生错误: {e}")

def test_direct_curl():
    url = "https://www.google.com"
    cmd = [
        'curl',
        '-I',
        '--connect-timeout', '10',
        url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        print("\n=== 不使用代理的 curl 测试 ===")
        print(f"命令: {' '.join(cmd)}")
        print(f"\n标准输出:\n{result.stdout}")
        print(f"错误输出:\n{result.stderr}")
        print(f"返回码: {result.returncode}")
        
        if result.returncode == 0:
            print("\n✅ 直接访问成功！")
        else:
            print("\n❌ 直接访问失败")
    except subprocess.TimeoutExpired:
        print("❌ 请求超时")
    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    config = load_config()
    proxy = config.get('proxy', '')
    
    print(f"加载的代理配置: {proxy}")
    print(f"代理节点: {config.get('proxy_node', '未知')}")
    
    test_curl_with_proxy(proxy)
