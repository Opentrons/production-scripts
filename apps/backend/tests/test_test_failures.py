from __future__ import annotations

import json
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth.dependencies import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME, get_auth_service
from modules.auth.service import AuthService
from modules.test_failures import routes, scanner
from modules.test_failures.service import ConflictError, NotFoundError, TestFailureService as FailureService


PREFIX = "/api/defect-search/test-failures"
SERIAL = "SYNTHETIC-P1000M-001"
RUN_ID = "synthetic-trace-run"
REPORT_RUN_ID = "run-26-10-29-03-16-26"


def row(tag="pressure-check", *, result="FAIL", recorded=True, index=0):
    failed = result == "FAIL"
    return {
        "section": "FIXTURE",
        "tag": tag,
        "index": index,
        "evidence_id": f"FIXTURE/{tag}[{index}]",
        "record_status": "recorded" if recorded else "not_recorded",
        "result": result,
        "data": [3.5, result] if recorded else [None, None],
        "elapsed_seconds": 1.5,
        "failure_reasons": ["[PRESSURE_VALUE_OUT_OF_RANGE] Pressure outside tolerance"] if failed else [],
        "error_codes": ["PRESSURE_VALUE_OUT_OF_RANGE"] if failed else [],
    }


def bundle(**changes):
    return {
        "schema_version": 1,
        "run_id": RUN_ID,
        "report_run_id": REPORT_RUN_ID,
        "created_at_utc": "2026-10-29T03:16:26Z",
        "mode": "assembly_qc",
        "stage": "result-summary",
        "archive_directory": {
            "serial_number": SERIAL,
            "timestamp_utc": "20261029T031626Z",
            "serial_source": "report.test_device_id",
            "remote_subdir": f"{SERIAL}/20261029T031626Z",
        },
        "failure_details": ["Pressure check failed"],
        "runtime_error": None,
        "exception_traceback": None,
        "report_rows": [row()],
        "trace": {
            "identity": {
                "actual_pipettes": {
                    "LEFT": {"serial": SERIAL, "model": "p1000_multi_v3", "name": "flex_8channel_1000", "channels": 8},
                    "RIGHT": {"serial": "SYNTHETIC-REFERENCE-ONLY", "model": "p50_single_v3", "channels": 1},
                }
            },
            "tests": {"FIXTURE": {"status": "failed"}},
            "last_failure": None,
        },
        "recommendations": [],
        "artifacts": [
            {"role": "manifest", "path": "/robot/local/qc.json", "upload_status": "pending_self_upload"},
            {"role": "readable_log", "path": "/robot/local/qc.log", "upload_status": "uploaded"},
        ],
    } | changes


def write_bundle(root: Path, payload=None, *, name="qc") -> Path:
    path = root / SERIAL / "20261029T031626Z" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload if payload is not None else bundle()), encoding="utf-8")
    return path


def rewrite_json_preserving_stat(path: Path, payload):
    original = path.stat()
    encoded = json.dumps(payload).encode("utf-8")
    assert len(encoded) == original.st_size
    path.write_bytes(encoded)
    os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
    updated = path.stat()
    assert (updated.st_ino, updated.st_size, updated.st_mtime_ns) == (
        original.st_ino, original.st_size, original.st_mtime_ns,
    )


def readable_log(payload):
    metadata_row = {
        "section": "META_DATA", "tag": "test_run_id", "index": 0,
        "evidence_id": "META_DATA/test_run_id[0]", "result": "unknown",
        "record_status": "recorded", "data": [payload["report_run_id"]],
        "failure_reasons": [], "error_codes": [],
    }
    return "\n".join([
        "Time UTC: " + payload["created_at_utc"],
        "Run ID: " + payload["run_id"],
        "QC mode: " + payload["mode"],
        "Stage: " + payload["stage"],
        "Completed modes: none",
        "Failure archive directory: " + json.dumps(payload["archive_directory"]),
        "Run parameters: {}", "", "Failure details:",
        *("- " + value for value in payload["failure_details"]),
        "", "Failure action and latest observed readings (not trigger-time values):",
        json.dumps({"last_failure": payload["trace"]["last_failure"], "latest_readings": {}}),
        "", "Run identity / versions:", json.dumps(payload["trace"]["identity"]),
        "", "Test execution states:", json.dumps(payload["trace"]["tests"]),
        "", "All report rows (unknown or not_recorded does not mean PASS):",
        json.dumps(metadata_row),
        *(json.dumps(value) for value in payload["report_rows"]),
        "",
    ])


@pytest.fixture
def evidence(tmp_path):
    root = tmp_path / "test-failure-uploads"
    root.mkdir()
    database_path = tmp_path / "state" / "failures.sqlite3"
    return root, database_path, FailureService(root, database_path, stable_seconds=0)


def only_device(service):
    devices = service.list_devices()["devices"]
    assert len(devices) == 1
    return devices[0]


def only_report(service):
    reports = only_device(service)["reports"]
    assert len(reports) == 1
    return service.get_report(reports[0]["id"])


def confirmation_text_records(items):
    """Compare original note fields independently of version coverage metadata."""
    return [{key: value for key, value in item.items() if key != "coverage"} for item in items]


def confirm(service, device, text="复测并确认压力偏差", author="alice"):
    return service.confirm_device(
        device["id"], text, device["version"], author, created_by_name=author.title(),
    )


def write_device_report(root, *, serial, product, name, report_run_id=REPORT_RUN_ID,
                        test_time="2026-10-29T03:16:26Z", mode="assembly_qc", runtime=False,
                        description="Synthetic pressure failure", report_folder=None):
    payload = bundle(run_id=f"synthetic-{name}", report_run_id=report_run_id, mode=mode,
                     created_at_utc=test_time, failure_details=[description])
    payload["archive_directory"].update(serial_number=serial, timestamp_utc=test_time)
    payload["trace"]["identity"]["actual_pipettes"]["LEFT"].update(serial=serial, name=product, model=product)
    if runtime:
        payload["report_rows"] = [row("not-started", result="unknown", recorded=False)]
        payload["runtime_error"] = {"type": "RuntimeError", "message": "Synthetic execution failure"}
        payload["trace"]["tests"] = {"FIXTURE": {"status": "execution_error"}}
    # Reports for these filter/search cases deliberately share one fixture
    # archive per serial. Cross-folder behavior is exercised separately below.
    path = root / (report_folder or f"{serial}_fixture-archive") / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def counts(total, pending, confirmed):
    return {"total": total, "pending": pending, "confirmed": confirmed}


def product_counts(result):
    return {item["product"]: {key: item[key] for key in ("total", "pending", "confirmed")}
            for item in result["facets"]["products"]}


@pytest.fixture
def categorized_evidence(evidence):
    root, _, service = evidence
    write_device_report(root, serial="FACET-A", product="p50_multi_flex", name="a-new", description="cohort-red pressure")
    write_device_report(root, serial="FACET-A", product="flex_8channel_50", name="a-old",
                        report_run_id="run-26-10-28-03-16-26", test_time="2026-10-28T03:16:26Z",
                        mode="volume_qc", runtime=True)
    write_device_report(root, serial="FACET-B", product="flex_8channel_50", name="b")
    write_device_report(root, serial="FACET-C", product="flex_8channel_1000", name="c", runtime=True,
                        description="cohort-red execution")
    write_device_report(root, serial="FACET-D", product="flex_1channel_50", name="d",
                        report_run_id="run-26-10-28-03-16-26", test_time="2026-10-28T03:16:26Z", mode="volume_qc")
    service.scan()
    for device in service.list_devices()["devices"]:
        if device["sn"] in {"FACET-B", "FACET-D"}:
            confirm(service, device)
    return root, service


@pytest.mark.parametrize("confirmation", ["all", "pending", "confirmed"])
def test_facets_count_devices_before_pagination_and_ignore_other_classification_filters(categorized_evidence, confirmation):
    _, service = categorized_evidence
    expected_totals = {"all": 2, "pending": 1, "confirmed": 1}
    expected_products = {"P50M": counts(2, 1, 1), "P1000M": counts(1, 1, 0), "P50S": counts(1, 0, 1)}
    pages = [service.list_devices(product="P50M", confirmation=confirmation, page=page, page_size=1)
             for page in (1, 2)]
    for result in pages:
        assert result["total"] == expected_totals[confirmation]
        assert result["facets"]["all"] == counts(4, 2, 2)
        assert product_counts(result) == expected_products
        assert result["facets"]["confirmation"] == counts(2, 1, 1)
    returned = [device for result in pages for device in result["devices"]]
    assert len(returned) == expected_totals[confirmation]
    assert len({device["id"] for device in returned}) == expected_totals[confirmation]
    assert {device["product"] for device in returned} == {"P50M"}
    if confirmation == "pending":
        assert returned[0]["sn"] == "FACET-A"
        assert returned[0]["report_count"] == 2
        assert returned[0]["unconfirmed_count"] == 2
    elif confirmation == "confirmed":
        assert returned[0]["sn"] == "FACET-B"


def test_query_filters_facet_counts_but_keeps_zero_count_models(categorized_evidence):
    _, service = categorized_evidence
    result = service.list_devices(q="cohort-red", product="P50M", confirmation="confirmed")
    assert result["devices"] == []
    assert result["total"] == 0
    assert result["facets"]["all"] == counts(2, 2, 0)
    assert result["facets"]["confirmation"] == counts(1, 1, 0)
    assert product_counts(result) == {
        "P50M": counts(1, 1, 0), "P1000M": counts(1, 1, 0), "P50S": counts(0, 0, 0),
    }
    empty = service.list_devices(q="no-such-device-or-symptom")
    assert empty["facets"]["all"] == counts(0, 0, 0)
    assert empty["facets"]["confirmation"] == counts(0, 0, 0)
    assert product_counts(empty) == {product: counts(0, 0, 0) for product in ("P50M", "P1000M", "P50S")}


def test_search_matches_summary_after_display_limit_without_expanding_device_summary(evidence):
    root, _, service = evidence
    visible = [f"Synthetic failure {number}" for number in range(10)]
    tail = "TailOnly-PressureLoss 尾部压差异常"
    write_bundle(root, bundle(failure_details=[*visible, tail]))
    service.scan()

    for query in (" tailonly-pressureloss ", "尾部压差异常"):
        result = service.list_devices(q=query)
        assert result["total"] == 1
        assert result["devices"][0]["summary"] == visible
        assert result["facets"]["all"] == counts(1, 1, 0)
        assert result["facets"]["confirmation"] == counts(1, 1, 0)


def test_search_includes_older_reports_and_preserves_confirmation_history_after_restart(evidence):
    root, database_path, service = evidence
    newest = write_device_report(root, serial="SEARCH-HISTORY", product="P50M", name="search-new")
    payload = json.loads(newest.read_text())
    payload["failure_details"] = [f"Latest failure {number}" for number in range(10)]
    newest.write_text(json.dumps(payload), encoding="utf-8")
    write_device_report(root, serial="SEARCH-HISTORY", product="P50M", name="search-old",
                        report_run_id="run-26-10-28-03-16-26", test_time="2026-10-28T03:16:26Z",
                        description="HistoricalOnly-EncoderOffset")
    service.scan()
    device = only_device(service)
    first = confirm(service, device, text="第一轮确认", author="alice")
    second = confirm(service, first["device"], text="补充复测确认", author="bob")
    before_history = service.list_confirmations(device["id"])
    before_reports = [(item["id"], item["revision"]) for item in second["device"]["reports"]]
    restarted = FailureService(root, database_path, stable_seconds=0)

    for current in (service, restarted):
        result = current.list_devices(q="historicalonly-encoderoffset", confirmation="confirmed")
        assert result["total"] == 1
        found = result["devices"][0]
        assert found["report_count"] == 2
        assert found["summary"] == payload["failure_details"]
        assert found["version"] == second["device"]["version"]
        assert found["confirmation"] == second["confirmation"]
        assert [(item["id"], item["revision"]) for item in found["reports"]] == before_reports
        assert current.list_confirmations(device["id"]) == before_history
        assert len(before_history["items"]) == 2


@pytest.mark.parametrize("field", ["failure_reasons", "error_codes"])
def test_search_matches_failed_row_fields_absent_from_summary(evidence, field):
    root, _, service = evidence
    failure = row()
    token = "ROW_ONLY_SENSOR_OFFSET"
    failure[field] = [token]
    write_bundle(root, bundle(report_rows=[failure], failure_details=["Generic failure summary"]))
    service.scan()

    result = service.list_devices(q=token.lower())
    assert result["total"] == 1
    assert result["devices"][0]["summary"] == ["Generic failure summary"]
    assert token not in json.dumps(result)
    report = service.get_report(result["devices"][0]["reports"][0]["id"])
    assert report["failures"][0][field] == [token]


@pytest.mark.parametrize("result", ["PASS", "unknown"])
def test_search_does_not_match_nonfailed_rows(evidence, result):
    root, _, service = evidence
    token = "NONFAIL_ONLY_SENTINEL"
    nonfailure = row(token, result=result)
    nonfailure.update(failure_reasons=[token], error_codes=[token], data=[token, result])
    write_bundle(root, bundle(report_rows=[row(), nonfailure], failure_details=["Generic failure summary"]))
    service.scan()

    assert len(only_report(service)["failures"]) == 1
    searched = service.list_devices(q=token)
    assert searched["devices"] == []
    assert searched["total"] == 0
    assert searched["facets"]["all"] == counts(0, 0, 0)
    assert product_counts(searched) == {"P1000M": counts(0, 0, 0)}


@pytest.mark.parametrize("source", ["last_failure", "execution_error", "blocked_test"])
def test_search_includes_failure_trace_evidence_absent_from_summary(evidence, source):
    root, _, service = evidence
    token = "TRACE_ONLY_ALIGNMENT_FAILURE"
    payload = bundle(failure_details=["Generic failure summary"])
    if source == "last_failure":
        payload["trace"]["last_failure"] = {"action": "move", "error": token}
    elif source == "execution_error":
        payload["trace"]["tests"]["ENCODER"] = {"status": "execution_error", "error": token}
    else:
        payload["trace"]["tests"]["LIQUID"] = {
            "status": "not_run_due_to_previous_failure", "blocking_stage": token,
        }
    write_bundle(root, payload)
    service.scan()

    result = service.list_devices(q=token.lower())
    assert result["total"] == 1
    assert result["devices"][0]["summary"] == ["Generic failure summary"]
    assert token not in json.dumps(result)


def test_search_does_not_treat_passed_test_handled_exception_as_failure(evidence):
    root, _, service = evidence
    token = "EXPECTED_HANDLED_TIP_EXCEPTION"
    payload = bundle(failure_details=["Generic pressure failure"])
    payload["trace"]["tests"]["TIP-SENSOR"] = {
        "status": "passed", "error": token,
        "last_handled_exception": {"action": "verify_tip_presence", "error": token},
    }
    write_bundle(root, payload)
    service.scan()

    assert service.list_devices(q=token)["total"] == 0
    assert service.list_devices(q="Generic pressure failure")["total"] == 1


@pytest.mark.parametrize("status", ["failed", "execution_error", "exception", "passed"])
def test_search_indexes_nested_handled_exception_only_for_failed_tests(evidence, status):
    root, _, service = evidence
    token = "NESTED_ONLY_ALIGNMENT_EXCEPTION"
    payload = bundle(failure_details=["Generic pressure failure"])
    payload["trace"]["tests"]["TIP-SENSOR"] = {
        "status": status,
        "last_handled_exception": {"action": "verify_tip_presence", "error": token},
    }
    write_bundle(root, payload)
    service.scan()

    report = only_report(service)
    assert report["tests"]["TIP-SENSOR"]["last_handled_exception"]["error"] == token
    response = service.list_devices(q=token.lower())
    assert response["total"] == (0 if status == "passed" else 1)
    assert token not in json.dumps(response)
    if response["devices"]:
        assert response["devices"][0]["summary"] == ["Generic pressure failure"]


def test_full_failure_search_applies_before_device_facets_and_pagination(evidence):
    root, _, service = evidence
    token = "DeepSearchCohort"
    for serial, product, name in (("SEARCH-A", "P50M", "search-a-new"),
                                  ("SEARCH-A", "P50M", "search-a-old"),
                                  ("SEARCH-B", "P1000M", "search-b"),
                                  ("SEARCH-C", "P50S", "search-c")):
        path = write_device_report(root, serial=serial, product=product, name=name)
        if serial != "SEARCH-C":
            payload = json.loads(path.read_text())
            payload["failure_details"] = [f"Display failure {number}" for number in range(10)] + [token]
            path.write_text(json.dumps(payload), encoding="utf-8")
    service.scan()
    confirmed = next(item for item in service.list_devices()["devices"] if item["sn"] == "SEARCH-B")
    confirm(service, confirmed)
    pages = [service.list_devices(q=token, page=page, page_size=1) for page in (1, 2)]
    expected_products = {"P50M": counts(1, 1, 0), "P1000M": counts(1, 0, 1), "P50S": counts(0, 0, 0)}

    for response in pages:
        assert response["total"] == 2
        assert len(response["devices"]) == 1
        assert response["summary"]["reports"] == 3
        assert response["facets"]["all"] == counts(2, 1, 1)
        assert response["facets"]["confirmation"] == counts(2, 1, 1)
        assert product_counts(response) == expected_products
    assert {item["sn"] for response in pages for item in response["devices"]} == {"SEARCH-A", "SEARCH-B"}
    filtered = service.list_devices(q=token, product="P50M", confirmation="confirmed", page_size=1)
    assert filtered["devices"] == []
    assert filtered["total"] == 0
    assert filtered["facets"]["all"] == counts(2, 1, 1)
    assert filtered["facets"]["confirmation"] == counts(1, 1, 0)
    assert product_counts(filtered) == expected_products


def test_date_mode_and_failure_kind_facets_require_one_matching_report(categorized_evidence):
    _, service = categorized_evidence
    result = service.list_devices(date_from="2026-10-29", date_to="2026-10-29", mode="assembly_qc", kind="test_failure")
    assert {device["sn"] for device in result["devices"]} == {"FACET-A", "FACET-B"}
    assert result["facets"]["all"] == counts(2, 1, 1)
    assert result["facets"]["confirmation"] == counts(2, 1, 1)
    assert product_counts(result) == {
        "P50M": counts(2, 1, 1), "P1000M": counts(0, 0, 0), "P50S": counts(0, 0, 0),
    }
    # A has an Oct 29 report and a volume/runtime report on Oct 28. These must not
    # jointly satisfy a filter that requires all three fields on one report.
    no_match = service.list_devices(date_from="2026-10-29", date_to="2026-10-29", mode="volume_qc", kind="runtime_error")
    assert no_match["total"] == 0
    assert no_match["facets"]["all"] == counts(0, 0, 0)
    assert all(value == counts(0, 0, 0) for value in product_counts(no_match).values())


def test_confirmation_and_new_failure_move_facet_counts_without_double_counting_device(categorized_evidence):
    root, service = categorized_evidence
    device = next(device for device in service.list_devices()["devices"] if device["sn"] == "FACET-A")
    confirm(service, device)
    confirmed = service.list_devices(product="P50M", confirmation="pending")
    assert confirmed["devices"] == []
    assert confirmed["facets"]["all"] == counts(4, 1, 3)
    assert confirmed["facets"]["confirmation"] == counts(2, 0, 2)
    assert product_counts(confirmed)["P50M"] == counts(2, 0, 2)
    write_device_report(root, serial="FACET-A", product="p50_multi_flex", name="a-later",
                        report_run_id="run-26-10-29-05-16-26", test_time="2026-10-29T05:16:26Z")
    service.scan()
    reopened = service.list_devices(product="P50M", confirmation="pending")
    assert reopened["total"] == 1
    assert reopened["devices"][0]["sn"] == "FACET-A"
    assert reopened["devices"][0]["report_count"] == 3
    assert reopened["devices"][0]["unconfirmed_count"] == 1
    assert reopened["facets"]["all"] == counts(4, 2, 2)
    assert reopened["facets"]["confirmation"] == counts(2, 1, 1)
    assert product_counts(reopened)["P50M"] == counts(2, 1, 1)


@pytest.mark.parametrize(("alias", "expected"), [
    ("p50_single_flex", "P50S"),
    ("p50_multi_flex", "P50M"),
    ("p1000_single_flex", "P1000S"),
    ("p1000_multi_flex", "P1000M"),
    ("FLEX_8CHANNEL_50", "P50M"),
    ("flex_96channel_200", "P200-96"),
    ("flex_96channel_1000", "P1000-96"),
    ("custom_lab_pipette", "custom_lab_pipette"),
])
def test_product_aliases_normalize_consistently_in_labels_filters_and_facets(evidence, alias, expected):
    root, _, service = evidence
    write_device_report(root, serial="ALIAS-ONLY", product=alias, name="alias")
    service.scan()
    for product_filter in (alias, expected):
        result = service.list_devices(product=product_filter)
        assert result["total"] == 1
        assert result["devices"][0]["product"] == expected
        assert result["options"]["products"] == [expected]
        assert product_counts(result) == {expected: counts(1, 1, 0)}
        assert result["facets"]["confirmation"] == counts(1, 1, 0)
        assert service.get_report(result["devices"][0]["reports"][0]["id"])["product"] == expected


def test_cached_product_aliases_merge_immediately_without_changing_identity_or_confirmation(evidence):
    root, database_path, service = evidence
    write_device_report(root, serial="CACHE-A", product="flex_8channel_50", name="cache-a")
    write_device_report(root, serial="CACHE-B", product="flex_8channel_50", name="cache-b")
    service.scan()
    for device in service.list_devices()["devices"]:
        confirm(service, device)
    before = {device["sn"]: device for device in service.list_devices()["devices"]}
    with sqlite3.connect(database_path) as connection:
        records = connection.execute("SELECT id,payload FROM failure_reports ORDER BY id").fetchall()
        for (report_id, serialized), alias in zip(records, ("p50_multi_flex", "flex_8channel_50")):
            payload = json.loads(serialized)
            payload["product"] = alias
            connection.execute("UPDATE failure_reports SET payload=? WHERE id=?", (json.dumps(payload), report_id))
        original_stored_payloads = connection.execute("SELECT id,payload FROM failure_reports ORDER BY id").fetchall()
    # A newly deployed reader must normalize the existing index without relying
    # on a rescan: unchanged upload signatures would otherwise skip these rows.
    restarted = FailureService(root, database_path, stable_seconds=0)
    for product_filter in ("P50M", "p50_multi_flex", "flex_8channel_50"):
        result = restarted.list_devices(product=product_filter, confirmation="confirmed")
        assert result["total"] == 2
        assert result["options"]["products"] == ["P50M"]
        assert product_counts(result) == {"P50M": counts(2, 0, 2)}
        assert result["facets"]["confirmation"] == counts(2, 0, 2)
        for device in result["devices"]:
            previous = before[device["sn"]]
            assert device["product"] == "P50M"
            assert device["id"] == previous["id"]
            assert device["version"] == previous["version"]
            assert device["reports"] == previous["reports"]
            assert device["confirmation"] == previous["confirmation"]
            assert device["unconfirmed_count"] == 0
            report = restarted.get_report(device["reports"][0]["id"])
            assert report["product"] == "P50M"
            assert report["revision"] == previous["reports"][0]["revision"]
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT id,payload FROM failure_reports ORDER BY id").fetchall() == original_stored_payloads


def test_explicit_failures_keep_measurements_and_ignore_unknown_or_unrecorded_rows(evidence):
    root, _, service = evidence
    payload = bundle(report_rows=[
        row(), row("pressure-curve", result="unknown"),
        row("not-started", result="unknown", recorded=False),
        row("passed-check", result="PASS"),
    ])
    write_bundle(root, payload)
    service.scan()
    report = only_report(service)
    assert len(report["failures"]) == 1
    failure = report["failures"][0]
    assert failure["evidence_id"] == "FIXTURE/pressure-check[0]"
    assert failure["data"] == [3.5, "FAIL"]
    assert failure["error_codes"] == ["PRESSURE_VALUE_OUT_OF_RANGE"]
    assert report["failure_count"] == 1
    assert report["runtime_error"] is None
    preview = service.preview_attachment(report["id"], "json")
    original_rows = json.loads(preview["text"])["report_rows"]
    assert original_rows[1]["result"] == "unknown"
    assert original_rows[2]["record_status"] == "not_recorded"
    assert len(service.list_devices()["devices"]) == 1  # RIGHT is a reference pipette.


def test_skipped_unexecuted_and_handled_exceptions_do_not_become_runtime_failures(evidence):
    root, _, service = evidence
    payload = bundle()
    payload["trace"]["tests"] = {
        "FIXTURE": {"status": "failed"},
        "LIQUID": {"status": "not_run_due_to_previous_failure"},
        "ENVIRONMENT": {"status": "skipped"},
        "TIP": {"status": "passed", "last_handled_exception": {"action": "tip-state", "error": "ExpectedTipError"}},
    }
    write_bundle(root, payload)
    service.scan()
    report = only_report(service)
    assert len(report["failures"]) == 1
    assert report["runtime_error"] is None
    assert report["last_failure"] is None
    assert report["tests"]["LIQUID"]["status"] == "not_run_due_to_previous_failure"
    assert report["tests"]["ENVIRONMENT"]["status"] == "skipped"
    assert report["tests"]["TIP"]["last_handled_exception"]["error"] == "ExpectedTipError"


def test_runtime_abort_without_any_fail_row_is_still_reviewable(evidence):
    root, _, service = evidence
    payload = bundle(
        report_rows=[row("not-started", result="unknown", recorded=False)],
        stage="diagnostics",
        runtime_error={"type": "RuntimeError", "message": "Synthetic diagnostic abort"},
        failure_details=["[QC_RUNTIME_ERROR] RuntimeError: Synthetic diagnostic abort"],
    )
    payload["trace"]["last_failure"] = {"action": "home", "error": "Synthetic diagnostic abort"}
    payload["trace"]["tests"] = {
        "DIAGNOSTICS": {"status": "execution_error", "error": "Synthetic diagnostic abort"},
        "LIQUID": {"status": "not_run_due_to_previous_failure"},
    }
    write_bundle(root, payload)
    service.scan()
    device = only_device(service)
    report = only_report(service)
    assert device["unconfirmed_count"] == 1
    assert report["failures"] == []
    assert report["kind"] == "runtime_error"
    assert report["runtime_error"]["type"] == "RuntimeError"
    assert report["last_failure"]["action"] == "home"


def test_repeated_scan_is_idempotent_and_changed_failure_reopens_confirmation(evidence):
    root, _, service = evidence
    payload = bundle()
    path = write_bundle(root, payload)
    service.scan()
    report = only_report(service)
    confirm(service, only_device(service))
    confirmed = only_device(service)
    for _ in range(2):
        service.scan()
        assert only_device(service)["version"] == confirmed["version"]
        assert only_device(service)["unconfirmed_count"] == 0
        assert only_report(service)["revision"] == report["revision"]
    payload["report_rows"][0]["data"][0] = 7.25
    path.write_text(json.dumps(payload), encoding="utf-8")
    service.scan()
    changed = only_report(service)
    assert changed["id"] == report["id"]
    assert changed["revision"] != report["revision"]
    assert only_device(service)["unconfirmed_count"] == 1
    assert len(service.list_confirmations(confirmed["id"])["items"]) == 1


def test_rescan_detects_same_stat_json_changes_without_losing_confirmation_history(evidence):
    root, _, service = evidence
    payload = bundle()
    path = write_bundle(root, payload)
    service.scan()
    original = only_report(service)
    confirm(service, only_device(service))
    payload["report_rows"][0]["data"][0] = 4.5
    rewrite_json_preserving_stat(path, payload)
    service.scan()
    updated = only_report(service)
    assert updated["id"] == original["id"]
    assert updated["revision"] != original["revision"]
    assert updated["failures"][0]["data"] == [4.5, "FAIL"]
    assert only_device(service)["unconfirmed_count"] == 1
    assert len(service.list_confirmations(only_device(service)["id"])["items"]) == 1


def test_same_stat_json_metadata_change_preserves_existing_confirmation(evidence):
    root, _, service = evidence
    payload = bundle()
    path = write_bundle(root, payload)
    service.scan()
    original = only_report(service)
    confirm(service, only_device(service))
    confirmed = only_device(service)
    payload["created_at_utc"] = "2026-10-29T03:16:27Z"
    rewrite_json_preserving_stat(path, payload)
    service.scan()
    assert only_report(service)["revision"] == original["revision"]
    assert only_device(service)["version"] == confirmed["version"]
    assert only_device(service)["confirmation"] == confirmed["confirmation"]
    assert only_device(service)["unconfirmed_count"] == 0


@pytest.mark.parametrize("removed_kind", ["log", "encoder"])
def test_rescan_removes_deleted_optional_attachment_without_reopening_confirmation(evidence, removed_kind):
    root, _, service = evidence
    source = write_bundle(root)
    attachments = {
        "log": source.with_suffix(".log"),
        "encoder": source.with_suffix(".encoder.csv"),
    }
    attachments["log"].write_text("Synthetic original log", encoding="utf-8")
    attachments["encoder"].write_text("cycle,position\n1,42\n", encoding="utf-8")
    service.scan()
    original = only_report(service)
    confirm(service, only_device(service))
    confirmed = only_device(service)
    attachments[removed_kind].unlink()
    service.scan()
    report = only_report(service)
    stored = service.repository.get_report(report["id"])
    assert removed_kind not in stored["attachment_paths"]
    assert removed_kind not in stored["attachment_signatures"]
    assert removed_kind not in stored.get("attachment_hashes", {})
    assert {item["kind"] for item in report["attachments"] if item["available"]} == {"json", "log", "encoder"} - {removed_kind}
    assert report["revision"] == original["revision"]
    assert only_device(service)["version"] == confirmed["version"]
    assert only_device(service)["unconfirmed_count"] == 0
    with pytest.raises(NotFoundError):
        service.preview_attachment(report["id"], removed_kind)


@pytest.mark.parametrize("change", [{"mode": "volume_qc"}, {"report_run_id": "run-26-10-29-03-19-26"}])
def test_shared_trace_run_with_distinct_mode_or_report_is_not_merged(evidence, change):
    root, _, service = evidence
    write_bundle(root, bundle(), name="first")
    write_bundle(root, bundle(**change), name="second")
    service.scan()
    device = only_device(service)
    assert len(device["reports"]) == 2
    assert len({value["id"] for value in device["reports"]}) == 2
    assert device["unconfirmed_count"] == 2


def test_reused_filename_for_a_new_run_preserves_history_and_requires_confirmation(evidence):
    root, _, service = evidence
    path = write_bundle(root)
    service.scan()
    previous = only_report(service)
    confirm(service, only_device(service))
    path.write_text(json.dumps(bundle(run_id="replacement-run", report_run_id="run-26-10-29-05-16-26")), encoding="utf-8")
    service.scan()
    device = only_device(service)
    assert device["report_count"] == 2
    assert device["unconfirmed_count"] == 1
    assert previous["id"] in {report["id"] for report in device["reports"]}
    assert len(service.list_confirmations(device["id"])["items"]) == 1
    assert not any(item["available"] for item in service.get_report(previous["id"])["attachments"])
    with pytest.raises(NotFoundError):
        service.preview_attachment(previous["id"], "json")


def test_log_arriving_before_json_is_upgraded_without_duplicate_report(evidence):
    root, _, service = evidence
    payload = bundle()
    path = root / SERIAL / "20261029T031626Z" / "qc.log"
    path.parent.mkdir(parents=True)
    path.write_text(readable_log(payload), encoding="utf-8")
    service.scan()
    first = only_report(service)
    assert len(first["failures"]) == 1
    write_bundle(root, payload)
    service.scan()
    upgraded = only_report(service)
    assert upgraded["id"] == first["id"]
    assert upgraded["source_format"] == "json"
    assert {item["kind"] for item in upgraded["attachments"] if item["available"]} >= {"json", "log"}


def test_optional_encoder_and_self_upload_status_do_not_invalidate_confirmation(evidence):
    root, _, service = evidence
    payload = bundle()
    path = write_bundle(root, payload)
    service.scan()
    initial = only_report(service)
    assert next(item for item in initial["attachments"] if item["kind"] == "json")["available"] is True
    assert not any(item["kind"] == "encoder" and item["available"] for item in initial["attachments"])
    confirm(service, only_device(service))
    confirmed = only_device(service)
    payload["created_at_utc"] = "2026-10-29T03:18:00Z"
    payload["artifacts"][0]["upload_status"] = "uploaded"
    payload["artifacts"].append({"role": "encoder_csv", "path": "/robot/encoder.csv", "upload_status": "uploaded"})
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.with_suffix(".encoder.csv").write_text("cycle,position\n1,42\n2,43\n", encoding="utf-8")
    service.scan()
    updated = only_report(service)
    assert updated["revision"] == initial["revision"]
    assert only_device(service)["version"] == confirmed["version"]
    assert only_device(service)["unconfirmed_count"] == 0
    preview = service.preview_attachment(updated["id"], "encoder")
    assert preview["columns"] == ["cycle", "position"]
    assert preview["rows"] == [["1", "42"], ["2", "43"]]


def test_confirmations_survive_restart_and_cover_only_existing_failure_evidence(evidence):
    root, database_path, service = evidence
    write_bundle(root)
    service.scan()
    first = only_device(service)
    confirm(service, first, text="检查气路后复测", author="alice")
    restarted = FailureService(root, database_path, stable_seconds=0)
    restarted.scan()
    current = only_device(restarted)
    assert current["unconfirmed_count"] == 0
    history = restarted.list_confirmations(first["id"])["items"]
    assert len(history) == 1
    assert history[0]["text"] == "检查气路后复测"
    assert history[0]["created_by"] == "alice"
    write_bundle(root, bundle(run_id="new-trace", report_run_id="run-26-10-29-04-16-26"), name="new-run")
    restarted.scan()
    assert only_device(restarted)["unconfirmed_count"] == 1
    assert len(restarted.list_confirmations(first["id"])["items"]) == 1


def test_concurrent_confirmations_allow_one_writer_and_keep_audit_history(evidence):
    root, database_path, service = evidence
    write_bundle(root)
    service.scan()
    before = only_device(service)
    second_service = FailureService(root, database_path, stable_seconds=0)

    def attempt(pair):
        instance, username = pair
        try:
            confirm(instance, before, author=username)
            return "saved"
        except ConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, [(service, "alice"), (second_service, "bob")]))
    assert sorted(outcomes) == ["conflict", "saved"]
    assert len(service.list_confirmations(before["id"])["items"]) == 1


def test_missing_directory_and_corrupt_manifest_do_not_crash_other_reports(tmp_path):
    root = tmp_path / "not-mounted"
    service = FailureService(root, tmp_path / "failures.sqlite3", stable_seconds=0)
    status = service.scan()
    assert status["error"]
    assert service.list_devices()["devices"] == []
    path = write_bundle(root)
    path.with_name("broken.json").write_text('{"schema_version": 1,', encoding="utf-8")
    path.with_name("invalid.json").write_text("[]", encoding="utf-8")
    status = service.scan()
    assert status["parse_errors"] == 2
    assert len(only_report(service)["failures"]) == 1
    path.unlink()
    service.scan()
    if service.list_devices()["devices"]:
        report = only_report(service)
        assert not any(item["kind"] == "json" and item["available"] for item in report["attachments"])


def test_incomplete_upload_waits_for_file_stability_then_indexes_once(evidence):
    root, database_path, _ = evidence
    service = FailureService(root, database_path, stable_seconds=2)
    path = write_bundle(root)
    status = service.scan()
    assert status["pending_files"] == 1
    assert service.list_devices()["devices"] == []
    older = time.time() - 10
    os.utime(path, (older, older))
    service.scan()
    first = only_report(service)
    service.scan()
    assert only_report(service)["id"] == first["id"]


def test_encoder_becomes_available_when_stable_without_another_file_change(evidence, monkeypatch):
    root, database_path, _ = evidence
    service = FailureService(root, database_path, stable_seconds=2)
    path = write_bundle(root)
    encoder = path.with_suffix(".encoder.csv")
    encoder.write_text("cycle,position\n1,42\n", encoding="utf-8")
    now = time.time()
    os.utime(path, (now - 10, now - 10))
    os.utime(encoder, (now, now))
    original_stat = encoder.stat()
    monkeypatch.setattr(scanner.time, "time", lambda: now)
    first_scan = service.scan()
    initial = only_report(service)
    assert first_scan["pending_files"] == 1
    assert next(item for item in initial["attachments"] if item["kind"] == "json")["available"] is True
    assert not next(item for item in initial["attachments"] if item["kind"] == "encoder")["available"]
    confirm(service, only_device(service))
    monkeypatch.setattr(scanner.time, "time", lambda: now + 3)
    second_scan = service.scan()
    current = only_report(service)
    assert second_scan["pending_files"] == 0
    assert next(item for item in current["attachments"] if item["kind"] == "encoder")["available"] is True
    assert service.preview_attachment(current["id"], "encoder")["rows"] == [["1", "42"]]
    assert current["id"] == initial["id"]
    assert current["revision"] == initial["revision"]
    assert only_device(service)["unconfirmed_count"] == 0
    assert encoder.stat().st_mtime_ns == original_stat.st_mtime_ns
    assert encoder.stat().st_size == original_stat.st_size


def test_unchanged_incomplete_evidence_remains_visible_as_a_scan_error(evidence):
    root, _, service = evidence
    payload = bundle(report_rows=[row("unrecorded", result="unknown", recorded=False)], failure_details=[])
    payload["trace"]["tests"] = {"FIXTURE": {"status": "unknown"}}
    write_bundle(root, payload)
    first = service.scan()
    report = only_report(service)
    assert report["parse_status"] == "incomplete"
    assert report["failure_count"] == 0
    assert first["parse_errors"] == 1
    for _ in range(2):
        current = service.scan()
        assert current["parse_errors"] == 1
        assert current["errors"]
        assert only_report(service)["id"] == report["id"]
        assert only_report(service)["parse_status"] == "incomplete"


@pytest.mark.parametrize("with_log", [False, True])
def test_unknown_schema_is_reported_as_an_error_instead_of_ready(evidence, with_log):
    root, _, service = evidence
    payload = bundle(schema_version=999)
    path = write_bundle(root, payload)
    if with_log:
        path.with_suffix(".log").write_text(readable_log(payload), encoding="utf-8")
    for _ in range(2):
        status = service.scan()
        assert status["parse_errors"] >= 1
        assert any("schema_version" in error["message"] for error in status["errors"])
        if with_log:
            report = only_report(service)
            assert report["source_format"] == "log"
            assert report["parse_status"] != "ready"
        else:
            assert service.list_devices()["devices"] == []


def test_corrupt_replacement_preserves_previously_indexed_evidence_and_confirmation(evidence):
    root, _, service = evidence
    path = write_bundle(root)
    service.scan()
    original = only_report(service)
    confirm(service, only_device(service))
    path.write_text('{"schema_version":1,', encoding="utf-8")
    status = service.scan()
    assert status["parse_errors"] == 1
    assert only_report(service)["revision"] == original["revision"]
    assert only_device(service)["unconfirmed_count"] == 0


def test_manifest_artifact_paths_cannot_escape_the_evidence_directory(evidence, tmp_path):
    root, _, service = evidence
    outside = tmp_path / "outside.log"
    outside.write_text("SENSITIVE-OUTSIDE-TEST-CONTENT", encoding="utf-8")
    payload = bundle(artifacts=[
        {"role": "readable_log", "path": str(outside), "upload_status": "uploaded"},
        {"role": "encoder_csv", "path": "../../../outside.log", "upload_status": "uploaded"},
    ])
    write_bundle(root, payload)
    service.scan()
    report = only_report(service)
    for kind in ("log", "encoder"):
        with pytest.raises((NotFoundError, ValueError)):
            service.preview_attachment(report["id"], kind)


def test_symlinked_source_files_and_attachment_replacements_are_rejected(evidence, tmp_path):
    root, _, service = evidence
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(bundle()), encoding="utf-8")
    (root / "linked.json").symlink_to(outside)
    service.scan()
    assert service.list_devices()["devices"] == []
    path = write_bundle(root)
    log = path.with_suffix(".log")
    log.write_text("Safe original evidence", encoding="utf-8")
    service.scan()
    report = only_report(service)
    assert service.preview_attachment(report["id"], "log")["text"] == "Safe original evidence"
    log.unlink()
    log.symlink_to(outside)
    with pytest.raises((NotFoundError, ValueError)):
        service.preview_attachment(report["id"], "log")


@pytest.fixture
def api(evidence, tmp_path):
    root, _, service = evidence
    write_bundle(root)
    service.scan()
    auth = AuthService(
        db_path=tmp_path / "auth.sqlite3", jwt_secret="test-secret-" * 4,
        issuer="test", audience="test", access_token_minutes=5, refresh_token_hours=1,
    )
    auth.initialize()
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[routes.get_service] = lambda: service
    with TestClient(app) as client:
        yield client, auth, service


def session_for(auth, username="alice", role="operator"):
    user = auth.create_user(
        username=username, password="synthetic-test-password-long-enough",
        display_name=username.title(), role=role,
    )
    return user, auth.issue_session(user, user_agent="pytest", ip_address="127.0.0.1")


def bearer(session):
    return {"Authorization": "Bearer " + session.access_token}


def test_anonymous_cannot_read_evidence_or_write_confirmation(api):
    client, _, service = api
    device = only_device(service)
    report = only_report(service)
    for endpoint in (
        "/devices", f"/reports/{report['id']}",
        f"/reports/{report['id']}/attachments/json/preview",
        f"/reports/{report['id']}/attachments/json",
        f"/devices/{device['id']}/confirmations",
    ):
        assert client.get(PREFIX + endpoint).status_code == 401
    assert client.post(PREFIX + "/scan").status_code == 401
    assert client.post(PREFIX + f"/devices/{device['id']}/confirmations", json={
        "text": "确认", "version": device["version"],
    }).status_code == 401


def test_cookie_confirmation_requires_matching_csrf(api):
    client, auth, service = api
    _, session = session_for(auth)
    client.cookies.set(ACCESS_COOKIE_NAME, session.access_token)
    client.cookies.set(CSRF_COOKIE_NAME, session.csrf_token)
    device = only_device(service)
    endpoint = PREFIX + f"/devices/{device['id']}/confirmations"
    body = {"text": "复测已完成", "version": device["version"]}
    assert client.get(PREFIX + "/devices").status_code == 200
    assert client.post(endpoint, json=body).status_code == 403
    assert client.post(endpoint, json=body, headers={"X-CSRF-Token": "incorrect"}).status_code == 403
    assert service.list_confirmations(device["id"])["items"] == []
    response = client.post(endpoint, json=body, headers={"X-CSRF-Token": session.csrf_token})
    assert response.status_code == 201, response.text


def test_viewer_can_read_but_cannot_scan_or_confirm(api):
    client, auth, service = api
    _, session = session_for(auth, username="viewer", role="viewer")
    headers = bearer(session)
    device = only_device(service)
    report = only_report(service)
    assert client.get(PREFIX + "/devices", headers=headers).status_code == 200
    assert client.get(PREFIX + f"/reports/{report['id']}", headers=headers).status_code == 200
    assert client.post(PREFIX + "/scan", headers=headers).status_code == 403
    assert client.post(PREFIX + f"/devices/{device['id']}/confirmations", headers=headers, json={
        "text": "Attempted viewer confirmation", "version": device["version"],
    }).status_code == 403
    assert service.list_confirmations(device["id"])["items"] == []


def test_report_links_use_server_identity_and_preserve_report_confirmation(api):
    client, auth, service = api
    calls = []

    class Links:
        def lookup(self, report, force=False):
            calls.append((report["sn"], report["report_run_id"], force))
            return {"status": "running", "sn": report["sn"], "report_run_id": report["report_run_id"],
                    "matches": [], "checked_at": None, "stale": False, "error_code": None}

    client.app.dependency_overrides[routes.get_report_link_service] = Links
    report = only_report(service)
    endpoint = PREFIX + f"/reports/{report['id']}/report-link"
    assert client.get(endpoint).status_code == 401
    assert client.post(endpoint).status_code == 401
    _, viewer_session = session_for(auth, username="links-viewer", role="viewer")
    assert client.get(endpoint, headers=bearer(viewer_session)).status_code == 200
    assert client.post(endpoint, headers=bearer(viewer_session)).status_code == 403
    _, editor_session = session_for(auth, username="links-editor")
    device = only_device(service)
    service.confirm_device(device["id"], "Keep original repair confirmation", device["version"], "editor")
    before = only_device(service)
    assert client.post(endpoint, headers=bearer(editor_session), json={"sn": "WRONG", "report_run_id": "WRONG"}).status_code == 202
    assert calls == [(SERIAL, REPORT_RUN_ID, False), (SERIAL, REPORT_RUN_ID, True)]
    assert only_device(service) == before
    assert only_report(service)["revision"] == report["revision"]
    assert before["reports"][0]["sn"] == SERIAL
    assert before["reports"][0]["report_run_id"] == REPORT_RUN_ID
    assert client.get(PREFIX + "/reports/unknown/report-link", headers=bearer(editor_session)).status_code == 404
    client.cookies.set(ACCESS_COOKIE_NAME, editor_session.access_token)
    client.cookies.set(CSRF_COOKIE_NAME, editor_session.csrf_token)
    assert client.post(endpoint).status_code == 403
    assert client.post(endpoint, headers={"X-CSRF-Token": editor_session.csrf_token}).status_code == 202


def test_confirmation_is_shared_auditable_and_stale_version_returns_409(api):
    client, auth, service = api
    alice, alice_session = session_for(auth, "alice")
    bob, bob_session = session_for(auth, "bob")
    before = only_device(service)
    endpoint = PREFIX + f"/devices/{before['id']}/confirmations"
    body = {"text": "Alice 已确认压力失败", "version": before["version"]}
    saved = client.post(endpoint, json=body, headers=bearer(alice_session))
    assert saved.status_code == 201, saved.text
    shared = client.get(endpoint, headers=bearer(bob_session))
    assert shared.status_code == 200
    history = shared.json()["items"]
    assert len(history) == 1
    assert history[0]["text"] == body["text"]
    assert history[0]["created_by"] in {alice.id, alice.username}
    assert history[0]["created_by_name"] == "Alice"
    assert history[0]["created_at"]
    stale = client.post(endpoint, json=body | {"text": "Bob stale update"}, headers=bearer(bob_session))
    assert stale.status_code == 409, stale.text
    current = only_device(service)
    second = client.post(endpoint, json={"text": "Bob 补充复测说明", "version": current["version"]}, headers=bearer(bob_session))
    assert second.status_code == 201, second.text
    history = client.get(endpoint, headers=bearer(alice_session)).json()["items"]
    assert len(history) == 2
    assert {item["created_by"] for item in history} in ({alice.id, bob.id}, {alice.username, bob.username})
    assert {item["text"] for item in history} == {body["text"], "Bob 补充复测说明"}


@pytest.mark.parametrize("confirmation_count", [0, 1, 3])
def test_recent_confirmations_show_latest_two_and_preserve_full_history(api, evidence, monkeypatch, confirmation_count):
    client, auth, _ = api
    root, database_path, _ = evidence
    _, session = session_for(auth)
    headers = bearer(session)
    # Equal timestamps still use insertion order to put the latest note first.
    monkeypatch.setattr("modules.test_failures.repository.now", lambda: "2026-10-29T06:00:00+00:00")
    device = client.get(PREFIX + "/devices", headers=headers).json()["devices"][0]
    assert device["recent_confirmations"] == []
    assert device["confirmation"] is None
    endpoint = PREFIX + f"/devices/{device['id']}/confirmations"
    saved_records = []
    public_fields = {"id", "text", "created_by", "created_by_name", "created_at"}
    for index in range(confirmation_count):
        previous_version = device["version"]
        response = client.post(endpoint, headers=headers, json={
            "text": f"第 {index + 1} 次返修检查与复测记录", "version": previous_version,
        })
        assert response.status_code == 201, response.text
        saved = response.json()
        saved_records.append(saved["confirmation"])
        device = saved["device"]
        assert device["version"] != previous_version
        assert device["recent_confirmations"] == list(reversed(saved_records[-2:]))
        assert device["confirmation"] == saved_records[-1]
        assert device["unconfirmed_count"] == 0
        assert "_history" not in device
        assert all(set(record) == public_fields for record in device["recent_confirmations"])

    listed = client.get(PREFIX + "/devices", headers=headers).json()["devices"][0]
    assert listed == device
    assert listed["recent_confirmations"] == list(reversed(saved_records[-2:]))
    assert confirmation_text_records(client.get(endpoint, headers=headers).json()["items"]) == list(reversed(saved_records))
    restarted = FailureService(root, database_path, stable_seconds=0)
    assert only_device(restarted) == device
    assert confirmation_text_records(restarted.list_confirmations(device["id"])["items"]) == list(reversed(saved_records))

    if confirmation_count == 3:
        fourth = confirm(restarted, device, text="第 4 次补充返修记录", author="bob")
        assert fourth["device"]["recent_confirmations"] == [fourth["confirmation"], saved_records[-1]]
        assert fourth["device"]["confirmation"] == fourth["confirmation"]
        assert confirmation_text_records(restarted.list_confirmations(device["id"])["items"]) == [fourth["confirmation"], *reversed(saved_records)]


def test_search_does_not_expose_private_corpus_in_list_or_confirmation_response(api, evidence):
    client, auth, service = api
    root, _, _ = evidence
    token = "PRIVATE_SEARCH_ONLY_FAILURE_REASON"
    failure = row()
    failure["failure_reasons"] = [token]
    write_bundle(root, bundle(report_rows=[failure], failure_details=["Public compact summary"]))
    service.scan()
    _, session = session_for(auth)

    def assert_public(value):
        if isinstance(value, dict):
            assert all(not key.startswith("_") for key in value)
            for child in value.values():
                assert_public(child)
        elif isinstance(value, list):
            for child in value:
                assert_public(child)

    listed = client.get(PREFIX + "/devices", headers=bearer(session), params={"q": token})
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["total"] == 1
    assert_public(listed_body)
    assert token not in listed.text
    device = listed_body["devices"][0]
    endpoint = PREFIX + f"/devices/{device['id']}/confirmations"
    saved = client.post(endpoint, headers=bearer(session), json={"text": "复测已确认", "version": device["version"]})
    assert saved.status_code == 201
    saved_body = saved.json()
    assert_public(saved_body)
    assert token not in saved.text
    assert saved_body["device"]["unconfirmed_count"] == 0
    history = client.get(endpoint, headers=bearer(session)).json()
    assert confirmation_text_records(history["items"]) == [saved_body["confirmation"]]
    assert_public(history)
    assert token not in json.dumps(history)
    detail = client.get(PREFIX + f"/reports/{device['reports'][0]['id']}", headers=bearer(session))
    assert detail.status_code == 200
    assert detail.json()["failures"][0]["failure_reasons"] == [token]


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_confirmation_is_rejected_without_mutation(api, text):
    client, auth, service = api
    _, session = session_for(auth)
    device = only_device(service)
    response = client.post(PREFIX + f"/devices/{device['id']}/confirmations", headers=bearer(session), json={
        "text": text, "version": device["version"],
    })
    assert response.status_code in {400, 422}
    assert service.list_confirmations(device["id"])["items"] == []


def phase_bundle(volume=None):
    stage = f"right-reference-{volume}ul" if volume is not None else "result-summary"
    return bundle(stage=stage, report_rows=[row(f"evidence-{stage}")],
                  failure_details=[f"Distinct phase evidence: {stage}"])


def write_phase_bundle(root, volume=None, *, encoder=False):
    name = f"qc.right-reference-{volume}ul" if volume is not None else "qc"
    payload = phase_bundle(volume)
    path = write_bundle(root, payload, name=name)
    path.with_suffix(".log").write_text(readable_log(payload), encoding="utf-8")
    if encoder:
        path.with_suffix(".encoder.csv").write_text("cycle,position\n1,42\n", encoding="utf-8")
    return path


def reports_by_stage(service):
    return {report["stage"]: service.get_report(report["id"])
            for report in only_device(service)["reports"]}


def test_reference_checkpoints_are_distinct_packages_with_main_first(evidence):
    root, database_path, service = evidence
    for volume in (200, None, 50):
        write_phase_bundle(root, volume, encoder=volume is None)
    assert service.scan()["parse_errors"] == 0
    device = only_device(service)
    assert device["report_count"] == device["unconfirmed_count"] == 3
    assert [report["stage"] for report in device["reports"]] == [
        "result-summary", "right-reference-50ul", "right-reference-200ul",
    ]
    assert len({report["id"] for report in device["reports"]}) == 3
    assert len({report["run_group_id"] for report in device["reports"]}) == 1
    for summary in device["reports"]:
        report = service.get_report(summary["id"])
        assert report["run_group_id"] == summary["run_group_id"]
        assert report["report_role"] == ("main" if report["stage"] == "result-summary" else "right_reference")
        assert report["reference_tip_volume_ul"] == {"result-summary": None, "right-reference-50ul": 50, "right-reference-200ul": 200}[report["stage"]]
        assert report["failures"][0]["tag"] == "evidence-" + report["stage"]
        stored = service.repository.get_report(report["id"])
        stem = str(Path(stored["attachment_paths"]["json"]).with_suffix(""))
        assert stored["attachment_paths"]["log"] == stem + ".log"
        assert ("encoder" in stored["attachment_paths"]) == (report["report_role"] == "main")
    result = service.list_devices(q="right-reference-200ul", product="P1000M", page_size=1)
    assert result["total"] == 1
    assert result["summary"]["reports"] == 3
    assert result["facets"]["all"] == counts(1, 1, 0)
    confirmed = confirm(service, device)["device"]
    assert confirmed["unconfirmed_count"] == 0
    restarted = FailureService(root, database_path, stable_seconds=0)
    restarted.scan()
    assert only_device(restarted) == confirmed


@pytest.mark.parametrize("order", [(50, 200, None), (50, None, 200), (200, 50, None),
                                   (200, None, 50), (None, 50, 200), (None, 200, 50)])
def test_reference_upload_order_and_late_encoder_never_replace_final(evidence, order):
    root, _, service = evidence
    seen_ids = {}
    for volume in order:
        write_phase_bundle(root, volume)
        service.scan()
        reports = reports_by_stage(service)
        assert len(reports) == len(seen_ids) + 1
        assert all(reports[stage]["id"] == report_id for stage, report_id in seen_ids.items())
        seen_ids = {stage: report["id"] for stage, report in reports.items()}
        if "result-summary" in reports:
            assert only_device(service)["reports"][0]["stage"] == "result-summary"
    before = confirm(service, only_device(service))["device"]
    final = reports_by_stage(service)["result-summary"]
    path = root / SERIAL / "20261029T031626Z" / "qc.right-reference-50ul.encoder.csv"
    path.write_text("cycle,position\n1,99\n", encoding="utf-8")
    service.scan()
    after = only_device(service)
    assert {key: value for key, value in after.items() if key != "reports"} == {key: value for key, value in before.items() if key != "reports"}
    for previous, current in zip(before["reports"], after["reports"]):
        assert {key: value for key, value in previous.items() if key != "evidence_version"} == {key: value for key, value in current.items() if key != "evidence_version"}
        assert (previous["evidence_version"] != current["evidence_version"]) == (current["stage"] == "right-reference-50ul")
    reports = reports_by_stage(service)
    assert reports["result-summary"] == final
    assert service.preview_attachment(reports["right-reference-50ul"]["id"], "encoder")["rows"] == [["1", "99"]]


def test_same_report_copies_select_a_whole_attachment_package(evidence):
    root, _, service = evidence
    original = write_phase_bundle(root, encoder=True)
    service.scan()
    first = only_report(service)
    duplicate = write_bundle(root, phase_bundle(), name="zz-copy")
    service.scan()
    current = only_report(service)
    assert current["id"] == first["id"]
    stored = service.repository.get_report(current["id"])
    assert stored["attachment_paths"] == {"json": duplicate.relative_to(root).as_posix()}
    assert set(stored["attachment_signatures"]) == set(stored["attachment_hashes"]) == {"json"}
    # A later log-only copy does not contribute its unrelated attachments to JSON.
    log = original.with_name("zzz-copy.log")
    log.write_text(readable_log(phase_bundle()), encoding="utf-8")
    service.scan()
    assert service.repository.get_report(current["id"])["attachment_paths"] == stored["attachment_paths"]


def collapse_phase_index_to_legacy(service, database_path, owner_stage, confirmed_stage=None):
    """Model the old index: all three sources/revisions shared one current ID."""
    reports = reports_by_stage(service)
    owner = reports[owner_stage]
    old_id = owner["id"]
    with sqlite3.connect(database_path) as connection:
        revision_rows = connection.execute("SELECT revision,payload,recorded_at FROM failure_report_revisions").fetchall()
        payload = json.loads(connection.execute("SELECT payload FROM failure_reports WHERE id=?", (old_id,)).fetchone()[0])
        for key in ("report_role", "reference_tip_volume_ul", "run_group_id", "report_folder"):
            payload.pop(key, None)
        from modules.test_failures.parser import digest
        old_identity = digest([payload["run_id"], payload["mode"], payload["report_run_id"]])
        connection.execute("UPDATE failure_reports SET identity_key=?,payload=? WHERE id=?", (old_identity, json.dumps(payload), old_id))
        connection.execute("DELETE FROM failure_reports WHERE id<>?", (old_id,))
        connection.execute("UPDATE failure_sources SET report_id=?", (old_id,))
        connection.execute("DELETE FROM failure_report_revisions")
        for revision, historical_payload, recorded_at in revision_rows:
            historical = json.loads(historical_payload)
            historical["id"] = old_id
            for key in ("report_role", "reference_tip_volume_ul", "run_group_id", "report_folder"):
                historical.pop(key, None)
            connection.execute("INSERT INTO failure_report_revisions VALUES (?,?,?,?)",
                               (old_id, revision, json.dumps(historical), recorded_at))
        connection.execute("INSERT INTO failure_report_aliases VALUES (?,?,?)", (service.repository.root_key, "legacy-alias", old_id))
        connection.execute("DELETE FROM failure_index_versions WHERE root_key=?", (service.repository.root_key,))
    confirmation = confirm(service, only_device(service), text="保留旧索引阶段确认原文")
    if confirmed_stage is not None:
        with sqlite3.connect(database_path) as connection:
            connection.execute("UPDATE repair_confirmations SET coverage=? WHERE id=?",
                               (json.dumps({old_id: reports[confirmed_stage]["revision"]}), confirmation["confirmation"]["id"]))
    with sqlite3.connect(database_path) as connection:
        history = connection.execute("SELECT * FROM repair_confirmations ORDER BY id").fetchall()
        revisions = connection.execute("SELECT * FROM failure_report_revisions ORDER BY report_id,revision").fetchall()
    return owner, history, revisions


@pytest.mark.parametrize(("owner_stage", "confirmed_stage"), [
    ("result-summary", None), ("right-reference-50ul", None), ("right-reference-200ul", None),
    ("right-reference-50ul", "result-summary"),
])
def test_legacy_collapsed_index_splits_on_scan_without_reassigning_history(evidence, owner_stage, confirmed_stage):
    root, database_path, service = evidence
    for volume in (None, 50, 200):
        write_phase_bundle(root, volume)
    service.scan()
    owner, before_history, before_revisions = collapse_phase_index_to_legacy(service, database_path, owner_stage, confirmed_stage)
    restarted = FailureService(root, database_path, stable_seconds=0)
    # Listing adds display metadata without silently performing migration.
    assert only_device(restarted)["report_count"] == 1
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version FROM failure_index_versions").fetchall() == []
        assert "report_role" not in json.loads(connection.execute("SELECT payload FROM failure_reports").fetchone()[0])
    assert restarted.scan()["parse_errors"] == 0
    after = only_device(restarted)
    reports = reports_by_stage(restarted)
    assert after["report_count"] == 3
    assert after["reports"][0]["stage"] == "result-summary"
    assert len({report["run_group_id"] for report in reports.values()}) == 1
    assert reports[owner_stage]["id"] == owner["id"]
    assert reports[owner_stage]["revision"] == owner["revision"]
    assert restarted.get_report("legacy-alias")["id"] == owner["id"]
    assert after["unconfirmed_count"] == (3 if confirmed_stage else 2)
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT * FROM repair_confirmations ORDER BY id").fetchall() == before_history
        remaining_revisions = connection.execute("SELECT * FROM failure_report_revisions ORDER BY report_id,revision").fetchall()
        assert all(revision in remaining_revisions for revision in before_revisions)
        assert len({row[0] for row in connection.execute("SELECT report_id FROM failure_sources")}) == 3
    # A repeat scan and another restart are stable; legacy signatures were reset once.
    restarted.scan()
    again = FailureService(root, database_path, stable_seconds=0)
    again.scan()
    assert only_device(again) == after


def test_legacy_missing_checkpoint_keeps_audit_identity_without_foreign_attachments(evidence):
    root, database_path, service = evidence
    paths = {volume: write_phase_bundle(root, volume, encoder=volume is None) for volume in (None, 50, 200)}
    service.scan()
    owner, history, revisions = collapse_phase_index_to_legacy(service, database_path, "right-reference-50ul")
    # Reproduce an old merged optional encoder and then a missing source package.
    with sqlite3.connect(database_path) as connection:
        payload = json.loads(connection.execute("SELECT payload FROM failure_reports").fetchone()[0])
        payload["attachment_paths"]["encoder"] = paths[None].with_suffix(".encoder.csv").relative_to(root).as_posix()
        payload["attachment_signatures"]["encoder"] = [1, 2, 3]
        payload["attachment_hashes"]["encoder"] = "old-foreign-hash"
        connection.execute("UPDATE failure_reports SET payload=?", (json.dumps(payload),))
    paths[50].unlink()
    paths[50].with_suffix(".log").unlink()
    service.scan()
    reports = reports_by_stage(service)
    assert len(reports) == 3
    retained = service.repository.get_report(owner["id"])
    assert retained["stage"] == "right-reference-50ul"
    assert retained["revision"] == owner["revision"]
    assert "encoder" not in retained["attachment_paths"]
    assert not any(item["available"] for item in reports["right-reference-50ul"]["attachments"])
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT * FROM repair_confirmations ORDER BY id").fetchall() == history
        assert all(row in connection.execute("SELECT * FROM failure_report_revisions").fetchall() for row in revisions)


def test_unrelated_main_report_upgrade_does_not_reopen_existing_confirmation(evidence):
    root, database_path, service = evidence
    write_bundle(root)
    service.scan()
    before = confirm(service, only_device(service))["device"]
    with sqlite3.connect(database_path) as connection:
        payload = json.loads(connection.execute("SELECT payload FROM failure_reports").fetchone()[0])
        for key in ("report_role", "reference_tip_volume_ul", "run_group_id", "report_folder"):
            payload.pop(key, None)
        connection.execute("UPDATE failure_reports SET payload=?", (json.dumps(payload),))
        connection.execute("DELETE FROM failure_index_versions")
        original_history = connection.execute("SELECT * FROM repair_confirmations").fetchall()
    restarted = FailureService(root, database_path, stable_seconds=0)
    restarted.scan()
    assert only_device(restarted) == before
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT * FROM repair_confirmations").fetchall() == original_history


def test_legacy_corrupt_source_cannot_borrow_another_checkpoints_payload(evidence):
    root, database_path, service = evidence
    paths = {volume: write_phase_bundle(root, volume) for volume in (None, 50, 200)}
    service.scan()
    owner, history, _ = collapse_phase_index_to_legacy(service, database_path, "right-reference-50ul")
    paths[None].write_text('{"schema_version":1,', encoding="utf-8")
    assert service.scan()["parse_errors"] == 1
    reports = reports_by_stage(service)
    assert len(reports) == 3
    assert reports["result-summary"]["source_format"] == "log"
    assert reports["result-summary"]["failures"][0]["tag"] == "evidence-result-summary"
    assert reports["right-reference-50ul"]["id"] == owner["id"]
    assert reports["right-reference-50ul"]["source_name"] == "qc.right-reference-50ul.json"
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT * FROM repair_confirmations ORDER BY id").fetchall() == history


def test_legacy_index_migration_is_scoped_to_its_report_root(evidence, tmp_path):
    root, database_path, service = evidence
    for volume in (None, 50, 200):
        write_phase_bundle(root, volume)
    service.scan()
    collapse_phase_index_to_legacy(service, database_path, "right-reference-50ul")
    other_root = tmp_path / "other-report-root"
    other = FailureService(other_root, database_path, stable_seconds=0)
    write_phase_bundle(other_root)
    other.scan()
    confirm(other, only_device(other), text="另一个目录的确认")
    with sqlite3.connect(database_path) as connection:
        snapshot = {table: connection.execute(f"SELECT * FROM {table} WHERE root_key=?", (other.repository.root_key,)).fetchall()
                    for table in ("failure_reports", "failure_sources", "repair_confirmations", "failure_index_versions")}
    service.scan()
    assert only_device(service)["report_count"] == 3
    with sqlite3.connect(database_path) as connection:
        for table, before in snapshot.items():
            assert connection.execute(f"SELECT * FROM {table} WHERE root_key=?", (other.repository.root_key,)).fetchall() == before


def write_folder_bundle(root, folder, payload=None, name="qc"):
    path = root / folder / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload if payload is not None else bundle()), encoding="utf-8")
    return path


def folder_rows(service):
    return {item["report_folder"]: item for item in service.list_devices()["devices"]}


@pytest.mark.parametrize("same_run", [True, False])
def test_same_serial_archives_are_independent_even_with_identical_run_fields(evidence, same_run):
    root, _, service = evidence
    write_folder_bundle(root, "SN_20261029T031626Z")
    second = bundle() if same_run else bundle(run_id="next-test", report_run_id="run-26-10-30-03-16-26")
    write_folder_bundle(root, "SN_20261030T031626Z", second)
    service.scan()
    rows = folder_rows(service)
    assert set(rows) == {"SN_20261029T031626Z", "SN_20261030T031626Z"}
    assert len({item["id"] for item in rows.values()}) == 2
    assert {item["sn"] for item in rows.values()} == {SERIAL}
    assert len({item["reports"][0]["id"] for item in rows.values()}) == 2
    assert len({item["reports"][0]["run_group_id"] for item in rows.values()}) == 2
    for folder, item in rows.items():
        assert item["report_count"] == item["unconfirmed_count"] == 1
        summary = item["reports"][0]
        assert summary["report_folder"] == folder
        assert service.get_report(summary["id"])["report_folder"] == folder
    listed = service.list_devices(page_size=1)
    assert len(listed["devices"]) == 1
    assert listed["total"] == listed["summary"]["devices"] == 2
    assert listed["facets"]["all"] == counts(2, 2, 0)
    found = service.list_devices(q="SN_20261030T031626Z")
    assert found["total"] == 1
    assert found["devices"][0]["report_folder"] == "SN_20261030T031626Z"


def test_folder_confirmation_and_versions_never_inherit_from_same_serial(evidence):
    root, database_path, service = evidence
    first_path = write_folder_bundle(root, "first-archive")
    write_folder_bundle(root, "second-archive")
    service.scan()
    before = folder_rows(service)
    first = confirm(service, before["first-archive"], text="只确认第一个目录")
    after_first = folder_rows(service)
    assert after_first["first-archive"]["unconfirmed_count"] == 0
    assert after_first["second-archive"] == before["second-archive"]
    assert service.list_confirmations(before["second-archive"]["id"])["items"] == []
    second = confirm(service, before["second-archive"], text="第二个目录的独立确认")
    changed = bundle(failure_details=["New first-folder failure"])
    first_path.write_text(json.dumps(changed), encoding="utf-8")
    service.scan()
    current = folder_rows(service)
    assert current["first-archive"]["unconfirmed_count"] == 1
    assert current["second-archive"] == second["device"]
    write_folder_bundle(root, "third-archive")
    service.scan()
    third = folder_rows(service)["third-archive"]
    assert third["confirmation"] is None and third["recent_confirmations"] == []
    assert third["unconfirmed_count"] == 1
    with sqlite3.connect(database_path) as connection:
        coverages = {key: json.loads(value) for key, value in connection.execute("SELECT id,coverage FROM repair_confirmations")}
    assert set(coverages[first["confirmation"]["id"]]) == {before["first-archive"]["reports"][0]["id"]}
    assert set(coverages[second["confirmation"]["id"]]) == {before["second-archive"]["reports"][0]["id"]}


def test_root_loose_files_use_distinct_stems_and_do_not_collide_with_folder_labels(evidence):
    root, _, service = evidence
    (root / "qc.json").write_text(json.dumps(bundle()), encoding="utf-8")
    (root / "qc-copy.json").write_text(json.dumps(bundle()), encoding="utf-8")
    write_folder_bundle(root, "qc")
    service.scan()
    rows = service.list_devices()["devices"]
    assert len(rows) == 3
    assert sorted(item["report_folder"] for item in rows) == ["qc", "qc", "qc-copy"]
    assert len({item["id"] for item in rows}) == 3
    assert len({item["reports"][0]["id"] for item in rows}) == 3
    assert len({item["reports"][0]["run_group_id"] for item in rows}) == 3


def test_folder_grouping_does_not_depend_on_serial_availability(evidence):
    root, _, service = evidence
    payload = bundle()
    payload["archive_directory"]["serial_number"] = "unknown-SN"
    payload["trace"]["identity"]["actual_pipettes"]["LEFT"]["serial"] = "unknown-SN"
    write_folder_bundle(root, "unknown-archive", payload)
    reference = json.loads(json.dumps(payload))
    reference["stage"] = "right-reference-50ul"
    write_folder_bundle(root, "unknown-archive", reference, "qc.right-reference-50ul")
    service.scan()
    current = only_device(service)
    assert current["sn"] == "unknown-SN"
    assert current["report_folder"] == "unknown-archive"
    assert current["report_count"] == 2


def make_legacy_v2_index(service, database_path):
    from modules.test_failures.parser import digest
    with sqlite3.connect(database_path) as connection:
        for report_id, encoded in connection.execute("SELECT id,payload FROM failure_reports").fetchall():
            payload = json.loads(encoded)
            payload.pop("report_folder", None)
            identity = digest([payload["run_id"], payload["mode"], payload["report_run_id"]])
            connection.execute("UPDATE failure_reports SET identity_key=?,payload=? WHERE id=?", (identity, json.dumps(payload), report_id))
        connection.execute("UPDATE failure_index_versions SET version=2 WHERE root_key=?", (service.repository.root_key,))


def test_legacy_serial_confirmation_is_attached_only_through_actual_report_coverage(evidence):
    root, database_path, service = evidence
    write_folder_bundle(root, "archive-a")
    write_folder_bundle(root, "archive-b", bundle(run_id="different-run", report_run_id="run-26-10-30-03-16-26"))
    service.scan()
    before = folder_rows(service)
    confirmed = confirm(service, before["archive-a"], text="旧SN行当时只包含A目录")
    make_legacy_v2_index(service, database_path)
    from modules.test_failures.parser import digest
    with sqlite3.connect(database_path) as connection:
        old_sn_id = digest([service.repository.root_key, "sn:" + SERIAL.upper()])[:32]
        connection.execute("UPDATE repair_confirmations SET device_id=?", (old_sn_id,))
        # A stale legacy row ID matching B must not grant B confirmation either.
        connection.execute("UPDATE repair_confirmations SET device_id=? WHERE id=?", (before["archive-b"]["id"], confirmed["confirmation"]["id"]))
        original_history = connection.execute("SELECT * FROM repair_confirmations").fetchall()
        original_revisions = connection.execute("SELECT * FROM failure_report_revisions").fetchall()
    restarted = FailureService(root, database_path, stable_seconds=0)
    restarted.scan()
    rows = folder_rows(restarted)
    assert rows["archive-a"]["confirmation"] == confirmed["confirmation"]
    assert rows["archive-a"]["unconfirmed_count"] == 0
    assert rows["archive-b"]["confirmation"] is None
    assert rows["archive-b"]["unconfirmed_count"] == 1
    assert rows["archive-a"]["reports"][0]["id"] == before["archive-a"]["reports"][0]["id"]
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT * FROM repair_confirmations").fetchall() == original_history
        assert all(item in connection.execute("SELECT * FROM failure_report_revisions").fetchall() for item in original_revisions)


def test_legacy_confirmation_actually_covering_two_folders_remains_visible_in_both(evidence):
    root, database_path, service = evidence
    write_folder_bundle(root, "archive-a")
    write_folder_bundle(root, "archive-b", bundle(run_id="another-run", report_run_id="another-report"))
    service.scan()
    rows = folder_rows(service)
    saved = confirm(service, rows["archive-a"], text="历史确认实际核对过A和B")
    with sqlite3.connect(database_path) as connection:
        coverage = {row["reports"][0]["id"]: row["reports"][0]["revision"] for row in rows.values()}
        connection.execute("UPDATE repair_confirmations SET coverage=? WHERE id=?", (json.dumps(coverage), saved["confirmation"]["id"]))
        original = connection.execute("SELECT * FROM repair_confirmations").fetchall()
    make_legacy_v2_index(service, database_path)
    service.scan()
    current = folder_rows(service)
    assert all(row["unconfirmed_count"] == 0 and row["confirmation"] == saved["confirmation"] for row in current.values())
    before_b = current["archive-b"]
    confirm(service, current["archive-a"], text="现在只更新A目录")
    assert folder_rows(service)["archive-b"] == before_b
    with sqlite3.connect(database_path) as connection:
        assert original[0] in connection.execute("SELECT * FROM repair_confirmations").fetchall()


@pytest.mark.parametrize("owner_folder", ["archive-a", "archive-b"])
def test_legacy_cross_folder_collapsed_sources_split_without_transferring_confirmation(evidence, owner_folder):
    root, database_path, service = evidence
    for folder in ("archive-a", "archive-b"):
        write_folder_bundle(root, folder)
    service.scan()
    rows = folder_rows(service)
    owner = rows[owner_folder]
    old_id = owner["reports"][0]["id"]
    other_id = next(row["reports"][0]["id"] for folder, row in rows.items() if folder != owner_folder)
    saved = confirm(service, owner, text="保留旧合并索引确认，不转授新目录")
    make_legacy_v2_index(service, database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE failure_sources SET report_id=?", (old_id,))
        connection.execute("DELETE FROM failure_reports WHERE id=?", (other_id,))
        connection.execute("INSERT INTO failure_report_aliases VALUES (?,?,?)", (service.repository.root_key, other_id, old_id))
        original_history = connection.execute("SELECT * FROM repair_confirmations").fetchall()
        original_revisions = connection.execute("SELECT * FROM failure_report_revisions").fetchall()
    restarted = FailureService(root, database_path, stable_seconds=0)
    restarted.scan()
    after = folder_rows(restarted)
    assert len(after) == 2
    assert after[owner_folder]["reports"][0]["id"] == old_id
    assert after[owner_folder]["confirmation"] == saved["confirmation"]
    assert after[owner_folder]["unconfirmed_count"] == 0
    other_folder = next(folder for folder in after if folder != owner_folder)
    new_id = after[other_folder]["reports"][0]["id"]
    assert new_id not in {old_id, other_id}
    assert restarted.get_report(new_id)["report_folder"] == other_folder
    assert after[other_folder]["confirmation"] is None
    assert after[other_folder]["unconfirmed_count"] == 1
    assert restarted.get_report(other_id)["report_folder"] == owner_folder  # Historical alias keeps its original target.
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT * FROM repair_confirmations").fetchall() == original_history
        assert all(item in connection.execute("SELECT * FROM failure_report_revisions").fetchall() for item in original_revisions)
    restarted.scan()
    assert folder_rows(FailureService(root, database_path, stable_seconds=0)) == after


def test_attachment_preview_rejects_user_supplied_traversal(api):
    client, auth, service = api
    _, session = session_for(auth)
    report = only_report(service)
    for kind in ("..%2F..%2Foutside.log", "%2Fetc%2Fpasswd", "unsupported"):
        response = client.get(PREFIX + f"/reports/{report['id']}/attachments/{kind}/preview", headers=bearer(session))
        assert response.status_code in {400, 404, 422}


def test_attachment_download_returns_only_indexed_source_and_missing_files_are_404(api, evidence):
    client, auth, service = api
    root, _, _ = evidence
    _, session = session_for(auth)
    report = only_report(service)
    response = client.get(PREFIX + f"/reports/{report['id']}/attachments/json", headers=bearer(session))
    assert response.status_code == 200
    assert response.json()["run_id"] == RUN_ID
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["cache-control"] == "no-store"
    (root / SERIAL / "20261029T031626Z" / "qc.json").unlink()
    missing = client.get(PREFIX + f"/reports/{report['id']}/attachments/json", headers=bearer(session))
    assert missing.status_code == 404
