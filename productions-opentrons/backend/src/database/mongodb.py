from pymongo import MongoClient
import logging
from settings import MONGO_HOST, MONGO_URI


logger = logging.getLogger(__name__)
MONGO_TIMEOUT_MS = 3000


class MongoDB:
    def __init__(self, host: str = None, port: int = 27017, uri: str = None):
        self.host = host or MONGO_HOST
        self.port = port
        self.uri = uri or MONGO_URI
        self.client = None
        self.db = None

    def connect(self):
        try:
            timeout_options = {
                "serverSelectionTimeoutMS": MONGO_TIMEOUT_MS,
                "connectTimeoutMS": MONGO_TIMEOUT_MS,
                "socketTimeoutMS": MONGO_TIMEOUT_MS,
            }
            if self.uri:
                self.client = MongoClient(self.uri, **timeout_options)
            else:
                self.client = MongoClient(self.host, self.port, **timeout_options)
            self.client.admin.command('ping')
            if self.uri:
                logger.info("MongoDB 连接成功 - URI mode")
            else:
                logger.info(f"MongoDB 连接成功 - Host: {self.host}, Port: {self.port}")
            return True
        except Exception as e:
            if self.client:
                self.client.close()
            self.client = None
            self.db = None
            target = "URI mode" if self.uri else f"Host: {self.host}, Port: {self.port}"
            logger.error(f"MongoDB 连接失败 - {target}, Error: {e}")
            return False

    def get_database(self, db_name: str = None):
        if db_name is None:
            return self.client
        return self.client[db_name]

    def close(self):
        if self.client:
            self.client.close()
            logger.info("MongoDB 连接已关闭")


mongodb = MongoDB()
