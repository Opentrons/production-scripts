"""Read the failed tests recorded by the upload pipeline."""
from __future__ import annotations

from datetime import datetime, timezone
import re

from bson import ObjectId

from modules.data_analysis.data import get_data_database, list_data_collections
from .parser import digest, normalized_time
from .products import normalize_product, product_from_serial
from .report_links import normalize_report_url


SERIAL_FIELDS = ("sn", "serial_number", "barcode", "test_tag")
PLACEHOLDERS = re.compile(r"^\s*(?:N\s*/?\s*A|none|null|-)?\s*$", re.I)
WORKSHEETS = {"assembly_qc": "Assembly QC", "current_speed": "Current/Speed Test"}
REPORT_TABS = {
    "gravimetric": ("Gravimetric Raw Data",),
    "burn_in": ("Burn in Test Results",),
}


def failure_text(record: dict) -> str:
    value = record.get("failure")
    if value is None or value == "":
        value = record.get("failures")
    if not isinstance(value, str) or PLACEHOLDERS.fullmatch(value):
        return ""
    return value.strip()


def _test_time(record: dict, run_ids: dict) -> str | None:
    for value in [*run_ids.values(), record.get("test_time"), record.get("test_date"), record.get("update_time")]:
        if isinstance(value, datetime):
            return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat()
        if timestamp := normalized_time(value):
            return timestamp
    return None


def report_from_record(collection: str, record: dict) -> dict | None:
    failure = failure_text(record)
    document_id = record["_id"]
    if not failure or not isinstance(document_id, (ObjectId, str, int)):
        return None
    sn = next((value.strip() for field in SERIAL_FIELDS if isinstance(value := record.get(field), str) and value.strip()), "")
    workflow = collection.split("_", 2)[-1]
    runs = {
        mode: value.strip() for mode in WORKSHEETS
        if isinstance(value := record.get(f"{mode}_run_id"), str) and value.strip()
    }
    if not runs and isinstance(run := record.get("test_run_id"), str) and run.strip():
        runs[workflow] = run.strip()
    mode = next(iter(runs)) if len(runs) == 1 and workflow == "assembly_qc" else workflow
    run_id = runs.get(mode, "")
    key = digest([collection, type(document_id).__name__, str(document_id)])
    name = " · ".join((collection, sn or "unknown-SN", run_id or str(document_id)))
    source = {
        "collection": collection, "id": str(document_id) if isinstance(document_id, ObjectId) else document_id,
        "id_type": type(document_id).__name__, "runs": runs,
        "url": normalize_report_url(record.get("csv_link")),
        "tabs": (
            [WORKSHEETS[mode] for mode in WORKSHEETS if record.get(mode) is not False]
            if workflow == "assembly_qc" and "_96ch_" not in collection
            else ["RawData"] if workflow == "assembly_qc" else list(REPORT_TABS.get(workflow, ()))
        ),
    }
    result = record.get("total_result") or record.get("total_qc_result")
    summary = [line.strip() for line in failure.splitlines() if line.strip()]
    return {
        "id": key, "source_group": f"mongodb/{key}/report", "source_name": name,
        "source_format": "test_report", "report_url": source["url"], "mongo_record": source,
        "sn": sn or "unknown-SN", "known_sn": bool(sn), "product": normalize_product(record.get("model")) or product_from_serial(sn),
        "test_time": _test_time(record, runs), "run_id": "", "report_run_id": run_id, "mode": mode,
        "kind": "test_failure", "stage": "test_report", "parse_status": "ready", "report_role": "main",
        "summary": summary, "failure_count": len(summary), "failures": [], "tests": {},
        "runtime_error": None, "last_failure": None, "recommendations": [], "warnings": [], "identity": {},
        "test_result": str(result) if result is not None else None,
        "mongo_confirmation": record.get("repair_confirmation") if isinstance(record.get("repair_confirmation"), str) else None,
        "mongo_confirmer": record.get("repair_confirmed_by") if isinstance(record.get("repair_confirmed_by"), str) else None,
        "revision": digest([key, sn, failure, runs, source["url"], result]),
    }


def read_mongo_reports(database=None) -> list[dict]:
    database = get_data_database() if database is None else database
    condition = {"$type": "string", "$not": PLACEHOLDERS}
    query = {"$or": [{"failure": condition}, {"failure": {"$in": [None, ""]}, "failures": condition}]}
    projection = dict.fromkeys((
        *SERIAL_FIELDS, "model", "failure", "failures", "csv_link", "test_run_id", "test_time", "test_date",
        "assembly_qc", "current_speed", "assembly_qc_run_id", "current_speed_run_id",
        "total_result", "total_qc_result", "update_time", "repair_confirmation", "repair_confirmed_by",
    ), 1)
    reports = []
    for name in list_data_collections(database):
        for record in database[name].find(query, projection):
            if report := report_from_record(name, record):
                reports.append(report)
    return reports


def document_id(source: dict):
    return ObjectId(source["id"]) if source["id_type"] == "ObjectId" else source["id"]
