from socket import *
import time
# 1. 创建udp套接字
udp_socket = socket(AF_INET, SOCK_DGRAM)

# 2. 准备接收方的地址
dest_addr = ('192.168.8.64', 64000)

# 3. 从键盘获取数据
send_data = "M0\r\n"

# 4. 发送数据到指定的电脑上
for i in range(100):
    udp_socket.sendto(send_data.encode('utf-8'), dest_addr)

    # 5. 等待接收对方发送的数据
    recv_data = udp_socket.recvfrom(1024)  # 1024表示本次接收的最大字节数

    # 6. 显示对方发送的数据
    # 接收到的数据recv_data是一个元组
    # 第1个元素是对方发送的数据
    # 第2个元素是对方的ip和端口
    print(recv_data[0].decode('gbk'))
    print(recv_data[1])
    time.sleep(1)

# 7. 关闭套接字
udp_socket.close()