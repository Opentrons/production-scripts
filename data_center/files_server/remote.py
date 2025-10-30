
from download_report_handler.download_files import LinuxFileManager

def build_handler(host, username):
    handler = LinuxFileManager(host, username, logger)
    return handler













