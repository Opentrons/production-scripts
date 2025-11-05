import pymongo
from pymongo import MongoClient
from typing import Dict, List, Any, Optional
import logging
import pandas as pd  # 可选，用于转换为DataFrame
from files_server.utils.utils import require_config
from files_server.logs import get_logger
DB_URL = require_config()["db_url"]

logger = get_logger("database.data")


class MongoDBReader:
    def __init__(self,
                 uri: str = DB_URL,
                 db_name: str = "test_db",
                 collection_name: str = "test_collection"):
        """
        初始化MongoDB读取器

        :param uri: MongoDB连接URI
        :param db_name: 数据库名称
        :param collection_name: 集合名称
        """
        self.uri = uri
        self.db_name = db_name
        self.collection_name = collection_name
        self.client = None
        self.db = None
        self.collection = None
        self.__auto_upload = True

    def connect(self) -> bool:
        """建立MongoDB连接"""
        try:
            self.client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=5000,
                socketTimeoutMS=30000,
                connectTimeoutMS=30000
            )
            # 测试连接
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            logger.info(f"成功连接到MongoDB: {self.db_name}.{self.collection_name}")
            return True
        except pymongo.errors.ServerSelectionTimeoutError as e:
            logger.error(f"连接MongoDB超时: {e}")
        except pymongo.errors.ConnectionFailure as e:
            logger.error(f"连接MongoDB失败: {e}")
        except Exception as e:
            logger.error(f"未知连接错误: {e}")
        return False

    @property
    def auto_upload(self):
        self.db_name = "Params"
        self.collection_name = "Index"
        self.connect()
        result = self.find_all()[0]
        current_status = result["auto_upload_data"]
        if current_status == "true":
            self.__auto_upload = True
        else:
            self.__auto_upload = False
        return self.__auto_upload

    @auto_upload.setter
    def auto_upload(self, value: bool):
        if isinstance(value, bool):
            self.__auto_upload = value
            self.db_name = "Params"
            self.collection_name = "Index"
            self.connect()
            auto_upload = "true" if self.__auto_upload else "false"
            self.set_database_filed({"index": 1}, {"auto_upload_data": auto_upload})
        else:
            raise TypeError("value should be a bool value")


    def find_all(self,
                 limit: int = 10,
                 projection: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        查询所有文档

        :param limit: 返回结果限制数量
        :param projection: 指定返回字段 {'field1':1, 'field2':0}
        :return: 文档列表
        """
        try:
            cursor = self.collection.find({}, projection).limit(limit)
            return list(cursor)
        except Exception as e:
            logger.error(f"查询失败: {e}")
            return []

    def find_by_condition(self,
                          condition: Dict[str, Any],
                          sort_field: Optional[str] = None,
                          ascending: bool = True) -> List[Dict[str, Any]]:
        """
        条件查询

        :param condition: 查询条件 {'field': value}
        :param sort_field: 排序字段
        :param ascending: 是否升序
        :return: 文档列表
        """
        try:
            sort = [(sort_field, pymongo.ASCENDING if ascending else pymongo.DESCENDING)] if sort_field else None
            cursor = self.collection.find(condition)
            if sort:
                cursor = cursor.sort(sort)
            return list(cursor)
        except Exception as e:
            logger.error(f"条件查询失败: {e}")
            return []

    def aggregate(self, pipeline: List[Dict]) -> List[Dict[str, Any]]:
        """
        聚合查询

        :param pipeline: 聚合管道
        :return: 聚合结果
        """
        try:
            return list(self.collection.aggregate(pipeline))
        except Exception as e:
            logger.error(f"聚合查询失败: {e}")
            return []

    def count_documents(self, condition: Optional[Dict] = None) -> int:
        """
        统计文档数量
        :param condition: 查询条件
        :return: 文档数量
        """
        try:
            return self.collection.count_documents(condition or {})
        except Exception as e:
            logger.error(f"统计文档失败: {e}")
            return 0

    def delete_document(self, request_key: dict) -> int:

        result = self.collection.delete_one(request_key)
        return result.deleted_count

    def set_database_filed(self, search_value: dict, update_value: dict[str, Any]):
        """
        update filed in a collection
        :param search_value:
        :param update_value:
        :return:
        """
        try:
            # 假设 self.collection 是你的 MongoDB 集合对象
            result = self.collection.update_one(
                search_value,  # 查询条件：搜索 SN 字段
                {"$set": update_value}  # 更新操作：设置指定字段的值
            )

            if result.matched_count > 0:
                return result
            else:
                logger.info(f"未找到文档")
                return None

        except Exception as e:
            logger.info(f"更新失败: {e}")
            return None

    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()
            logger.info("MongoDB连接已关闭")

    @staticmethod
    def to_dataframe(data: List[Dict]) -> pd.DataFrame:
        """将查询结果转为Pandas DataFrame"""
        return pd.DataFrame(data)


# 使用示例
if __name__ == "__main__":
    # 1. 初始化读取器
    reader = MongoDBReader()
    print(reader.auto_upload)



