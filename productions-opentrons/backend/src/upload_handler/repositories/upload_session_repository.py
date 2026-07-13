from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from settings import get_logger
from upload_handler.product_catalog import (
    get_upload_database_config,
    get_upload_database_peer_fields,
    get_upload_workflow,
    get_upload_workflow_from_config_key,
    is_upload_result_successful,
)

logger = get_logger(__name__)

UPLOAD_SESSION_COLLECTION = "upload_sessions"


class UploadSessionRepository:
    """Mongo repository for upload workflows that span multiple test files."""

    def __init__(self, mongo) -> None:
        self.mongo = mongo

    def find_reusable_sheet(
        self,
        db_name: str,
        collection_name: str,
        device_sn: str,
        current_test: str,
        required_test: str,
        expire_days: int,
        model: str = "",
    ) -> str | None:
        if not model:
            logger.warning("Skip reusable upload session lookup because model is empty")
            return None

        collection = self._collection(db_name)
        workflow = self.resolve_workflow(model, current_test)
        expire_time = datetime.now() - timedelta(days=expire_days)
        query = {
            "sn": device_sn,
            "model": model,
            "workflow": workflow,
            f"tests.{required_test}.status": "uploaded",
            f"tests.{current_test}.status": {"$ne": "uploaded"},
            "updated_at": {"$gte": expire_time},
        }
        session = collection.find_one(query, sort=[("updated_at", -1)])
        if not session:
            return None

        sheet_link = session.get("sheet_link")
        logger.info(
            "Found reusable upload session: sn=%s workflow=%s sheet_link=%s",
            device_sn,
            workflow,
            sheet_link,
        )
        return sheet_link

    def find_reusable_sheet_by_config(
        self,
        db_name: str,
        device_sn: str,
        model: str,
        config_key: str,
        expire_days: int,
    ) -> str | None:
        peer_fields = get_upload_database_peer_fields(config_key)
        if not peer_fields:
            return None

        current_field = get_upload_database_config(config_key).test_field
        workflow = get_upload_workflow_from_config_key(config_key)
        expire_time = datetime.now() - timedelta(days=expire_days)
        query = {
            "sn": device_sn,
            "model": model,
            "workflow": workflow,
            f"tests.{current_field}.status": {"$ne": "uploaded"},
            "$or": [
                {f"tests.{peer_field}.status": "uploaded"}
                for peer_field in peer_fields
            ],
            "updated_at": {"$gte": expire_time},
        }
        session = self._collection(db_name).find_one(query, sort=[("updated_at", -1)])
        if not session:
            return None

        sheet_link = session.get("sheet_link")
        logger.info(
            "Found reusable upload session: sn=%s workflow=%s sheet_link=%s",
            device_sn,
            workflow,
            sheet_link,
        )
        return sheet_link

    def delete_workflow_session(
        self,
        db_name: str,
        device_sn: str,
        model: str,
        workflow: str,
    ) -> int:
        result = self._collection(db_name).delete_many(
            {
                "sn": device_sn,
                "model": model,
                "workflow": workflow,
            }
        )
        deleted_count = int(result.deleted_count)
        if deleted_count:
            logger.info(
                "Deleted upload session: sn=%s workflow=%s count=%s",
                device_sn,
                workflow,
                deleted_count,
            )
        return deleted_count

    def mark_uploaded(self, db_name: str, collection_name: str, result: dict[str, Any]) -> bool:
        tests = self.extract_test_updates(result)
        if not tests:
            return False

        sn = result.get("sn")
        model = result.get("model", "")
        if not sn:
            logger.warning("Skip upload session update because result.sn is empty")
            return False
        if not model:
            logger.warning("Skip upload session update because result.model is empty")
            return False

        now = datetime.now()
        collection = self._collection(db_name)
        config_key = result.get("upload_config_key")
        if config_key:
            workflow = get_upload_workflow_from_config_key(config_key)
        else:
            workflow = self.resolve_workflow(model, next(iter(tests)))

        query = {
            "sn": sn,
            "model": model,
            "workflow": workflow,
        }
        set_fields = {
            "collection_name": collection_name,
            "production_type": result.get("type", ""),
            "updated_at": now,
        }
        for key in ("csv_link", "unit_tracker", "raw_data"):
            value = result.get(key)
            if value:
                set_fields[self._session_field_name(key)] = value

        for test_name, status in tests.items():
            set_fields[f"tests.{test_name}"] = {
                "status": status,
                "result": self.extract_test_result(result, test_name),
                "csv_link": result.get("csv_link", ""),
                "raw_data": result.get("raw_data", ""),
                "updated_at": now,
            }

        update = {
            "$setOnInsert": {
                "sn": sn,
                "model": model,
                "workflow": workflow,
                "created_at": now,
            },
            "$set": set_fields,
        }
        collection.update_one(query, update, upsert=True)
        return True

    @staticmethod
    def resolve_workflow(model: str, test_name: str) -> str:
        return get_upload_workflow(model, test_name)

    @staticmethod
    def extract_test_updates(result: dict[str, Any]) -> dict[str, str]:
        config_key = result.get("upload_config_key")
        if config_key:
            db_config = get_upload_database_config(config_key)
            status = "uploaded" if is_upload_result_successful(config_key, result) else "failed"
            return {db_config.test_field: status}

        test_keys = (
            "gravimetric",
            "assembly_qc",
            "current_speed",
            "ninety_six_assembly_qc",
        )
        updates = {}
        for key in test_keys:
            if key not in result:
                continue
            updates[key] = "uploaded" if result.get(key) is True else "failed"

        return updates

    @staticmethod
    def extract_test_result(result: dict[str, Any], test_name: str) -> str:
        return result.get("total_result", "")

    @staticmethod
    def _session_field_name(result_key: str) -> str:
        if result_key == "csv_link":
            return "sheet_link"
        return result_key

    def _collection(self, db_name: str):
        return self.mongo.get_database(db_name)[UPLOAD_SESSION_COLLECTION]
