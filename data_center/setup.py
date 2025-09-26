Packages = {
    "fastapi": 
        {"_module": "fastapi", "version": ""},
    "uvicorn": 
        {"_module": "uvicorn", "version": ""},
    "paramiko": 
        {"_module": "paramiko", "version": ""},
    "google-auth": 
        {"_module": "google-auth", "version": ""},
    "google-auth-oauthlib": 
        {"_module": "google-auth-oauthlib", "version": ""},
    "google-auth-httplib2": 
        {"_module": "google-auth-httplib2", "version": ""},
    "google-api-python-client": 
        {"_module": "google-api-python-client", "version": ""},
    "pandas": 
        {"_module": "pandas", "version": ""},
    "python-jose[cryptography]": 
        {"_module": "python-jose[cryptography]", "version": ""},
    "pymongo": 
        {"_module": "pymongo", "version": ""},
    "python-multipart": 
        {"_module": "python-multipart", "version": ""},
    "requests": 
        {"_module": "requests", "version": ""},
}

MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

def pip_dependences():
    for _, value in Packages.items():
        module_name = value["_module"]
        version = value["version"]
        try:
            # 使用 __import__ 函数
            module = __import__(module_name)
            version = getattr(module, '__version__', '未知版本')
            print(f"{module_name} 已安装，版本: {version}")    
        except ImportError:
            print(f"✗ {module_name} 未安装，正在安装...")
            try:
                import subprocess
                import sys
                # 使用pip安装
                if version:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", '-i', f"{MIRROR}", f"{module_name}=={version}"])
                else:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", '-i', f"{MIRROR}", module_name])
                print(f"✓ {module_name} 安装成功")
            except subprocess.CalledProcessError:
                print(f"✗ {module_name} 安装失败")

pip_dependences()
