import os
from server.main import start_sever as start_backend_serve
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread


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

    th1 = Thread(target=start_front_server)
    th1.start()
    th2 = Thread(target=start_backend_serve)
    th2.start()


if __name__ == '__main__':
    start_server()
