from server.start_server import start_server
import subprocess


def start_front_server():
    cmd = 'python -m http.server'
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    while True:
        line = process.stdout.readline()
        if not line:
            break  # 如果没有读取到数据，表示子进程已经结束，退出循环
        else:
            print(line, end='')  # 实时打印输出
    process.wait()


if __name__ == '__main__':
    # start_front_server()
    start_server()



