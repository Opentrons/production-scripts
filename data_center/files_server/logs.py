import logging
import os

# from files_server.server import _is_simulate
_is_simulate = True

# 定义日志目录（绝对路径）
LOG_DIR = "/opt/data-center-files_server/logs"
LOG_FILE = os.path.join(LOG_DIR, "data-center.log")


class Logger:
    def __init__(self):
        pass

    def print_info(self, info):
        print("INFO INFO INFO INFO INFO INFO INFO INFO INFO")
        print(info)

    def print_error(self, error):
        print("ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR")
        print(error)


# 创建logger
if not _is_simulate:
    # 基本配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=LOG_FILE,
        filemode='a'
    )
    logger = logging.getLogger(__name__)
else:
    logger = Logger()
