from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import core.config as setting


ALLOWED_QUERY_OPERATORS = {"$and", "$or", "$eq", "$ne", "$in", "$nin", "$gt", "$gte", "$lt", "$lte", "$exists", "$regex", "$options"}


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_dump(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _dump(item) for key, item in value.items()}
    return value


def current_time() -> dict[str, str]:
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    return {"datetime": now.isoformat(), "date": now.strftime("%Y-%m-%d"), "timezone": "Asia/Shanghai"}


def platform_overview() -> dict[str, Any]:
    from core.runtime_mode import get_simulating_status
    from modules.data_analysis import product_management
    from modules.protocol_monitor import service as protocol_service
    from modules.robots import robots, version_records
    from modules.system import messages
    from modules.uploads import upload_records
    from modules.workflows.runtime import workflow_service

    sections: dict[str, Any] = {"runtime": get_simulating_status(), "queried_at": current_time()["datetime"]}
    checks = {
        "upload_stats": upload_records.get_upload_record_stats,
        "products": lambda: product_management.get_products(page=1, page_size=1),
        "devices": lambda: robots.load_robot_scan_cache(setting.ROBOT_HEALTH_PORT),
        "versions": lambda: version_records.list_history(page=1, page_size=1),
        "protocol_rooms": protocol_service.list_rooms,
        "messages": messages.get_messages,
        "workflows": workflow_service.list_workflows,
    }
    for key, function in checks.items():
        try:
            value = _dump(function())
            if key == "products":
                value = {"total": value.get("total", 0)}
            elif key == "devices":
                value = {
                    "online_count": value.get("online_count", 0),
                    "offline_count": value.get("offline_count", 0),
                    "abnormal_count": value.get("abnormal_count", 0),
                    "scan_network": value.get("scan_network"),
                    "last_scan_at": value.get("last_scan_at"),
                }
            elif key == "versions":
                value = {"total": value.get("total", 0), "storage": value.get("storage")}
            elif key == "protocol_rooms":
                value = {"total": len(value.get("rooms") or []), "storage": value.get("storage")}
            elif key == "messages":
                value = {"total": value.get("total", 0), "unread_count": value.get("unread_count", 0)}
            elif key == "workflows":
                value = {"total": len(value), "active": sum(1 for item in value if item.get("status") == "active")}
            sections[key] = value
        except Exception as exc:
            sections[key] = {"error": str(exc)}
    return sections


def query_upload_records(
    status: str = "",
    model: str = "",
    barcode: str = "",
    start_date: str = "",
    end_date: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    from modules.uploads.upload_records import get_upload_records

    return get_upload_records(
        page=page,
        page_size=min(max(int(page_size), 1), 100),
        status=status or None,
        model=model or None,
        barcode=barcode or None,
        start_date=start_date or None,
        end_date=end_date or None,
    )


def analyze_upload_records(
    status: str = "",
    model: str = "",
    barcode: str = "",
    start_date: str = "",
    end_date: str = "",
) -> dict[str, Any]:
    from modules.uploads.upload_records import get_upload_record_stats

    return get_upload_record_stats(
        status=status or None,
        model=model or None,
        barcode=barcode or None,
        start_date=start_date or None,
        end_date=end_date or None,
    )


def query_products(
    barcode: str = "",
    model: str = "",
    test_type: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    from modules.data_analysis.product_management import get_products

    return get_products(
        page=page,
        page_size=min(max(int(page_size), 1), 100),
        barcode=barcode or None,
        model=model or None,
        test_type=test_type or None,
        status=status or None,
    )


def query_unit_tracker(
    source: str = "mongodb",
    product: str = "",
    test_type: str = "",
    barcode: str = "",
    page: int = 1,
    page_size: int = 30,
    refresh: bool = False,
) -> dict[str, Any]:
    from modules.data_analysis.unit_tracker import list_rows

    normalized_source = str(source or "mongodb").strip()
    if normalized_source not in {"mongodb", "google_drive"}:
        raise ValueError("source 只能是 mongodb 或 google_drive")
    if normalized_source == "google_drive" and (not product or not test_type):
        raise ValueError("Google Drive Unit Tracker 查询必须提供 product 和 test_type")
    return list_rows(
        page=page,
        page_size=min(max(int(page_size), 1), 100),
        product=product or None,
        test_type=test_type or None,
        barcode=barcode or None,
        source=normalized_source,
        refresh=bool(refresh),
    )


def list_data_links() -> dict[str, Any]:
    from modules.data_analysis.data_links import get_data_links

    return get_data_links()


def query_test_data(
    collection: str = "__all__",
    model: str = "",
    production_type: str = "",
    total_result: str = "",
    barcode: str = "",
    start_date: str = "",
    end_date: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    from modules.data_analysis.data import get_collection_data

    return get_collection_data(
        collection_name=collection or "__all__",
        page=page,
        page_size=min(max(int(page_size), 1), 100),
        model=model or None,
        production_type=production_type or None,
        total_result=total_result or None,
        barcode=barcode or None,
        start_date=start_date or None,
        end_date=end_date or None,
    )


def list_test_data_collections() -> dict[str, Any]:
    from modules.data_analysis.data import get_collections

    return get_collections()


def query_devices(ip: str = "", include_detail: bool = False) -> dict[str, Any]:
    from modules.robots import robots

    normalized_ip = str(ip or "").strip()
    if normalized_ip and include_detail:
        return {"device": robots.get_robot_detail(normalized_ip, setting.ROBOT_HEALTH_PORT)}
    cached = robots.load_robot_scan_cache(setting.ROBOT_HEALTH_PORT)
    if normalized_ip:
        robots_list = [
            item for item in [*(cached.get("online_robots") or []), *(cached.get("offline_robots") or [])]
            if str(item.get("ip") or "") == normalized_ip
        ]
        return {"devices": robots_list, "total": len(robots_list), "cached": True}
    return cached


def query_version_history(page: int = 1, page_size: int = 30, ip: str = "") -> dict[str, Any]:
    from modules.robots.version_records import get_current_robot_versions, list_history

    if str(ip or "").strip():
        return get_current_robot_versions(str(ip).strip(), setting.ROBOT_HEALTH_PORT)
    return list_history(page=page, page_size=min(max(int(page_size), 1), 100))


async def query_protocol_monitor(room_id: str = "", refresh_status: bool = False) -> dict[str, Any]:
    from modules.protocol_monitor import service

    normalized_room_id = str(room_id or "").strip()
    if refresh_status:
        if not normalized_room_id:
            raise ValueError("刷新 Protocol 状态必须提供 room_id")
        return _dump(await service.refresh_room_status(normalized_room_id))
    response = _dump(service.list_rooms())
    if normalized_room_id:
        response["rooms"] = [item for item in response.get("rooms") or [] if item.get("id") == normalized_room_id]
    return response


def query_workflows(workflow_id: str = "", include_runs: bool = True, limit: int = 20) -> dict[str, Any]:
    from modules.workflows.runtime import workflow_service

    normalized_id = str(workflow_id or "").strip()
    workflows = [workflow_service.get_workflow(normalized_id)] if normalized_id else workflow_service.list_workflows()
    payload: dict[str, Any] = {"workflows": _dump(workflows), "total": len(workflows)}
    if include_runs:
        payload["runs"] = _dump(workflow_service.list_run_summaries(workflow_id=normalized_id or None, limit=min(max(int(limit), 1), 100)))
    return payload


def query_test_cases(product_id: str = "", test_type: str = "", include_archived: bool = False) -> dict[str, Any]:
    from modules.test_management.domain.services.test_case_service import test_case_service

    response = test_case_service.list_cases(
        product_id=product_id or None,
        test_type=test_type or None,
        include_archived=bool(include_archived),
    )
    return _dump(response)


def search_sop_catalog(query: str = "", refresh: bool = False, limit: int = 30) -> dict[str, Any]:
    from modules.sop.runtime import sop_service

    response = sop_service.get_master_sheet(refresh=bool(refresh)).model_dump(mode="json")
    needle = str(query or "").strip().casefold()
    entries = response.get("entries") or []
    if needle:
        entries = [
            item for item in entries
            if needle in " ".join(str(value) for value in item.values()).casefold()
        ]
    response["entries"] = entries[: max(1, min(int(limit), 100))]
    response["matched_rows"] = len(entries)
    return response


def query_messages(limit: int = 30, unread_only: bool = False) -> dict[str, Any]:
    from modules.system.messages import get_messages

    result = get_messages()
    messages = result.get("messages") or []
    if unread_only:
        messages = [item for item in messages if item.get("new") is True]
    result["messages"] = messages[: max(1, min(int(limit), 50))]
    return result


def _sanitize_query(value: Any, *, depth: int = 0) -> Any:
    if depth > 6:
        raise ValueError("查询条件层级过深")
    if isinstance(value, dict):
        result = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            if key.startswith("$") and key not in ALLOWED_QUERY_OPERATORS:
                raise ValueError(f"不允许的查询操作符: {key}")
            if "\x00" in key or len(key) > 200:
                raise ValueError("查询字段名无效")
            result[key] = _sanitize_query(item, depth=depth + 1)
        return result
    if isinstance(value, list):
        if len(value) > 200:
            raise ValueError("查询数组过长")
        return [_sanitize_query(item, depth=depth + 1) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("查询条件只支持 JSON 基础类型")


def _nested_get(document: dict[str, Any], path: str) -> Any:
    current: Any = document
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _matches_operator(actual: Any, operator: str, expected: Any, options: str = "") -> bool:
    if operator == "$eq":
        return actual == expected
    if operator == "$ne":
        return actual != expected
    if operator == "$in":
        return actual in expected
    if operator == "$nin":
        return actual not in expected
    if operator == "$exists":
        return (actual is not None) == bool(expected)
    if operator == "$regex":
        flags = re.IGNORECASE if "i" in options else 0
        return bool(re.search(str(expected), str(actual or ""), flags=flags))
    try:
        if operator == "$gt":
            return actual > expected
        if operator == "$gte":
            return actual >= expected
        if operator == "$lt":
            return actual < expected
        if operator == "$lte":
            return actual <= expected
    except TypeError:
        return False
    return True


def _matches_filter(document: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, expected in query.items():
        if key == "$and":
            if not all(_matches_filter(document, item) for item in expected):
                return False
            continue
        if key == "$or":
            if not any(_matches_filter(document, item) for item in expected):
                return False
            continue
        actual = _nested_get(document, key)
        if isinstance(expected, dict):
            options = str(expected.get("$options") or "")
            if not all(
                _matches_operator(actual, operator, value, options)
                for operator, value in expected.items()
                if operator != "$options"
            ):
                return False
        elif actual != expected:
            return False
    return True


def _resolve_collection(dataset: str, collection_name: str = ""):
    normalized = str(dataset or "").strip()
    if normalized == "upload_records":
        from modules.uploads.upload_records import get_upload_record_collection

        return get_upload_record_collection()
    if normalized == "messages":
        from modules.system.messages import _get_message_collection

        return _get_message_collection()
    if normalized == "product_management":
        from modules.data_analysis.product_management import get_product_collection

        return get_product_collection()
    if normalized == "unit_tracker":
        from modules.data_analysis.unit_tracker import get_unit_tracker_collection

        return get_unit_tracker_collection()
    if normalized == "version_history":
        from modules.robots.version_records import _get_collection

        return _get_collection()
    if normalized == "protocol_rooms":
        from modules.protocol_monitor.service import _get_collection

        return _get_collection()
    if normalized == "robot_scan_cache":
        from modules.robots.robots import get_robot_scan_cache_collection

        return get_robot_scan_cache_collection()
    if normalized == "test_cases":
        from modules.test_management.domain.config import TEST_CASE_COLLECTION_NAME
        from modules.test_management.domain.repositories.test_case_repository import test_case_repository

        return test_case_repository._database()[TEST_CASE_COLLECTION_NAME]
    if normalized == "test_data":
        from modules.data_analysis.data import get_data_database, list_data_collections

        database = get_data_database()
        available = list_data_collections(database)
        if collection_name not in available:
            raise ValueError(f"测试数据集合不存在。可选: {', '.join(available)}")
        return database[collection_name]
    raise ValueError("不支持的数据集")


def query_platform_database(
    dataset: str,
    collection_name: str = "",
    filters: dict[str, Any] | None = None,
    fields: list[str] | None = None,
    sort_by: str = "",
    sort_direction: str = "desc",
    limit: int = 50,
) -> dict[str, Any]:
    return _query_platform_database(
        dataset=dataset,
        collection_name=collection_name,
        filters=filters,
        fields=fields,
        sort_by=sort_by,
        sort_direction=sort_direction,
        limit=limit,
        limit_cap=200,
    )


def _query_platform_database(
    dataset: str,
    collection_name: str,
    filters: dict[str, Any] | None,
    fields: list[str] | None,
    sort_by: str,
    sort_direction: str,
    limit: int,
    limit_cap: int,
) -> dict[str, Any]:
    safe_filter = _sanitize_query(filters or {})
    safe_fields = [str(field).strip() for field in (fields or []) if str(field).strip()][:100]
    normalized_limit = max(1, min(int(limit), max(1, int(limit_cap))))
    collection = _resolve_collection(dataset, collection_name)
    is_sqlite = hasattr(collection, "_store")

    if is_sqlite:
        documents = [dict(item) for item in collection.find({}) if _matches_filter(dict(item), safe_filter)]
        if sort_by:
            documents.sort(
                key=lambda item: str(_nested_get(item, sort_by) or ""),
                reverse=str(sort_direction).lower() != "asc",
            )
        total = len(documents)
        documents = documents[:normalized_limit]
    else:
        projection = {field: 1 for field in safe_fields} if safe_fields else None
        cursor = collection.find(safe_filter, projection)
        total = collection.count_documents(safe_filter)
        if sort_by:
            cursor = cursor.sort(sort_by, 1 if str(sort_direction).lower() == "asc" else -1)
        documents = [dict(item) for item in cursor.limit(normalized_limit)]

    if safe_fields and is_sqlite:
        documents = [
            {field: _nested_get(document, field) for field in safe_fields if _nested_get(document, field) is not None}
            for document in documents
        ]
    return {
        "dataset": dataset,
        "collection": collection_name or None,
        "filters": safe_filter,
        "records": documents,
        "returned": len(documents),
        "total": total,
        "truncated": total > len(documents),
        "storage": "sqlite" if is_sqlite else "mongodb",
    }


def aggregate_platform_database(
    dataset: str,
    collection_name: str = "",
    filters: dict[str, Any] | None = None,
    group_by: str = "",
    value_field: str = "",
    operation: str = "count",
    limit: int = 2000,
) -> dict[str, Any]:
    normalized_operation = str(operation or "count").lower()
    if normalized_operation not in {"count", "sum", "average", "min", "max"}:
        raise ValueError("operation 只能是 count、sum、average、min 或 max")
    query_result = _query_platform_database(
        dataset=dataset,
        collection_name=collection_name,
        filters=filters,
        fields=None,
        sort_by="",
        sort_direction="desc",
        limit=min(max(int(limit), 1), 2000),
        limit_cap=2000,
    )
    records = query_result["records"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = str(_nested_get(record, group_by) if group_by else "all")
        groups[key].append(record)

    results = []
    for key, items in groups.items():
        values = [
            float(value)
            for item in items
            for value in [_nested_get(item, value_field)]
            if value is not None and isinstance(value, (int, float))
        ]
        if normalized_operation == "count":
            value: int | float | None = len(items)
        elif not values:
            value = None
        elif normalized_operation == "sum":
            value = sum(values)
        elif normalized_operation == "average":
            value = sum(values) / len(values)
        elif normalized_operation == "min":
            value = min(values)
        else:
            value = max(values)
        results.append({"group": key, "value": value, "record_count": len(items)})
    results.sort(key=lambda item: (item["value"] is not None, item["value"] or 0), reverse=True)
    return {
        "dataset": dataset,
        "collection": collection_name or None,
        "operation": normalized_operation,
        "group_by": group_by or None,
        "value_field": value_field or None,
        "groups": results[:100],
        "analyzed_records": len(records),
        "source_total": query_result["total"],
        "source_truncated": query_result["truncated"],
    }
