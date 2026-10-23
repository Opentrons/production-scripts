from __future__ import annotations

import re
from typing import Any

import core.config as setting
from core.persistence import get_message_database
from modules.ecn.models import EcnRecord
from pymongo import UpdateOne


class MongoEcnRepository:
    def __init__(self) -> None:
        self._initialized = False

    def _collection(self):
        collection = get_message_database()[setting.ECN_RECORDS_COLLECTION]
        if not self._initialized:
            collection.create_index("source_row")
            collection.create_index("ecn_number")
            collection.create_index("origin")
            collection.create_index("table")
            self._initialized = True
        return collection

    @staticmethod
    def _selector(table: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        selector: dict[str, Any] = {"$or": [{"table": table}, {"table": {"$exists": False}}]} if table == "eng" else {"table": table}
        if extra:
            selector.update(extra)
        return selector

    def google_count(self, table: str = "eng") -> int:
        return int(self._collection().count_documents(self._selector(table, {"origin": "google"})))

    def insert_initial_google_records(self, records: list[EcnRecord]) -> int:
        collection = self._collection()
        operations = []
        for record in records:
            document = self._to_document(record)
            document.pop("_id", None)
            operations.append(
                UpdateOne(
                    {"_id": record.id},
                    {"$setOnInsert": document},
                    upsert=True,
                )
            )
        if not operations:
            return 0
        result = collection.bulk_write(operations, ordered=False)
        return int(getattr(result, "upserted_count", 0))

    def sync_google_records(self, records: list[EcnRecord], table: str = "eng") -> int:
        """Make Google-origin records for one table match the source rows."""
        collection = self._collection()
        operations = []
        for record in records:
            document = self._to_document(record)
            document.pop("_id", None)
            operations.append(UpdateOne(
                {"_id": record.id},
                {"$set": document, "$setOnInsert": {"_id": record.id}},
                upsert=True,
            ))
        if operations:
            collection.bulk_write(operations, ordered=False)
        ids = [record.id for record in records]
        stale = self._selector(table, {"origin": "google"})
        if ids:
            stale["_id"] = {"$nin": ids}
        result = collection.delete_many(stale)
        return int(getattr(result, "deleted_count", 0))

    def list(
        self,
        *,
        search: str,
        page: int,
        page_size: int,
        sort_order: str,
        table: str = "eng",
        status: str = "",
    ) -> tuple[list[EcnRecord], int]:
        selector: dict[str, Any] = self._selector(table)
        filters: list[dict[str, Any]] = [selector]
        if search:
            expression = {"$regex": re.escape(search), "$options": "i"}
            filters.append({"$or": [
                    {"ecn_number": expression},
                    {"ecn_title": expression},
                    {"form_number": expression},
                    {"product_name": expression},
                    {"change_item": expression},
                    {"changed_by": expression},
                ]})
        if status:
            filters.append({"extra_fields.status": status})
        if len(filters) > 1:
            selector = {"$and": filters}
        collection = self._collection()
        total = int(collection.count_documents(selector))
        direction = 1 if sort_order == "asc" else -1
        documents = collection.aggregate([
            {"$match": selector},
            {
                "$set": {
                    "_ecn_number_match": {
                        "$regexFind": {
                            "input": {"$ifNull": ["$ecn_number", ""]},
                            "regex": r"\d+",
                        }
                    }
                }
            },
            {
                "$set": {
                    "_ecn_has_number": {
                        "$cond": [{"$ne": ["$_ecn_number_match", None]}, 1, 0]
                    },
                    "_ecn_sort_number": {
                        "$convert": {
                            "input": "$_ecn_number_match.match",
                            "to": "long",
                            "onError": -1,
                            "onNull": -1,
                        }
                    },
                }
            },
            {
                "$sort": {
                    "_ecn_has_number": -1,
                    "_ecn_sort_number": direction,
                    "source_row": direction,
                }
            },
            {"$skip": (page - 1) * page_size},
            {"$limit": page_size},
            {
                "$project": {
                    "_ecn_number_match": 0,
                    "_ecn_has_number": 0,
                    "_ecn_sort_number": 0,
                }
            },
        ])
        return [self._from_document(item) for item in documents], total

    def status_options(self, table: str = "eng") -> list[str]:
        values = self._collection().distinct("extra_fields.status", self._selector(table))
        return sorted({str(value).strip() for value in values if str(value).strip()})

    def find_by_number(self, ecn_number: str, table: str = "eng") -> EcnRecord | None:
        document = self._collection().find_one(self._selector(table, {"ecn_number": ecn_number}))
        return self._from_document(document) if document else None

    def max_sequence_number(self, table: str = "eng") -> int | None:
        documents = list(self._collection().aggregate([
            {
                "$set": {
                    "_ecn_number_match": {
                        "$regexFind": {
                            "input": {"$ifNull": ["$ecn_number", ""]},
                            "regex": r"\d+",
                        }
                    }
                }
            },
            {
                "$set": {
                    "_ecn_sequence_number": {
                        "$convert": {
                            "input": "$_ecn_number_match.match",
                            "to": "long",
                            "onError": None,
                            "onNull": None,
                        }
                    }
                }
            },
            {"$match": {"_ecn_sequence_number": {"$ne": None}, **self._selector(table)}},
            {"$sort": {"_ecn_sequence_number": -1}},
            {"$limit": 1},
            {"$project": {"_ecn_sequence_number": 1}},
        ]))
        if not documents:
            return None
        return int(documents[0]["_ecn_sequence_number"])

    def changed_by_options(self, table: str = "eng") -> list[str]:
        return sorted(value for value in self._collection().distinct("changed_by", self._selector(table))
                      if isinstance(value, str) and value.strip())

    def insert_created(self, record: EcnRecord) -> None:
        self._collection().insert_one(self._to_document(record))

    def find_by_id(self, record_id: str) -> EcnRecord | None:
        document = self._collection().find_one({"_id": record_id})
        return self._from_document(document) if document else None

    def replace(self, record: EcnRecord) -> None:
        self._collection().replace_one({"_id": record.id}, self._to_document(record))

    def delete(self, record_id: str) -> None:
        self._collection().delete_one({"_id": record_id})

    def google_records(self, table: str = "eng") -> list[EcnRecord]:
        return [
            self._from_document(item)
            for item in self._collection().find(self._selector(table, {"origin": "google"}))
        ]

    def master_records(self, table: str = "eng") -> list[EcnRecord]:
        return [self._from_document(item) for item in self._collection().find(self._selector(table, {"source_row": {"$gt": 0}}))]

    @staticmethod
    def _to_document(record: EcnRecord) -> dict[str, Any]:
        document = record.model_dump(mode="python")
        document["_id"] = document.pop("id")
        return document

    @staticmethod
    def _from_document(document: dict[str, Any]) -> EcnRecord:
        payload = dict(document)
        payload["id"] = str(payload.pop("_id", payload.get("id", "")))
        return EcnRecord.model_validate(payload)
