import os
import time

from server.main import start_sever as start_backend_serve
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import webbrowser


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        message = "Opened"
        self.wfile.write(bytes(message, 'utf8'))


def start_front_server():
    # _ip = "127.0.0.1"
    # port = 8000
    # with HTTPServer((_ip, port), Handler) as httpd:
    #     httpd.serve_forever()
    os.system('python -m http.server --directory ./dist')


def start_server():
    print("Open web page on http://127.0.0.1:8000 \n")
    time.sleep(0.5)
    th1 = Thread(target=start_front_server)
    th1.start()
    time.sleep(0.5)
    webbrowser.open("http://127.0.0.1:8000")
    start_backend_serve()
    th1.join()
    input("Server Closed !")


if __name__ == '__main__':
    start_server()
