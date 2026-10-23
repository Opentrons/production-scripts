from pymongo import MongoClient
import logging
import time
from core.config import (
    MONGO_CONNECT_ATTEMPTS,
    MONGO_CONNECT_RETRY_DELAY_MS,
    MONGO_CONNECT_TIMEOUT_MS,
    MONGO_HOST,
    MONGO_SERVER_SELECTION_TIMEOUT_MS,
    MONGO_SOCKET_TIMEOUT_MS,
    MONGO_URI,
)


logger = logging.getLogger(__name__)


class MongoDB:
    def __init__(self, host: str = None, port: int = 27017, uri: str = None):
        self.host = host or MONGO_HOST
        self.port = port
        self.uri = uri or MONGO_URI
        self.client = None
        self.db = None

    def connect(self):
        timeout_options = {
            "serverSelectionTimeoutMS": MONGO_SERVER_SELECTION_TIMEOUT_MS,
            "connectTimeoutMS": MONGO_CONNECT_TIMEOUT_MS,
            "socketTimeoutMS": MONGO_SOCKET_TIMEOUT_MS,
        }
        target = "URI mode" if self.uri else f"Host: {self.host}, Port: {self.port}"
        last_error: Exception | None = None
        for attempt in range(1, MONGO_CONNECT_ATTEMPTS + 1):
            try:
                if self.uri:
                    self.client = MongoClient(self.uri, **timeout_options)
                else:
                    self.client = MongoClient(self.host, self.port, **timeout_options)
                self.client.admin.command("ping")
                logger.info(
                    "MongoDB 连接成功 - %s (attempt %s/%s)",
                    target,
                    attempt,
                    MONGO_CONNECT_ATTEMPTS,
                )
                return True
            except Exception as exc:
                last_error = exc
                if self.client:
                    self.client.close()
                self.client = None
                self.db = None
                if attempt < MONGO_CONNECT_ATTEMPTS:
                    logger.warning(
                        "MongoDB 连接失败，准备重试 - %s (attempt %s/%s): %s",
                        target,
                        attempt,
                        MONGO_CONNECT_ATTEMPTS,
                        exc,
                    )
                    if MONGO_CONNECT_RETRY_DELAY_MS:
                        time.sleep(MONGO_CONNECT_RETRY_DELAY_MS / 1000)
        logger.error(
            "MongoDB 连接失败 - %s after %s attempt(s), Error: %s",
            target,
            MONGO_CONNECT_ATTEMPTS,
            last_error,
        )
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
