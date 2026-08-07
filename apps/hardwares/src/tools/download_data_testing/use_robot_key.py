import base64

with open("./robot_key", "rb") as f:
    data_base64 = base64.b64encode(f.read()).decode('utf-8')

print(data_base64)  # 复制输出的字符串