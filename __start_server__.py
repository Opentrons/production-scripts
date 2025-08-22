import os
import time

# from server.main import start_sever as start_backend_serve
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler

from threading import Thread
import webbrowser


def start_front_server(folder):
    if folder is None:
        def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler):
            server_address = ('', 8000)  # 服务器监听的IP和端口
            httpd = server_class(server_address, handler_class)
            print('HTTP server running on http://127.0.0.1:8000')
            httpd.serve_forever()

        run()
    else:
        os.system(f'python -m http.server --directory {folder}')


# def start_server(folder):
#     """
#     dist
#     """
#     print("Open web page on http://127.0.0.1:8000 \n")
#     time.sleep(0.5)
#     th1 = Thread(target=start_backend_serve)
#     th1.start()
#     time.sleep(0.5)
#     webbrowser.open("http://127.0.0.1:8000")
#     start_front_server(folder)
#     th1.join()
#     input("Server Closed !")


if __name__ == '__main__':
    start_server('./dist')
