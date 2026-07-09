from __future__ import annotations

from datetime import datetime
import re
from typing import Any

import settings as setting
from database.mongodb import mongodb

from api.services.data import serialize_mongo_doc
from api.services.logging import logger
from api.services.test_names import canonical_test_type, test_type_query_values, unique_test_types


PRODUCT_STATUS_OPTIONS = ["Testing", "Eng", "ProductionLine", "Shipped", "Scrapped"]


def get_product_collection():
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("Product management database connection failed")
    collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.PRODUCT_MANAGEMENT_COLLECTION]
    try:
        collection.create_index("barcode", unique=True)
        collection.create_index("model")
        collection.create_index("status")
        collection.create_index("tests.test_type")
        collection.create_index("latest_date")
    except Exception as exc:
        logger.warning(f"Product management index creation skipped: {exc}")
    return collection


def get_upload_record_collection():
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("Upload record database connection failed")
    return mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.DATA_UPLOAD_RECORD_COLLECTION]


def normalize_text(value: Any, default: str = "-") -> str:
    text = str(value or "").strip()
    if not text or text.upper() in {"N/A", "NA", "NONE", "NULL"}:
        return default
    return text


def normalize_link(value: Any) -> str:
    text = normalize_text(value)
    return "" if text == "-" else text


def resolve_barcode(record: dict[str, Any]) -> str:
    for value in (
        (record.get("file_desc") or {}).get("sn"),
        (record.get("result") or {}).get("sn"),
        (record.get("upload_result") or {}).get("sn"),
        (record.get("csv_file") or {}).get("name"),
    ):
        barcode = normalize_text(value, "")
        if barcode:
            return barcode
    return ""


def resolve_model(record: dict[str, Any]) -> str:
    return normalize_text(
        (record.get("file_desc") or {}).get("model")
        or (record.get("result") or {}).get("model")
        or (record.get("upload_result") or {}).get("model")
    )


def resolve_oem(record: dict[str, Any]) -> str:
    return normalize_text(
        (record.get("file_desc") or {}).get("kind_oem_type")
        or (record.get("result") or {}).get("production_type")
        or (record.get("upload_result") or {}).get("production_type")
        or (record.get("result") or {}).get("kind_oem_type")
        or (record.get("upload_result") or {}).get("kind_oem_type")
        or "Opentrons"
    )


def resolve_test_type(record: dict[str, Any]) -> str:
    return canonical_test_type(
        (record.get("result") or {}).get("test_type")
        or (record.get("file_desc") or {}).get("test_type")
        or (record.get("upload_result") or {}).get("upload_config_key")
    )


def resolve_record_date(record: dict[str, Any]) -> Any:
    return record.get("request_started_at") or record.get("updated_at") or record.get("request_finished_at")


def date_sort_value(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


def build_product_test(record: dict[str, Any]) -> dict[str, Any] | None:
    test_type = resolve_test_type(record)
    if not test_type:
        return None
    record_id = str(record.get("_id") or "")
    date = resolve_record_date(record)
    return {
        "key": record_id or f"{test_type}-{date_sort_value(date)}",
        "upload_record_id": record_id,
        "test_type": test_type,
        "status": str(record.get("status") or "Testing"),
        "date": date,
        "csv_link": normalize_link((record.get("result") or {}).get("csv_link") or (record.get("upload_result") or {}).get("csv_link")),
        "source_csv_path": normalize_link(
            (record.get("result") or {}).get("source_csv_path")
            or (record.get("upload_result") or {}).get("source_csv_path")
            or (record.get("csv_file") or {}).get("path")
        ),
    }


def normalize_product_test(test: dict[str, Any]) -> dict[str, Any]:
    normalized_test = dict(test)
    normalized_test["test_type"] = canonical_test_type(test.get("test_type"))
    return normalized_test


def normalize_product_document(product: dict[str, Any]) -> dict[str, Any]:
    normalized_product = dict(product)
    tests = [
        normalized_test
        for test in (product.get("tests") or [])
        if isinstance(test, dict) and (normalized_test := normalize_product_test(test)).get("test_type")
    ]
    tests.sort(key=lambda item: date_sort_value(item.get("date")), reverse=True)
    normalized_product["tests"] = tests
    normalized_product["test_types"] = unique_test_types([item.get("test_type") for item in tests])
    normalized_product["upload_record_count"] = len(tests)
    if tests:
        normalized_product["latest_date"] = tests[0].get("date")
    return normalized_product


def build_product_query(
    *,
    barcode: str | None = None,
    model: str | None = None,
    test_type: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    and_queries: list[dict[str, Any]] = []
    if barcode:
        escaped_barcode = re.escape(str(barcode).strip())
        if escaped_barcode:
            and_queries.append({"barcode": {"$regex": escaped_barcode, "$options": "i"}})
    if model:
        query["model"] = model
    if test_type:
        values = test_type_query_values(test_type)
        query["tests.test_type"] = {"$in": values}
    if status:
        query["status"] = status
    if and_queries:
        query["$and"] = and_queries
    return query


def sync_products_from_upload_records() -> dict[str, Any]:
    try:
        product_collection = get_product_collection()
        upload_collection = get_upload_record_collection()
        existing_products = {
            str(doc.get("barcode")): doc
            for doc in product_collection.find({})
            if doc.get("barcode")
        }
        source_records = 0
        skipped_records = 0
        existing_record_count = 0
        product_map: dict[str, dict[str, Any]] = {}

        for record in upload_collection.find({}).sort("request_started_at", -1):
            source_records += 1
            barcode = resolve_barcode(record)
            if not barcode:
                skipped_records += 1
                continue
            if barcode in existing_products:
                existing_record_count += 1
                continue

            product_test = build_product_test(record)
            if product_test is None:
                skipped_records += 1
                continue

            product = product_map.setdefault(
                barcode,
                {
                    "barcode": barcode,
                    "status": "Testing",
                    "model": resolve_model(record),
                    "oem": resolve_oem(record),
                    "tests": [],
                    "test_types": [],
                    "latest_date": None,
                    "upload_record_count": 0,
                },
            )
            if product["model"] == "-":
                product["model"] = resolve_model(record)
            if product["oem"] == "-":
                product["oem"] = resolve_oem(record)

            product["tests"].append(product_test)

        now = datetime.now()
        created_count = 0
        for barcode, product in product_map.items():
            product["tests"].sort(key=lambda item: date_sort_value(item.get("date")), reverse=True)
            product["upload_record_count"] = len(product["tests"])
            product["test_types"] = unique_test_types([item.get("test_type") for item in product["tests"]])
            product["latest_date"] = product["tests"][0].get("date") if product["tests"] else None
            product["created_at"] = now
            product["updated_at"] = now
            try:
                product_collection.insert_one(product)
                created_count += 1
            except Exception as exc:
                logger.warning(f"Skip product sync insert for {barcode}: {exc}")
                skipped_records += 1

        return {
            "success": True,
            "source_records": source_records,
            "skipped_records": skipped_records,
            "existing_records": existing_record_count,
            "total_products": len(product_map),
            "created_count": created_count,
            "updated_count": 0,
        }
    except Exception as exc:
        logger.error(f"Error syncing product management documents: {str(exc)}", exc_info=True)
        return {
            "success": False,
            "source_records": 0,
            "skipped_records": 0,
            "total_products": 0,
            "created_count": 0,
            "updated_count": 0,
            "error": str(exc),
        }


def get_products(
    page: int = 1,
    page_size: int = 100,
    barcode: str | None = None,
    model: str | None = None,
    test_type: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    try:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 2000)
        query = build_product_query(barcode=barcode, model=model, test_type=test_type, status=status)
        collection = get_product_collection()
        total = collection.count_documents(query)
        cursor = collection.find(query).sort("latest_date", -1).skip((page - 1) * page_size).limit(page_size)
        return {
            "products": [serialize_mongo_doc(normalize_product_document(doc)) for doc in cursor],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as exc:
        logger.error(f"Error fetching product management documents: {str(exc)}", exc_info=True)
        return {
            "products": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "error": str(exc),
        }


def get_filter_options() -> dict[str, Any]:
    try:
        collection = get_product_collection()
        return {
            "models": sorted(value for value in collection.distinct("model") if value and value != "-"),
            "statuses": PRODUCT_STATUS_OPTIONS,
            "test_types": unique_test_types(collection.distinct("tests.test_type")),
        }
    except Exception as exc:
        logger.error(f"Error fetching product management filter options: {str(exc)}")
        return {
            "models": [],
            "statuses": PRODUCT_STATUS_OPTIONS,
            "test_types": [],
            "error": str(exc),
        }


def update_product_status(barcode: str, status: str) -> dict[str, Any]:
    try:
        normalized_status = str(status).strip()
        if normalized_status not in PRODUCT_STATUS_OPTIONS:
            raise ValueError(f"Unsupported product status: {status}")
        result = get_product_collection().update_one(
            {"barcode": barcode},
            {
                "$set": {
                    "status": normalized_status,
                    "status_updated_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
            },
        )
        return {
            "success": result.matched_count > 0,
            "barcode": barcode,
            "status": normalized_status,
            "matched_count": result.matched_count,
            "modified_count": result.modified_count,
        }
    except Exception as exc:
        logger.error(f"Error updating product status: {str(exc)}")
        return {
            "success": False,
            "barcode": barcode,
            "status": status,
            "matched_count": 0,
            "modified_count": 0,
            "error": str(exc),
        }


def add_manual_product_or_test(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        barcode = normalize_text(payload.get("barcode"), "")
        model = normalize_text(payload.get("model"), "")
        oem = normalize_text(payload.get("oem"), "")
        test_type = canonical_test_type(payload.get("test_type"))
        status = normalize_text(payload.get("status") or "Testing")
        if not barcode:
            raise ValueError("barcode is required")
        if not model:
            raise ValueError("Productions is required")
        if not oem:
            raise ValueError("Type is required")
        if not test_type:
            raise ValueError("Test Data is required")
        if status not in PRODUCT_STATUS_OPTIONS:
            raise ValueError(f"Unsupported product status: {status}")

        now = datetime.now()
        manual_test = {
            "key": f"manual-{test_type}-{now.strftime('%Y%m%d%H%M%S%f')}",
            "upload_record_id": "",
            "test_type": test_type,
            "status": "manual",
            "date": now,
            "csv_link": normalize_link(payload.get("csv_link")),
            "source_csv_path": normalize_link(payload.get("source_csv_path") or payload.get("csv_link")),
            "source": "manual",
        }
        collection = get_product_collection()
        existing = collection.find_one({"barcode": barcode})
        created_product = existing is None
        if existing:
            tests = list(existing.get("tests") or [])
            tests.append(manual_test)
            tests.sort(key=lambda item: date_sort_value(item.get("date")), reverse=True)
            normalized_existing_tests = [normalize_product_test(item) for item in tests]
            tests = [item for item in normalized_existing_tests if item.get("test_type")]
            test_types = unique_test_types([item.get("test_type") for item in tests])
            collection.update_one(
                {"barcode": barcode},
                {
                    "$set": {
                        "model": model,
                        "oem": oem,
                        "tests": tests,
                        "test_types": test_types,
                        "latest_date": tests[0].get("date") if tests else now,
                        "upload_record_count": len(tests),
                        "updated_at": now,
                    }
                },
            )
        else:
            collection.insert_one(
                {
                    "barcode": barcode,
                    "status": status,
                    "model": model,
                    "oem": oem,
                    "tests": [manual_test],
                    "test_types": [test_type],
                    "latest_date": now,
                    "upload_record_count": 1,
                    "created_at": now,
                    "updated_at": now,
                    "source": "manual",
                }
            )
        product = collection.find_one({"barcode": barcode})
        return {
            "success": True,
            "barcode": barcode,
            "created_product": created_product,
            "added_test": True,
            "product": serialize_mongo_doc(normalize_product_document(product)) if product else None,
        }
    except Exception as exc:
        logger.error(f"Error adding manual product/test: {str(exc)}")
        return {
            "success": False,
            "barcode": str(payload.get("barcode") or ""),
            "created_product": False,
            "added_test": False,
            "product": None,
            "error": str(exc),
        }
