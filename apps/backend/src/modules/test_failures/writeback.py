"""Synchronize repair confirmations with the matching product test document."""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Callable

from pymongo.errors import PyMongoError

from modules.data_analysis.data import CollectionDataUnavailableError, get_data_database
from modules.uploads.handler.product_catalog import get_upload_collection_name
from .mongo_reports import SERIAL_FIELDS, WORKSHEETS, document_id, failure_text, report_from_record
from .parser import digest
from .products import normalize_product
from .report_link_source import GoogleReportLinkSource
from .repository import ConflictError, NotFoundError, Repository, evidence_version

if TYPE_CHECKING:
    from .service import TestFailureService


logger = logging.getLogger(__name__)
SUPPORTED_PRODUCTS = {"P50S", "P1000S", "P50M", "P1000M"}
MAX_CANDIDATES = 12
AUTO_BATCH_SIZE = 12


def _writeback_product(report: dict) -> str | None:
    product = normalize_product(report.get("product"))
    if (report.get("mode") in WORKSHEETS and product in SUPPORTED_PRODUCTS and report.get("report_role") == "main"
            and report.get("parse_status") == "ready" and report.get("known_sn")
            and (report.get("report_run_id") or "").strip()):
        return product
    return None


def write_pending_confirmations(
    service: TestFailureService, database_name: str, interval: float, *, stopped: Callable[[], bool],
) -> None:
    """Process a bounded batch and persist retries across service restarts."""
    pending = service.repository.pending_writebacks(database_name, time.time(), AUTO_BATCH_SIZE)
    database = None
    for report, updated_at, attempts in pending:
        if stopped():
            return
        report_id = report["id"]
        retry_at = None
        if report["source_format"] == "test_report" or _writeback_product(report):
            if database is None:
                database = get_data_database()
            try:
                result = write_confirmation(
                    service, report_id, report["revision"], evidence_version(report), database=database,
                )
                if result["status"] == "written":
                    logger.info("Synchronized repair confirmation for report %s to %s", report_id, result["collection"])
            except (NotFoundError, ConflictError, CollectionDataUnavailableError) as exc:
                retry_at = time.time() + max(interval, min(3600, 30 * 2 ** min(attempts, 7)))
                logger.info("Automatic writeback for report %s will retry: %s", report_id, exc)
        service.repository.record_writeback(database_name, report_id, updated_at, attempts + 1, retry_at)


def repair_confirmation_fields(
    repository: Repository, sn: str, run_ids: dict[str, str | None], *, expected_report: tuple[str, str] | None = None,
    uploaded_confirmation: dict | None = None,
) -> dict:
    confirmations = [uploaded_confirmation] if uploaded_confirmation else []
    matched_reports = set()
    for mode, run_id in run_ids.items():
        if not run_id:
            continue
        reports = [report for report in repository.writeback_reports(sn, mode, run_id) if _writeback_product(report)]
        if len(reports) > 1:
            if expected_report:
                raise ConflictError("相同 SN、运行编号及测试模式存在多份失败报告")
            continue
        if reports:
            report = reports[0]
            identity = (report["id"], report["revision"])
            matched_reports.add(identity)
            confirmation = repository.latest_report_confirmation(*identity)
            if confirmation:
                confirmations.append(confirmation)
    if expected_report is not None and expected_report not in matched_reports:
        raise ConflictError("报告证据已更新，请刷新详情后重试")
    latest = max(confirmations, key=lambda item: (item["created_at"], item["id"]), default=None)
    return {
        "repair_confirmation": latest["text"] if latest else None,
        "repair_confirmed_by": (latest.get("confirmed_by_name") or latest["created_by_name"]) if latest else None,
    }


def _record_run_ids(repository: Repository, record: dict, report: dict) -> dict[str, str | None]:
    sn, mode = report["sn"], report["mode"]
    run_ids = {name: record.get(f"{name}_run_id") for name in WORKSHEETS}
    run_ids[mode] = report["report_run_id"].strip()
    for peer, worksheet in WORKSHEETS.items():
        if not run_ids[peer] and record.get(peer) is not False and record.get("csv_link"):
            if not any(_writeback_product(item) for item in repository.writeback_reports(sn, peer, None)):
                continue
            try:
                identity = GoogleReportLinkSource().read_identity(record["csv_link"], worksheet=worksheet)
            except Exception as exc:
                raise CollectionDataUnavailableError("暂时无法核对合并记录的测试表格，请稍后重试") from exc
            if identity["sn"] == sn:
                run_ids[peer] = identity["report_run_id"]
    return run_ids


def _matching_record(collection, report: dict, worksheet: str, run_field: str) -> dict:
    sn, run_id = report["sn"], report["report_run_id"].strip()
    serial_query = {"$or": [{key: sn} for key in SERIAL_FIELDS]}
    projected_fields = (
        *SERIAL_FIELDS, "assembly_qc_run_id", "current_speed_run_id", "csv_link",
        "assembly_qc", "current_speed", "test_run_id", "total_result", "total_qc_result", "update_time",
        "failure", "failures", "repair_confirmation", "repair_confirmed_by",
    )
    projection = dict.fromkeys(projected_fields, 1)
    records = list(collection.find({"$and": [serial_query, {run_field: run_id}]}, projection).limit(2))
    if not records:
        legacy_query = {"$and": [
            serial_query, {run_field: {"$in": [None, ""]}}, {report["mode"]: {"$ne": False}},
        ]}
        candidates = list(collection.find(legacy_query, projection).limit(MAX_CANDIDATES + 1))
        if len(candidates) > MAX_CANDIDATES:
            raise ConflictError("历史测试记录过多，无法唯一核对运行编号")
        if candidates:
            try:
                source = GoogleReportLinkSource()
                identities = {}
                for candidate in candidates:
                    link = candidate.get("csv_link")
                    if not link or link in {"N/A", "NA"}:
                        raise ValueError("Missing worksheet link")
                    if link not in identities:
                        identities[link] = source.read_identity(link, worksheet=worksheet)
                    identity = identities[link]
                    if (identity["sn"], identity["report_run_id"]) == (sn, run_id):
                        records.append(candidate)
            except Exception as exc:
                logger.warning("Legacy QC worksheet identity unavailable: %s", type(exc).__name__)
                raise CollectionDataUnavailableError("暂时无法核对历史测试表格，请稍后重试") from exc
    if len(records) > 1:
        raise ConflictError("同一 SN 与运行编号对应多条记录，无法唯一写回")
    if not records:
        raise NotFoundError("未找到相同 SN 和运行编号的已上传测试记录")
    return records[0]


def _write_mongo_report_confirmation(repository: Repository, database, report: dict) -> dict:
    source = report["mongo_record"]
    name = source["collection"]
    collection = database[name]
    record = collection.find_one({"_id": document_id(source)})
    current = report_from_record(name, record) if record else None
    if not current or current["revision"] != report["revision"]:
        raise ConflictError("测试数据已更新，请刷新报告后重试")
    confirmation = repository.latest_report_confirmation(report["id"], report["revision"])
    if not confirmation and not repository.has_report_confirmation(report["id"]):
        return {"status": "unchanged", "collection": name}
    native_runs = source["runs"] if name in {"pipette_1ch_assembly_qc", "pipette_8ch_assembly_qc"} else {}
    fields = repair_confirmation_fields(repository, report["sn"], native_runs, uploaded_confirmation=confirmation)
    if all(record.get(key) == value for key, value in fields.items()):
        return {"status": "unchanged", "collection": name}
    match = {key: record.get(key) for key in (
        "_id", "failure", "failures", "csv_link", "assembly_qc_run_id", "current_speed_run_id", "test_run_id",
        "update_time", "total_result", "total_qc_result", *SERIAL_FIELDS, *fields,
    )}
    result = collection.update_one(match, {
        "$set": fields,
        "$currentDate": {"sync_updated_at": True, "repair_confirmation_updated_at": True},
    })
    if not result.matched_count:
        raise ConflictError("测试数据已更新，请重新核对后再写回")
    return {"status": "written", "collection": name}


def write_confirmation(service: TestFailureService, report_id: str, revision: str, evidence: str, *, database=None) -> dict:
    report = service.repository.get_report(report_id)
    if report.get("inactive") or report["revision"] != revision or evidence_version(report) != evidence:
        raise ConflictError("报告证据已更新，请刷新详情后重试")
    if report["source_format"] == "test_report":
        try:
            database = get_data_database() if database is None else database
            return _write_mongo_report_confirmation(service.repository, database, report)
        except (PyMongoError, RuntimeError) as exc:
            raise CollectionDataUnavailableError("测试数据存储暂时不可用，请稍后重试") from exc
    mode = report["mode"]
    product = _writeback_product(report)
    if not product:
        raise ConflictError("当前报告缺少可核对的 1ch / 8ch QC 主报告证据")

    collection_name = get_upload_collection_name(product)
    run_field = f"{mode}_run_id"
    try:
        if database is None:
            database = get_data_database()
        collection = database[collection_name]
        record = _matching_record(collection, report, WORKSHEETS[mode], run_field)
        total_result = record.get("total_result") or record.get("total_qc_result")
        if not failure_text(record) and str(total_result).strip().casefold() != "fail":
            raise ConflictError("匹配的测试记录没有失败判定")

        run_ids = _record_run_ids(service.repository, record, report)
        with service.open_attachment(report_id, "json", _snapshot_content=False)[0]:
            current = service.repository.get_report(report_id)
            if current["revision"] != revision or evidence_version(current) != evidence:
                raise ConflictError("报告证据已更新，请刷新详情后重试")

        uploaded_confirmation = None
        if uploaded := report_from_record(collection_name, record):
            uploaded_id = digest([service.repository.root_key, uploaded["id"]])
            uploaded_confirmation = service.repository.latest_report_confirmation(uploaded_id, uploaded["revision"])
        fields = repair_confirmation_fields(
            service.repository, report["sn"], run_ids, expected_report=(report["id"], revision),
            uploaded_confirmation=uploaded_confirmation,
        )
        if all(key in record and record[key] == value for key, value in fields.items()):
            return {"status": "unchanged", "collection": collection_name}

        # The selected document may still be updated by another upload or editor.
        match = {key: record.get(key) for key in (
            "_id", "update_time", "csv_link", "assembly_qc_run_id", "current_speed_run_id", "test_run_id",
            "assembly_qc", "current_speed", "total_result", "total_qc_result", "failure", "failures",
            "repair_confirmation", "repair_confirmed_by",
            *SERIAL_FIELDS,
        )}
        result = collection.update_one(match, {
            "$set": fields,
            "$currentDate": {"sync_updated_at": True, "repair_confirmation_updated_at": True},
        })
    except (PyMongoError, RuntimeError) as exc:
        if isinstance(exc, CollectionDataUnavailableError):
            raise
        raise CollectionDataUnavailableError("测试数据存储暂时不可用，请稍后重试") from exc
    if not result.matched_count:
        raise ConflictError("测试数据已更新，请重新核对后再写回")
    return {"status": "written", "collection": collection_name}
