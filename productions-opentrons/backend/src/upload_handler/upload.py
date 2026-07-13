from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from pprint import pformat
from typing import TYPE_CHECKING
from typing import Callable
from typing import Sequence

from settings import ENVIRONMENT, EXPIRE_DAYS, get_logger

from upload_handler.models import FileDescription, TestTypes, UploadApiResponse, build_api_response
from upload_handler.product_catalog import (
    get_upload_collection_name_from_config_key,
    get_upload_config_key,
    get_combined_test_fields,
    get_test_field_from_config_key,
    get_upload_database_config,
    get_upload_database_peer_fields,
    get_upload_handler_config,
    get_upload_workflow_from_config_key,
    is_combined_upload_config,
    is_upload_result_successful,
)
from api.services import upload_settings as upload_settings_service

if TYPE_CHECKING:
    from database.mongodb import MongoDB

logger = get_logger(__name__)
SLACK_UPLOAD_CHANNEL = "production-data-center"
UploadProgressCallback = Callable[[str, dict], None]

class UploadData:
    def __init__(self, mongo: MongoDB = None) -> None:
        from database.mongodb import MongoDB
        from upload_handler.drivers.csv_driver import CsvDriver
        from upload_handler.repositories.config_repository import ConfigRepository
        from upload_handler.repositories.upload_session_repository import UploadSessionRepository
        from upload_handler.repositories.upload_repository import default_upload_repositories

        # 初始化日志系统
        from settings import setup_logging
        setup_logging()
        """
        Test_environment:测试环境切换 debug 调试使用 Production 生产环境

        Args:
            Test_environment (str, optional): _description_. Defaults to "debug".
        """
        self.gdrive = None
        self.csv_driver = CsvDriver()
        self.mongo = mongo
        self.upload_session_repo = None
        self.google_init_error = None
        self.config_repo = ConfigRepository.from_environment(ENVIRONMENT)
        self.upload_repositories = default_upload_repositories(self)
        self.nowmonth = self.get_current_month()
        if self.mongo is None:
            logger.warning("MongoDB not connected, try to connect...")
            self.mongo = MongoDB()
            ret = self.mongo.connect()
            if not ret:
                logger.error("MongoDB connect fail")
                raise Exception("MongoDB connect fail")
        self.upload_session_repo = UploadSessionRepository(self.mongo)

    def init_upload_handler(self):
        from upload_handler.drivers.google_drive import GoogleDriveDriver

        try:
            self.gdrive = GoogleDriveDriver()
            self.google_init_error = None
        except Exception as e:
            self.google_init_error = str(e)
            logger.error("Init Google Drive driver fail")
            logger.error(e)
            print(f"Init Google Drive driver fail, {e}")

    def get_current_month(self):
        """获取服务器当前月份"""
        now = datetime.now()  # 获取当前服务器本地时间
        return now.month

    @staticmethod
    def quote_sheet_name(sheet_name: str) -> str:
        escaped_sheet_name = str(sheet_name).replace("'", "''")
        return f"'{escaped_sheet_name}'"

    @staticmethod
    def normalize_sheet_name(sheet_name: str) -> str:
        return " ".join(str(sheet_name).split()).lower()

    def resolve_sheet_name(self, spreadsheet_id: str, sheet_name: str):
        sheet_gid_map = self.gdrive.get_sheet_gid_map(spreadsheet_id) or {}
        if sheet_name in sheet_gid_map:
            return sheet_name, sheet_gid_map

        normalized_sheet_name = self.normalize_sheet_name(sheet_name)
        for existing_sheet_name in sheet_gid_map:
            if self.normalize_sheet_name(existing_sheet_name) == normalized_sheet_name:
                return existing_sheet_name, sheet_gid_map

        return sheet_name, sheet_gid_map
    
    def is_upload_successful(self, result: dict, file_desc: dict) -> bool:
        if not result:
            return False
        if result.get("database_saved") is False:
            return False

        return is_upload_result_successful(self.resolve_upload_config_key(file_desc, result), result)

    def build_upload_error(self, result: dict | None, file_desc: dict) -> str:
        if not result:
            return "Update data result is None"
        if result.get("error"):
            return result.get("error")
        if result.get("database_saved") is False:
            return result.get("database_error") or "Database upload failed"

        config_key = self.resolve_upload_config_key(file_desc, result)
        test_display_name = get_upload_handler_config(config_key).test_display_name
        return f"{test_display_name} upload failed"

    @staticmethod
    def resolve_upload_config_key(file_desc: dict, result: dict | None = None) -> str:
        config_key = ""
        if result:
            config_key = str(result.get("upload_config_key") or "")
        config_key = config_key or str(file_desc.get("upload_config_key") or "")
        if config_key:
            return config_key
        return get_upload_config_key(file_desc.get("model"), file_desc.get("test_type"))

    def build_upload_response(self, result: dict | None, file_desc: dict, upload_repository, test_type) -> UploadApiResponse:
        if not result:
            return build_api_response(
                finished=False,
                error=self.build_upload_error(result, file_desc),
                sn=file_desc.get("sn", ""),
            )

        message = upload_repository.build_message(result, file_desc)
        finished = self.is_upload_successful(result, file_desc)
        return build_api_response(
            finished=finished,
            error=None if finished else self.build_upload_error(result, file_desc),
            production_name=message.get("production_name", ""),
            test_type=message.get("test_type", ""),
            test_result=message.get("test_result", ""),
            sn=result.get("sn") or message.get("sn", ""),
            csv_link=result.get("csv_link") or message.get("csv_link", ""),
            unit_tracker=result.get("unit_tracker") or message.get("unit_tracker", ""),
            unit_tracker_status=result.get("unit_tracker_status", ""),
            missing_tests=result.get("missing_tests"),
            raw_data=result.get("raw_data", ""),
            raw_data_name=result.get("raw_data_name", ""),
        )

    def build_file_description(
        self,
        file_path: str,
        zip_file=None,
        meta: dict | None = None,
    ) -> tuple[FileDescription | None, str | None]:
        file_desc = FileDescription.build(file_path, meta=meta)
        if not file_desc:
            return None, "Failed to build file description"
        if not file_desc.is_parse_successful:
            return file_desc, f"Failed to get file description: {file_desc.error}"

        file_desc.attach_upload_context(zip_file=zip_file)

        require_finished = upload_settings_service.should_require_finished(
            file_desc.get("model"),
            file_desc.get("test_type"),
        )
        file_desc["require_finished"] = require_finished
        if not file_desc.finished and require_finished:
            return file_desc, f"File is not finished: {file_desc.get('file_path')}"
        if not file_desc.finished and not require_finished:
            file_desc["finished_bypassed"] = True

        return file_desc, None

    def log_file_description(self, file_desc: FileDescription) -> None:
        logger.info("==== FILE DESCRIPTION START====")
        for key, value in file_desc.items():
            logger.info(f"{key} : {value}")
        logger.info("==== FILE DESCRIPTION END====")

    def update_data_to_google_drive(
        self,
        file_path: str,
        zip_file=None,
        progress_callback: UploadProgressCallback | None = None,
        meta: dict | None = None,
    ) -> UploadApiResponse:
        """
        上传测试数据到 Google Drive。

        Args:
            file_path: 测试原始数据的服务器路径地址。
            zip_file: 需要上传的测试原文件压缩包。

        Returns:
            UploadApiResponse: 统一 API 响应，成功时包含 finished/test_type/test_result/sn/csv_link/unit_tracker。
        """
        print(f"Start to upload {file_path}")
        logger.info("==== Upload data to google drive start ====")
        try:
            if self.gdrive is None:
                error = f"Google driver not ready: {self.google_init_error}" if self.google_init_error else "Google driver not ready"
                logger.error(error)
                return build_api_response(finished=False, error=error)
            logger.info("Google driver is ready!")

            file_desc, error = self.build_file_description(file_path, zip_file, meta=meta)
            if error:
                if error.startswith("File is not finished"):
                    logger.warning(error)
                else:
                    logger.error(error)
                if file_desc and progress_callback:
                    progress_callback("file_desc", file_desc.to_dict())
                return build_api_response(finished=False, error=error)

            logger.info("成功解析文件描述.")
            self.log_file_description(file_desc)
            if progress_callback:
                progress_callback("file_desc", file_desc.to_dict())
            test_type = file_desc.test_type
            logger.info(f"start to update data with {getattr(test_type, 'value', test_type)}")

            from upload_handler.repositories.upload_repository import resolve_upload_repository

            upload_repository = resolve_upload_repository(self.upload_repositories, file_desc, test_type)
            if upload_repository is None:
                logger.error(f"不支持的 test_type 或 model: {test_type}, model: {file_desc.get('model')}")
                return build_api_response(
                    finished=False,
                    error=f"Unsupported test_type or model: {test_type}, model: {file_desc.get('model')}",
                )

            logger.info(f"Handling upload with {upload_repository.__class__.__name__}")
            result = upload_repository.upload(file_desc)
            if progress_callback:
                progress_callback("upload_result", result or {})
            return self.build_upload_response(result, file_desc, upload_repository, test_type)
        except Exception as errval:
            logger.exception("Upload data to google drive failed")
            return build_api_response(finished=False, error=f"Exception occurred: {str(errval)}")
        finally:
            logger.info("==== Upload data to google drive end ====")

    def query_csv_link(
        self,
        db_name,
        collection_name,
        device_sn: str,
        my_test_name: str,
        search_test_name: str,
        model: str = "",
    ):
        """
        查询最新测试数据的 CSV 链接
        Args:
            db_name (str): 数据库名称
            collection_name (str): 集合名称
            device_sn (str): 移液器的序列号
            my_test_name (str): 当前的测试名称
            search_test_name (str): 搜索的测试名称，确认是否测试完成
            model (str): 产品型号，用于解析跨测试 workflow
        Returns:
            str: 最新测试数据的 CSV 链接
        """
        now = datetime.now()
        db = self.mongo.get_database(db_name)
        collection = db[collection_name]
        csv_link = None

        if self.upload_session_repo is not None:
            csv_link = self.upload_session_repo.find_reusable_sheet(
                db_name=db_name,
                collection_name=collection_name,
                device_sn=device_sn,
                current_test=my_test_name,
                required_test=search_test_name,
                expire_days=EXPIRE_DAYS,
                model=model,
            )
            if csv_link:
                return csv_link

        query = {"sn": device_sn}
        all_data = list(collection.find(query))

        if not all_data:
            return csv_link

        filtered_by_test_name = [
            d for d in all_data
            if d.get(search_test_name) is True
        ]

        if not filtered_by_test_name:
            return csv_link

        expire_time = now - timedelta(days=EXPIRE_DAYS)

        filtered_by_expire = []
        for d in filtered_by_test_name:
            update_time_val = d.get("update_time")
            if update_time_val is None:
                continue
            if isinstance(update_time_val, str):
                try:
                    update_time_dt = datetime.fromisoformat(update_time_val.replace("Z", "+00:00"))
                except:
                    continue
            else:
                update_time_dt = update_time_val
            if getattr(update_time_dt, "tzinfo", None) is not None:
                update_time_dt = update_time_dt.replace(tzinfo=None)
            if update_time_dt >= expire_time:
                filtered_by_expire.append(d)

        if not filtered_by_expire:
            return csv_link

        filtered_by_field = [
            d for d in filtered_by_expire
            if d.get(my_test_name) is None or d.get(my_test_name) != True
        ]

        if not filtered_by_field:
            return csv_link

        sorted_data = sorted(filtered_by_field, key=lambda x: x.get("update_time") or "", reverse=True)
        latest_update_time = sorted_data[0].get("update_time") or ""

        records_with_latest_date = [d for d in sorted_data if (d.get("update_time") or "") == latest_update_time]

        for record in records_with_latest_date[1:]:
            collection.delete_one({"_id": record["_id"]})

        csv_link = records_with_latest_date[0].get("csv_link", None)
        return csv_link

    def build_workflow_record_query(self, file_desc: dict, config_key: str) -> dict:
        return {
            "sn": file_desc.get("sn"),
            "model": file_desc.get("model"),
            "workflow": get_upload_workflow_from_config_key(config_key),
        }

    def is_same_test_reupload_before_combine_complete(
        self,
        db_name: str,
        collection_name: str,
        file_desc: dict,
        config_key: str,
    ) -> bool:
        if not is_combined_upload_config(config_key):
            return False

        record = self.get_latest_upload_record(db_name, collection_name, file_desc, config_key)
        if not record:
            return False

        current_field = get_test_field_from_config_key(config_key)
        if record.get(current_field) is not True:
            return False

        required_fields = get_combined_test_fields(config_key)
        missing_tests = [test_field for test_field in required_fields if record.get(test_field) is not True]
        return bool(missing_tests)

    def collect_stale_incomplete_drive_links(
        self,
        db_name: str,
        collection_name: str,
        file_desc: dict,
        config_key: str,
    ) -> list[str]:
        query = self.build_workflow_record_query(file_desc, config_key)
        collection = self.mongo.get_database(db_name)[collection_name]
        stale_links: list[str] = []
        for record in collection.find(query):
            for key in ("csv_link", "raw_data"):
                drive_link = record.get(key)
                if not drive_link or drive_link in {"N/A", "NA", "http:xx"}:
                    continue
                if drive_link not in stale_links:
                    stale_links.append(drive_link)
        return stale_links

    def delete_stale_incomplete_drive_files(
        self,
        stale_links: list[str],
        *,
        permanent: bool = False,
    ) -> dict:
        if not stale_links:
            return {"deleted": [], "failed": [], "skipped": [], "driver_unavailable": False}

        if self.gdrive is None:
            logger.warning(
                "Skip stale Drive cleanup because Google driver is not ready: links=%s",
                stale_links,
            )
            return {
                "deleted": [],
                "failed": [{"url": link, "file_id": ""} for link in stale_links],
                "skipped": [],
                "driver_unavailable": True,
                "permanent": permanent,
            }

        result = self.gdrive.delete_drive_resources_by_urls(stale_links, permanent=permanent)
        result["driver_unavailable"] = False
        return result

    def cleanup_incomplete_combined_workflow(
        self,
        db_name: str,
        collection_name: str,
        file_desc: dict,
        config_key: str,
    ) -> dict:
        workflow = get_upload_workflow_from_config_key(config_key)
        query = self.build_workflow_record_query(file_desc, config_key)
        stale_drive_links = self.collect_stale_incomplete_drive_links(
            db_name,
            collection_name,
            file_desc,
            config_key,
        )
        drive_cleanup = self.delete_stale_incomplete_drive_files(stale_drive_links)

        collection = self.mongo.get_database(db_name)[collection_name]
        delete_result = collection.delete_many(query)
        deleted_records = int(delete_result.deleted_count)

        if self.upload_session_repo is not None:
            self.upload_session_repo.delete_workflow_session(
                db_name,
                file_desc.get("sn"),
                file_desc.get("model"),
                workflow,
            )

        return {
            "cleaned": deleted_records > 0,
            "deleted_records": deleted_records,
            "stale_drive_links": stale_drive_links,
            "stale_csv_links": [
                link for link in stale_drive_links if "spreadsheets" in link or "/d/" in link
            ],
            "drive_cleanup": drive_cleanup,
            "workflow": workflow,
        }

    def cleanup_incomplete_combined_workflow_if_needed(
        self,
        db_name: str,
        collection_name: str,
        file_desc: dict,
    ) -> dict:
        config_key = self.resolve_upload_config_key(file_desc)
        if not self.is_same_test_reupload_before_combine_complete(
            db_name,
            collection_name,
            file_desc,
            config_key,
        ):
            return {
                "cleaned": False,
                "deleted_records": 0,
                "stale_csv_links": [],
                "workflow": get_upload_workflow_from_config_key(config_key),
            }

        logger.warning(
            "Same test re-upload detected before combine workflow is complete; "
            "resetting workflow and stale sheets: sn=%s model=%s config_key=%s",
            file_desc.get("sn"),
            file_desc.get("model"),
            config_key,
        )
        return self.cleanup_incomplete_combined_workflow(
            db_name,
            collection_name,
            file_desc,
            config_key,
        )

    def query_reusable_csv_link(self, db_name: str, collection_name: str, file_desc: dict) -> str | None:
        config_key = self.resolve_upload_config_key(file_desc)
        peer_fields = get_upload_database_peer_fields(config_key)
        if not peer_fields:
            return None

        device_sn = file_desc.get("sn")
        model = file_desc.get("model")
        current_field = get_test_field_from_config_key(config_key)

        if self.upload_session_repo is not None:
            csv_link = self.upload_session_repo.find_reusable_sheet_by_config(
                db_name=db_name,
                device_sn=device_sn,
                model=model,
                config_key=config_key,
                expire_days=EXPIRE_DAYS,
            )
            if csv_link:
                return csv_link

        expire_time = datetime.now() - timedelta(days=EXPIRE_DAYS)
        query = {
            "sn": device_sn,
            "model": model,
            "$and": [
                {
                    "$or": [
                        {current_field: False},
                        {current_field: {"$exists": False}},
                    ],
                },
                {
                    "$or": [
                        {peer_field: True}
                        for peer_field in peer_fields
                    ],
                },
            ],
        }
        collection = self.mongo.get_database(db_name)[collection_name]
        records = collection.find(query).sort("update_time", -1)
        for record in records:
            update_time = record.get("update_time")
            if update_time is None:
                continue
            if isinstance(update_time, str):
                try:
                    update_time = datetime.fromisoformat(update_time.replace("Z", "+00:00"))
                except ValueError:
                    continue
            if getattr(update_time, "tzinfo", None) is not None:
                update_time = update_time.replace(tzinfo=None)
            if update_time < expire_time:
                continue
            csv_link = record.get("csv_link")
            if csv_link:
                return csv_link
        return None

    def build_combined_upload_query(self, file_desc: dict, config_key: str) -> dict:
        current_field = get_test_field_from_config_key(config_key)
        peer_fields = get_upload_database_peer_fields(config_key)
        return {
            "sn": file_desc.get("sn"),
            "model": file_desc.get("model"),
            "$and": [
                {
                    "$or": [
                        {current_field: False},
                        {current_field: {"$exists": False}},
                    ],
                },
                {
                    "$or": [
                        {peer_field: True}
                        for peer_field in peer_fields
                    ],
                },
            ],
        }

    def build_upload_db_result(self, file_desc: dict, result: dict) -> tuple[str, str, dict]:
        config_key = self.resolve_upload_config_key(file_desc, result)
        db_config = get_upload_database_config(config_key)
        collection_name = get_upload_collection_name_from_config_key(file_desc.get("model"), config_key)
        db_result = {
            **result,
            "upload_config_key": config_key,
            "workflow": get_upload_workflow_from_config_key(config_key),
            "source_csv_path": file_desc.get("file_path", ""),
        }

        if is_combined_upload_config(config_key):
            for test_field in get_combined_test_fields(config_key):
                db_result.setdefault(test_field, False)
            db_result[get_test_field_from_config_key(config_key)] = True
        elif db_config.test_field and db_config.test_field not in db_result:
            db_result[db_config.test_field] = True

        return config_key, collection_name, db_result

    def save_upload_result_to_database(self, db_name: str, file_desc: dict, result: dict) -> dict:
        config_key = self.resolve_upload_config_key(file_desc, result)
        if not is_upload_result_successful(config_key, result):
            logger.warning(
                "Skip database write because data upload failed: config_key=%s, sn=%s",
                config_key,
                result.get("sn") or file_desc.get("sn"),
            )
            return {
                "saved": False,
                "workflow_complete": False,
                "missing_tests": [],
                "unit_tracker_uploaded": False,
                "unit_tracker_link": "N/A",
                "error": "数据上传失败，跳过数据库写入",
            }

        config_key, collection_name, db_result = self.build_upload_db_result(file_desc, result)

        database_error = ""
        if is_combined_upload_config(config_key):
            saved, database_error = self.edit_database_with_result(
                db_name,
                collection_name,
                self.build_combined_upload_query(file_desc, config_key),
                db_result,
            )
        else:
            saved, database_error = self.fill_database_with_result(db_name, collection_name, db_result)

        status = self.get_upload_workflow_status(db_name, collection_name, file_desc, config_key) if saved else {}
        return {
            "saved": saved,
            "workflow_complete": status.get("workflow_complete", False),
            "missing_tests": status.get("missing_tests", []),
            "unit_tracker_uploaded": status.get("unit_tracker_uploaded", False),
            "unit_tracker_link": status.get("unit_tracker_link", "N/A"),
            "error": database_error,
        }

    def write_upload_result_to_database(self, db_name: str, file_desc: dict, result: dict) -> bool:
        return bool(self.save_upload_result_to_database(db_name, file_desc, result).get("saved"))

    def get_latest_upload_record(self, db_name: str, collection_name: str, file_desc: dict, config_key: str) -> dict | None:
        collection = self.mongo.get_database(db_name)[collection_name]
        return collection.find_one(
            {
                "sn": file_desc.get("sn"),
                "model": file_desc.get("model"),
                "workflow": get_upload_workflow_from_config_key(config_key),
            },
            sort=[("update_time", -1)],
        )

    def get_upload_workflow_status(self, db_name: str, collection_name: str, file_desc: dict, config_key: str) -> dict:
        if not is_combined_upload_config(config_key):
            record = self.get_latest_upload_record(db_name, collection_name, file_desc, config_key) or {}
            return {
                "workflow_complete": True,
                "missing_tests": [],
                "unit_tracker_uploaded": record.get("unit_tracker_uploaded") is True,
                "unit_tracker_link": record.get("unit_tracker", "N/A"),
            }

        record = self.get_latest_upload_record(db_name, collection_name, file_desc, config_key) or {}
        required_fields = get_combined_test_fields(config_key)
        missing_tests = [test_field for test_field in required_fields if record.get(test_field) is not True]
        workflow_complete = not missing_tests
        return {
            "workflow_complete": workflow_complete,
            "missing_tests": missing_tests,
            "unit_tracker_uploaded": record.get("unit_tracker_uploaded") is True,
            "unit_tracker_link": record.get("unit_tracker", "N/A"),
        }

    def mark_unit_tracker_uploaded(self, db_name: str, file_desc: dict, unit_tracker_link: str) -> bool:
        config_key = self.resolve_upload_config_key(file_desc)
        collection_name = get_upload_collection_name_from_config_key(file_desc.get("model"), config_key)
        record = self.get_latest_upload_record(db_name, collection_name, file_desc, config_key)
        if not record:
            logger.error("Cannot mark unit tracker uploaded because upload record was not found")
            return False

        collection = self.mongo.get_database(db_name)[collection_name]
        collection.update_one(
            {"_id": record["_id"]},
            {
                "$set": {
                    "unit_tracker": unit_tracker_link,
                    "unit_tracker_uploaded": True,
                    "unit_tracker_status": "Uploaded to Unit Tracker",
                    "unit_tracker_updated_at": datetime.now(),
                }
            },
        )
        return True

    def fill_database_with_result(self, db_name, collection_name, result:dict):
        """
        填充数据库中的测试结果
        Args:
            db_name (str): 数据库名称
            collection_name (str): 集合名称
            result (dict): 测试结果字典
        """
        if self.mongo is None:
            error = "MongoDB connection not initialized"
            logger.error(error)
            return False, error
        
        try:
            db_result = {**result, "update_time": datetime.now()}
            db = self.mongo.get_database(db_name)
            collection = db[collection_name]
            insert_result = collection.insert_one(db_result)
            logger.info(f"Inserted result into {db_name}.{collection_name}, id: {insert_result.inserted_id}")
            if self.upload_session_repo is not None:
                self.upload_session_repo.mark_uploaded(db_name, collection_name, db_result)
            return True, ""
        except Exception as e:
            error = f"Failed to insert result into {db_name}.{collection_name}: {e}"
            logger.error(error)
            return False, error

    def edit_database_with_result(self, db_name, collection_name, query:dict, result:dict):
        """
        更新数据库中的测试结果，根据查询条件 query 更新结果 result里面的字段到数据库的update_time最新的一条
        如果没有符合条件的记录，则插入新记录
        Args:
            db_name (str): 数据库名称
            collection_name (str): 集合名称
            query (dict): 查询条件字典
            result (dict): 测试结果字典
        """
        logger.info(f"Editing record in {db_name}.{collection_name} with query: {query}")
        if self.mongo is None:
            error = "MongoDB connection not initialized"
            logger.error(error)
            return False, error
        
        try:
            db = self.mongo.get_database(db_name)
            collection = db[collection_name]
            db_result = {**result, "update_time": datetime.now()}
            
            existing_record = collection.find_one(query, sort=[("update_time", -1)])
            
            if existing_record:
                for key, value in list(db_result.items()):
                    if value is False and existing_record.get(key) is True:
                        db_result[key] = True
                collection.update_one(
                    {"_id": existing_record["_id"]},
                    {"$set": db_result}
                )
                logger.info(f"Updated record in {db_name}.{collection_name}, id: {existing_record['_id']}")
                
                delete_query = {"_id": {"$ne": existing_record["_id"]}}
                for key, value in query.items():
                    delete_query[key] = value
                delete_result = collection.delete_many(delete_query)
                logger.info(f"Deleted {delete_result.deleted_count} other records with same query in {db_name}.{collection_name}")
                if self.upload_session_repo is not None:
                    self.upload_session_repo.mark_uploaded(db_name, collection_name, db_result)
                return True, ""
            else:
                insert_result = collection.insert_one(db_result)
                logger.info(f"Inserted new record into {db_name}.{collection_name}, id: {insert_result.inserted_id}")
                if self.upload_session_repo is not None:
                    self.upload_session_repo.mark_uploaded(db_name, collection_name, db_result)
                return True, ""
        except Exception as e:
            error = f"Failed to edit result in {db_name}.{collection_name}: {e}"
            logger.error(error)
            return False, error

def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload a CSV test result to Google Drive.")
    parser.add_argument("--file", "-f", required=True, help="CSV file path.")
    parser.add_argument("--zip", "-z", dest="zip_file", help="Optional raw data zip path.")
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Parse CSV and print file description only. Skip MongoDB and Google Drive upload.",
    )
    return parser.parse_args(argv)


def resolve_cli_path(path_value: str) -> str:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return str(path.resolve())


def print_upload_result(result: UploadApiResponse | None) -> None:
    print("==== Result ====")
    if result:
        for key, value in result.items():
            print(f"{key}: {value}")
    else:
        print(result)


def is_upload_data_complete(result: UploadApiResponse) -> bool:
    missing_tests = result.get("missing_tests") or []
    return not missing_tests


def build_slack_upload_title(result: UploadApiResponse) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "数据已完整" if is_upload_data_complete(result) else "数据不完整"
    return f"Data Upload -{timestamp}（{status}）!"


def build_slack_test_type(result: UploadApiResponse) -> str:
    return (
        f"{result.get('production_name') or 'Unknown Production'} - "
        f"{result.get('test_type') or 'Unknown Test Type'}"
    )


def infer_slack_failure_stage(error: str) -> str:
    lowered = error.lower()
    if any(keyword in lowered for keyword in ("mongodb", "database", "数据库", "mongo")):
        return "数据库写入"
    if any(
        keyword in lowered
        for keyword in ("google", "drive", "sheet", "spreadsheet", "proxy", "ghelper", "oauth", "token")
    ):
        return "Google Drive / Sheets"
    if any(keyword in lowered for keyword in ("parse", "parser", "file description", "csv", "解析")):
        return "CSV 解析"
    if any(keyword in lowered for keyword in ("zip", "package", "compress", "打包")):
        return "Zip 打包"
    if any(keyword in lowered for keyword in ("unsupported test_type", "unsupported", "不支持")):
        return "产品/测试配置"
    if any(keyword in lowered for keyword in ("scp", "sftp", "robot_key", "permission denied")):
        return "Robot 数据拉取"
    if "exception occurred" in lowered:
        return "未捕获异常"
    return "上传流程"


def build_slack_failure_hints(
    error: str,
    *,
    failure_stage: str,
    upload_success: bool | None = None,
    database_success: bool | None = None,
) -> list[str]:
    lowered = error.lower()
    hints: list[str] = []

    if failure_stage == "数据库写入" or database_success is False:
        hints.append(
            "检查 MongoDB：`systemctl status mongod`，并查看 `/var/log/data-handler-error.log` 中的 `MongoDB 连接失败 - Host`。"
        )
    if failure_stage == "Google Drive / Sheets" or upload_success is False:
        hints.append(
            "检查 Google 鉴权与代理：确认 `/configs/token.json` 有效，且 `/opt/data-handler/backend/ghelper-test/` 文件完整。"
        )
    if failure_stage == "CSV 解析":
        hints.append("打开失败 CSV，确认 SN、test_name、operator 等字段是否符合当前产品 parser 规则。")
    if failure_stage == "产品/测试配置":
        hints.append("确认该产品型号与 test_name 已在 `product_catalog` / upload YAML 中配置。")
    if failure_stage == "Robot 数据拉取" or "robot_key" in lowered:
        hints.append("修复机器人私钥权限：`chmod 600 /root/robot_key && chown root:root /root/robot_key`。")
    if "proxy" in lowered or "ghelper" in lowered:
        hints.append("在服务器执行 `ls -la /opt/data-handler/backend/ghelper-test/`，必要时重新 `make update`。")
    if "file is not finished" in lowered:
        hints.append("CSV 对应测试可能尚未完成，确认设备端测试状态后再上传。")

    if not hints:
        hints.append("查看 Web UI 上传记录详情，并在服务器检索 `data-handler-error.log` 获取完整堆栈。")
    return hints


def build_slack_failure_title() -> str:
    return f"Data Upload Failed ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"


def notify_upload_result_to_slack(
    result: UploadApiResponse | None,
    csv_path: str,
    error_message: str | None = None,
    *,
    zip_path: str | None = None,
    record_id: str | None = None,
    upload_success: bool | None = None,
    database_success: bool | None = None,
) -> bool:
    try:
        from slack_driver.message import SlackBotMessenger

        bot = SlackBotMessenger()
        if result and result.get("finished"):
            slack_success = bot.send_test_result(
                channel=SLACK_UPLOAD_CHANNEL,
                test_type=build_slack_test_type(result),
                test_result=result.get("test_result"),
                serial_number=result.get("sn"),
                test_data_link=result.get("csv_link"),
                tracking_sheet_link=result.get("unit_tracker"),
                message_title=build_slack_upload_title(result),
            )
            logger.info("Slack upload success message sent" if slack_success else "Slack upload success message failed")
            return bool(slack_success)

        resolved_error = error_message or (result.get("error") if result else None) or "Unknown error"
        failure_stage = infer_slack_failure_stage(resolved_error)
        hints = build_slack_failure_hints(
            resolved_error,
            failure_stage=failure_stage,
            upload_success=upload_success,
            database_success=database_success,
        )
        slack_success = bot.send_fail_message(
            SLACK_UPLOAD_CHANNEL,
            error=resolved_error,
            title=build_slack_failure_title(),
            failure_stage=failure_stage,
            csv_path=csv_path,
            zip_path=zip_path,
            production_name=result.get("production_name") if result else None,
            test_type=result.get("test_type") if result else None,
            serial_number=result.get("sn") if result else None,
            record_id=record_id,
            upload_success=upload_success,
            database_success=database_success,
            unit_tracker_status=result.get("unit_tracker_status") if result else None,
            missing_tests=result.get("missing_tests") if result else None,
            hints=hints,
        )
        logger.info("Slack upload failure message sent" if slack_success else "Slack upload failure message failed")
        return bool(slack_success)
    except Exception as slack_err:
        logger.error(f"Failed to send slack upload message: {slack_err}")
        return False


def to_jsonable(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


def print_file_description(file_desc: FileDescription | None) -> None:
    print("==== File Description ====")
    if file_desc is None:
        print("None")
        return

    data = to_jsonable(file_desc.to_dict())
    try:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except TypeError:
        print(pformat(data))


def parse_csv_only(csv_path: str) -> int:
    file_desc = FileDescription.build(csv_path)
    print_file_description(file_desc)

    if file_desc is None:
        print("error: Failed to build file description")
        return 1
    if not file_desc.is_parse_successful:
        print(f"error: Failed to parse CSV: {file_desc.error}")
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    csv_path = resolve_cli_path(args.file)
    if not Path(csv_path).is_file():
        print(f"error: CSV file not found: {csv_path}")
        return 2

    if args.csv:
        return parse_csv_only(csv_path)

    zip_path = None
    if args.zip_file:
        zip_path = resolve_cli_path(args.zip_file)
        if not Path(zip_path).is_file():
            print(f"error: zip file not found: {zip_path}")
            return 2

    try:
        upload = UploadData()
        upload.init_upload_handler()
        result = upload.update_data_to_google_drive(csv_path, zip_file=zip_path)
    except Exception as exc:
        logger.exception("Upload CLI failed")
        notify_upload_result_to_slack(None, csv_path, error_message=str(exc))
        print(f"error: {exc}")
        return 1

    notify_upload_result_to_slack(result, csv_path)
    print_upload_result(result)
    return 0 if result and result.get("finished") else 1


if __name__ == "__main__":
    raise SystemExit(main())
