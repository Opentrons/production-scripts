import bluetooth

# 创建一个蓝牙服务端套接字
server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)

# 绑定本地的一个端口
port = bluetooth.PORT_ANY
server_sock.bind(port)

# 开始监听，最多允许1个连接
server_sock.listen(1)

print("Waiting for connection...")

# 接受客户端的连接请求
client_sock, address = server_sock.accept()

print("Connected to ", address)

# 接收数据
data = client_sock.recv(1024)
print("Received data:", data)

# 关闭套接字
client_sock.close()
server_sock.close()