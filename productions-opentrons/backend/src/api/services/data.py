from __future__ import annotations

from datetime import datetime, time
import re

import settings as setting
from database.mongodb import mongodb
from upload_handler.product_catalog import get_upload_collection_name

from api.services.logging import logger

ALL_COLLECTIONS_KEY = "__all__"
DATA_COLLECTION_PREFIX = "pipette_"


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

        collection = mongodb.get_database(setting.DATA_DB_NAME)[collection_name]
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
        logger.error(f"Error fetching test data: {str(exc)}")
        return {
            "data": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "error": str(exc),
        }


def list_data_collections(db=None) -> list[str]:
    database = mongodb.get_database(setting.DATA_DB_NAME) if db is None else db
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
        logger.error(f"Error fetching collections: {str(exc)}")
        return {
            "collections": [],
            "total": 0,
            "error": str(exc),
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
            parsed_datetime = parsed_datetime.replace(tzinfo=None)
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


def get_collection_filter_options(collection_name: str) -> dict:
    try:
        db_productions = mongodb.get_database(setting.DATA_DB_NAME)
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
        logger.error(f"Error fetching collection filter options: {str(exc)}")
        return {
            "models": [],
            "types": [],
            "total_results": [],
            "error": str(exc),
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
    db_productions = mongodb.get_database(setting.DATA_DB_NAME)
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
        db_productions = mongodb.get_database(setting.DATA_DB_NAME)

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
        logger.error(f"Error fetching collection data: {str(exc)}")
        return {
            "data": [],
            "total": 0,
            "error": str(exc),
        }
