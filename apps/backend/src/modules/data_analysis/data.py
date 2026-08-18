from __future__ import annotations

import base64
from datetime import datetime, time, timezone
import hashlib
import json
import re
from typing import Any

from bson import ObjectId
import core.config as setting
from core.database import mongodb
from modules.uploads.handler.product_catalog import get_upload_collection_name
from pymongo.errors import AutoReconnect, ConnectionFailure, NetworkTimeout, ServerSelectionTimeoutError

from core.logging import get_logger

logger = get_logger(__name__)

ALL_COLLECTIONS_KEY = "__all__"
DATA_COLLECTION_PREFIX = "pipette_"
TEST_DATA_DATABASE_ERROR = "Test data database connection failed"
COLLECTION_CURSOR_VERSION = 1


class InvalidCollectionCursor(ValueError):
    pass


class CollectionNotFoundError(LookupError):
    pass


class CollectionDataUnavailableError(RuntimeError):
    pass


def get_data_database():
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError(TEST_DATA_DATABASE_ERROR)
    return mongodb.get_database(setting.DATA_DB_NAME)


def format_data_error(exc: Exception) -> str:
    if isinstance(
        exc,
        (AutoReconnect, ConnectionFailure, NetworkTimeout, ServerSelectionTimeoutError),
    ):
        return TEST_DATA_DATABASE_ERROR
    message = str(exc).strip()
    if mongodb.client is None or not message or "NoneType" in message:
        return TEST_DATA_DATABASE_ERROR
    return message


def serialize_mongo_doc(doc: dict) -> dict:
    doc["_id"] = str(doc.get("_id", ""))
    return doc


def get_test_data(page: int = 1, page_size: int = 20, test_type: str | None = None) -> dict:
    try:
        skip = (page - 1) * page_size
        model_by_test_type = {
            "1ch": "P1000S",
            "8ch": "P1000M",
            "96ch": "P1KH",
        }
        collection_name = get_upload_collection_name(model_by_test_type["1ch"])
        if test_type == "8ch":
            collection_name = get_upload_collection_name(model_by_test_type["8ch"])
        elif test_type == "96ch":
            collection_name = get_upload_collection_name(model_by_test_type["96ch"])

        collection = get_data_database()[collection_name]
        query = {}
        if test_type:
            query["test_type"] = test_type

        total = collection.count_documents(query)
        cursor = collection.find(query).skip(skip).limit(page_size).sort("test_date", -1)
        data = [serialize_mongo_doc(doc) for doc in cursor]
        return {
            "data": data,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as exc:
        error = format_data_error(exc)
        logger.error(f"Error fetching test data: {error}")
        return {
            "data": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "error": error,
        }


def list_data_collections(db=None) -> list[str]:
    database = get_data_database() if db is None else db
    return sorted(
        name
        for name in database.list_collection_names()
        if name.startswith(DATA_COLLECTION_PREFIX)
    )


def get_collections() -> dict:
    try:
        collections = list_data_collections()
        return {
            "collections": collections,
            "total": len(collections),
        }
    except Exception as exc:
        error = format_data_error(exc)
        logger.error(f"Error fetching collections: {error}")
        return {
            "collections": [],
            "total": 0,
            "error": error,
        }


def parse_date_bound(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    if not value:
        return None

    raw_value = str(value).strip()
    if not raw_value:
        return None

    try:
        if len(raw_value) == 10:
            parsed_date = datetime.fromisoformat(raw_value).date()
            return datetime.combine(parsed_date, time.max if end_of_day else time.min)
        parsed_datetime = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        if getattr(parsed_datetime, "tzinfo", None) is not None:
            parsed_datetime = parsed_datetime.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed_datetime
    except ValueError:
        logger.warning(f"Invalid date filter ignored: {value}")
        return None


def build_collection_query(
    *,
    model: str | None = None,
    production_type: str | None = None,
    total_result: str | None = None,
    barcode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    query: dict = {}
    if model:
        query["model"] = model
    if production_type:
        query["type"] = production_type
    if total_result:
        query["$or"] = [
            {"total_result": total_result},
            {"total_qc_result": total_result},
        ]

    if barcode:
        escaped_barcode = re.escape(str(barcode).strip())
        if escaped_barcode:
            barcode_query = [
                {"sn": {"$regex": escaped_barcode, "$options": "i"}},
                {"serial_number": {"$regex": escaped_barcode, "$options": "i"}},
                {"barcode": {"$regex": escaped_barcode, "$options": "i"}},
                {"test_tag": {"$regex": escaped_barcode, "$options": "i"}},
            ]
            if "$or" in query:
                query["$and"] = [{"$or": query.pop("$or")}, {"$or": barcode_query}]
            else:
                query["$or"] = barcode_query

    start_time = parse_date_bound(start_date)
    end_time = parse_date_bound(end_date, end_of_day=True)
    if start_time or end_time:
        update_time_query = {}
        if start_time:
            update_time_query["$gte"] = start_time
        if end_time:
            update_time_query["$lte"] = end_time
        query["update_time"] = update_time_query

    return query


def _combine_queries(*queries: dict[str, Any]) -> dict[str, Any]:
    populated = [query for query in queries if query]
    if not populated:
        return {}
    if len(populated) == 1:
        return populated[0]
    return {"$and": populated}


def _normalize_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _format_utc_datetime(value: datetime) -> str:
    normalized = _normalize_utc_datetime(value).replace(tzinfo=timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


def _parse_cursor_datetime(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise InvalidCollectionCursor("Cursor timestamp is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidCollectionCursor("Cursor timestamp is invalid") from exc
    return _normalize_utc_datetime(parsed)


def _cursor_scope(
    *,
    collection_name: str,
    model: str | None,
    production_type: str | None,
    total_result: str | None,
    barcode: str | None,
    start_date: str | None,
    end_date: str | None,
) -> str:
    payload = {
        "barcode": barcode or "",
        "collection_name": collection_name,
        "end_date": end_date or "",
        "model": model or "",
        "start_date": start_date or "",
        "total_result": total_result or "",
        "type": production_type or "",
    }
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _encode_collection_cursor(
    *,
    scope: str,
    snapshot_time: datetime,
    update_time: datetime,
    collection: str,
    document_id: ObjectId,
) -> str:
    payload = {
        "position": {
            "collection": collection,
            "id": str(document_id),
            "update_time": _format_utc_datetime(update_time),
        },
        "scope": scope,
        "snapshot_time": _format_utc_datetime(snapshot_time),
        "v": COLLECTION_CURSOR_VERSION,
    }
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_collection_cursor(cursor: str, *, expected_scope: str) -> dict[str, Any]:
    if not cursor or len(cursor) > 2048:
        raise InvalidCollectionCursor("Cursor is empty or too long")
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidCollectionCursor("Cursor cannot be decoded") from exc

    if not isinstance(payload, dict) or payload.get("v") != COLLECTION_CURSOR_VERSION:
        raise InvalidCollectionCursor("Cursor version is unsupported")
    if payload.get("scope") != expected_scope:
        raise InvalidCollectionCursor("Cursor does not match the current filters")

    position = payload.get("position")
    if not isinstance(position, dict):
        raise InvalidCollectionCursor("Cursor position is missing")
    collection = position.get("collection")
    document_id = position.get("id")
    if not isinstance(collection, str) or not collection:
        raise InvalidCollectionCursor("Cursor collection is invalid")
    if not isinstance(document_id, str) or not ObjectId.is_valid(document_id):
        raise InvalidCollectionCursor("Cursor document id is invalid")

    return {
        "snapshot_time": _parse_cursor_datetime(payload.get("snapshot_time")),
        "update_time": _parse_cursor_datetime(position.get("update_time")),
        "collection": collection,
        "document_id": ObjectId(document_id),
    }


def _cursor_position_query(position: dict[str, Any]) -> dict[str, Any]:
    update_time = position["update_time"]
    collection = position["collection"]
    document_id = position["document_id"]
    return {
        "$or": [
            {"update_time": {"$lt": update_time}},
            {"update_time": update_time, "collection": {"$gt": collection}},
            {
                "update_time": update_time,
                "collection": collection,
                "_id": {"$lt": document_id},
            },
        ]
    }


def _first_present(document: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = document.get(key)
        if value is not None and value != "":
            return value
    return None


def _public_text(document: dict[str, Any], *keys: str) -> str | None:
    value = _first_present(document, *keys)
    return str(value) if value is not None else None


def _public_collection_item(document: dict[str, Any]) -> dict[str, Any]:
    update_time = document.get("update_time")
    if not isinstance(update_time, datetime):
        raise CollectionDataUnavailableError("Collection record has an invalid update_time")
    return {
        "collection": str(document.get("collection") or ""),
        "update_time": _format_utc_datetime(update_time),
        "sn": _public_text(document, "sn", "serial_number", "barcode", "test_tag"),
        "model": _public_text(document, "model"),
        "type": _public_text(document, "type"),
        "total_result": _public_text(document, "total_result", "total_qc_result"),
    }


def get_collection_data_cursor(
    collection_name: str = ALL_COLLECTIONS_KEY,
    limit: int = 200,
    cursor: str | None = None,
    model: str | None = None,
    production_type: str | None = None,
    total_result: str | None = None,
    barcode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    limit = min(max(limit, 1), 1000)
    scope = _cursor_scope(
        collection_name=collection_name,
        model=model,
        production_type=production_type,
        total_result=total_result,
        barcode=barcode,
        start_date=start_date,
        end_date=end_date,
    )
    position = _decode_collection_cursor(cursor, expected_scope=scope) if cursor else None
    snapshot_time = (
        position["snapshot_time"]
        if position
        else datetime.now(timezone.utc).replace(tzinfo=None)
    )

    try:
        database = get_data_database()
        available_collections = list_data_collections(database)
        if collection_name == ALL_COLLECTIONS_KEY:
            collections = available_collections
        elif collection_name in available_collections:
            collections = [collection_name]
        else:
            raise CollectionNotFoundError(collection_name)

        if not collections:
            return {
                "data": [],
                "count": 0,
                "limit": limit,
                "has_more": False,
                "next_cursor": None,
                "collection": collection_name,
                "snapshot_time": _format_utc_datetime(snapshot_time),
            }

        base_query = build_collection_query(
            model=model,
            production_type=production_type,
            total_result=total_result,
            barcode=barcode,
            start_date=start_date,
            end_date=end_date,
        )
        collection_query = _combine_queries(
            base_query,
            {"update_time": {"$type": "date", "$lte": snapshot_time}},
        )
        pipeline: list[dict[str, Any]] = [
            {"$match": collection_query},
            {"$addFields": {"collection": {"$literal": collections[0]}}},
        ]
        for name in collections[1:]:
            pipeline.append(
                {
                    "$unionWith": {
                        "coll": name,
                        "pipeline": [
                            {"$match": collection_query},
                            {"$addFields": {"collection": {"$literal": name}}},
                        ],
                    }
                }
            )
        if position:
            pipeline.append({"$match": _cursor_position_query(position)})
        pipeline.extend(
            [
                {"$sort": {"update_time": -1, "collection": 1, "_id": -1}},
                {"$limit": limit + 1},
                {
                    "$project": {
                        "_id": 1,
                        "barcode": 1,
                        "collection": 1,
                        "model": 1,
                        "serial_number": 1,
                        "sn": 1,
                        "test_tag": 1,
                        "total_qc_result": 1,
                        "total_result": 1,
                        "type": 1,
                        "update_time": 1,
                    }
                },
            ]
        )

        documents = list(database[collections[0]].aggregate(pipeline))
        has_more = len(documents) > limit
        page_documents = documents[:limit]
        data = [_public_collection_item(document) for document in page_documents]
        next_cursor = None
        if has_more and page_documents:
            last = page_documents[-1]
            document_id = last.get("_id")
            update_time = last.get("update_time")
            if not isinstance(document_id, ObjectId) or not isinstance(update_time, datetime):
                raise CollectionDataUnavailableError("Collection cursor fields are invalid")
            next_cursor = _encode_collection_cursor(
                scope=scope,
                snapshot_time=snapshot_time,
                update_time=update_time,
                collection=str(last.get("collection") or ""),
                document_id=document_id,
            )

        return {
            "data": data,
            "count": len(data),
            "limit": limit,
            "has_more": has_more,
            "next_cursor": next_cursor,
            "collection": collection_name,
            "snapshot_time": _format_utc_datetime(snapshot_time),
        }
    except (InvalidCollectionCursor, CollectionNotFoundError, CollectionDataUnavailableError):
        raise
    except Exception as exc:
        error = format_data_error(exc)
        logger.error(f"Error fetching cursor collection data: {error}")
        raise CollectionDataUnavailableError(error) from exc


def get_collection_filter_options(collection_name: str) -> dict:
    try:
        db_productions = get_data_database()
        if collection_name == ALL_COLLECTIONS_KEY:
            models: set[str] = set()
            types: set[str] = set()
            total_results: set[str] = set()
            for coll_name in list_data_collections(db_productions):
                collection = db_productions[coll_name]
                models.update(value for value in collection.distinct("model") if value)
                types.update(value for value in collection.distinct("type") if value)
                total_results.update(
                    value
                    for value in [
                        *collection.distinct("total_result"),
                        *collection.distinct("total_qc_result"),
                    ]
                    if value
                )
            return {
                "models": sorted(models),
                "types": sorted(types),
                "total_results": sorted(total_results),
            }

        if collection_name not in db_productions.list_collection_names():
            return {
                "models": [],
                "types": [],
                "total_results": [],
                "error": f"Collection '{collection_name}' does not exist",
            }

        collection = db_productions[collection_name]
        total_results = {
            value
            for value in [
                *collection.distinct("total_result"),
                *collection.distinct("total_qc_result"),
            ]
            if value
        }
        return {
            "models": sorted([value for value in collection.distinct("model") if value]),
            "types": sorted([value for value in collection.distinct("type") if value]),
            "total_results": sorted(total_results),
        }
    except Exception as exc:
        error = format_data_error(exc)
        logger.error(f"Error fetching collection filter options: {error}")
        return {
            "models": [],
            "types": [],
            "total_results": [],
            "error": error,
        }


def get_all_collection_data(
    page: int = 1,
    page_size: int = 20,
    model: str | None = None,
    production_type: str | None = None,
    total_result: str | None = None,
    barcode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    db_productions = get_data_database()
    collections = list_data_collections(db_productions)
    if not collections:
        return {
            "data": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "collection": ALL_COLLECTIONS_KEY,
        }

    query = build_collection_query(
        model=model,
        production_type=production_type,
        total_result=total_result,
        barcode=barcode,
        start_date=start_date,
        end_date=end_date,
    )
    skip = (page - 1) * page_size

    if len(collections) == 1:
        coll_name = collections[0]
        collection = db_productions[coll_name]
        total = collection.count_documents(query)
        cursor = collection.find(query).skip(skip).limit(page_size).sort("update_time", -1)
        data = [serialize_mongo_doc(doc) for doc in cursor]
        for doc in data:
            doc["collection"] = coll_name
        return {
            "data": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "collection": ALL_COLLECTIONS_KEY,
        }

    pipeline: list[dict] = [
        {"$match": query},
        {"$addFields": {"collection": {"$literal": collections[0]}}},
    ]
    for coll_name in collections[1:]:
        pipeline.append(
            {
                "$unionWith": {
                    "coll": coll_name,
                    "pipeline": [
                        {"$match": query},
                        {"$addFields": {"collection": {"$literal": coll_name}}},
                    ],
                }
            }
        )
    pipeline.extend(
        [
            {"$sort": {"update_time": -1}},
            {
                "$facet": {
                    "metadata": [{"$count": "total"}],
                    "data": [{"$skip": skip}, {"$limit": page_size}],
                }
            },
        ]
    )
    facet_result = next(iter(db_productions[collections[0]].aggregate(pipeline)), {})
    metadata = facet_result.get("metadata") or []
    total = metadata[0]["total"] if metadata else 0
    data = [serialize_mongo_doc(doc) for doc in facet_result.get("data", [])]
    return {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "collection": ALL_COLLECTIONS_KEY,
    }


def get_collection_data(
    collection_name: str,
    page: int = 1,
    page_size: int = 20,
    model: str | None = None,
    production_type: str | None = None,
    total_result: str | None = None,
    barcode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    try:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        skip = (page - 1) * page_size
        db_productions = get_data_database()

        if collection_name == ALL_COLLECTIONS_KEY:
            return get_all_collection_data(
                page=page,
                page_size=page_size,
                model=model,
                production_type=production_type,
                total_result=total_result,
                barcode=barcode,
                start_date=start_date,
                end_date=end_date,
            )

        if collection_name not in db_productions.list_collection_names():
            return {
                "data": [],
                "total": 0,
                "error": f"Collection '{collection_name}' does not exist",
            }

        collection = db_productions[collection_name]
        query = build_collection_query(
            model=model,
            production_type=production_type,
            total_result=total_result,
            barcode=barcode,
            start_date=start_date,
            end_date=end_date,
        )
        total = collection.count_documents(query)
        cursor = collection.find(query).skip(skip).limit(page_size).sort("update_time", -1)
        data = [serialize_mongo_doc(doc) for doc in cursor]
        return {
            "data": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "collection": collection_name,
        }
    except Exception as exc:
        error = format_data_error(exc)
        logger.error(f"Error fetching collection data: {error}")
        return {
            "data": [],
            "total": 0,
            "error": error,
        }
