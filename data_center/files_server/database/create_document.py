import pandas as pd
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from typing import List, Dict, Any
import logging

logger = logging.getLogger('database.document')


class ExcelToMongoDB:
    def __init__(self, mongodb_uri: str, db_name: str, collection_name: str):
        """
        初始化MongoDB连接

        :param mongodb_uri: MongoDB连接字符串
        :param db_name: 数据库名称
        :param collection_name: 集合名称
        """
        self.mongodb_uri = mongodb_uri
        self.db_name = db_name
        self.collection_name = collection_name
        self.client = None
        self.db = None
        self.collection = None

    def connect_to_mongodb(self) -> bool:
        """连接MongoDB服务器"""
        try:
            self.client = MongoClient(self.mongodb_uri, serverSelectionTimeoutMS=5000)
            # 测试连接
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            logger.info(f"成功连接到MongoDB: {self.mongodb_uri}")
            return True
        except ConnectionFailure as e:
            logger.error(f"连接MongoDB失败: {e}")
            return False

    def create_collection(self) -> bool:
        """创建集合（如果不存在）"""
        try:
            if self.collection_name not in self.db.list_collection_names():
                self.db.create_collection(self.collection_name)
                logger.info(f"创建集合: {self.collection_name}")
            return True
        except OperationFailure as e:
            logger.error(f"创建集合失败: {e}")
            return False

    def read_excel(self, file_path: str) -> List[Dict[str, Any]]:
        """
        读取Excel文件并转换为字典列表

        :param file_path: Excel文件路径
        :return: 数据字典列表
        """
        try:
            # 读取Excel文件
            df = pd.read_excel(file_path)

            # 处理空值
            df = df.where(pd.notnull(df), None)

            # 转换为字典列表
            data = df.to_dict('records')

            logger.info(f"从 {file_path} 读取到 {len(data)} 条记录")
            return data
        except Exception as e:
            logger.error(f"读取Excel文件失败: {e}")
            return []

    def insert_data(self, data: List[Dict[str, Any]]) -> int:
        """
        插入数据到MongoDB

        :param data: 要插入的数据
        :return: 成功插入的数量
        """
        if not data:
            return 0

        try:
            result = self.collection.insert_many(data)
            logger.info(f"成功插入 {len(result.inserted_ids)} 条记录")
            return len(result.inserted_ids)
        except Exception as e:
            logger.error(f"插入数据失败: {e}")
            return 0

    def close_connection(self):
        """关闭MongoDB连接"""
        if self.client:
            self.client.close()
            logger.info("MongoDB连接已关闭")

