from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .products import normalize_product, product_from_serial
from .reference import reference_snapshot


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def normalized_time(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    for fmt in ("%Y/%m/%d-%H:%M:%S", "run-%y-%m-%d-%H-%M-%S", "%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S.%fZ"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def _strings(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def _mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _log_json(text: str, marker: str, default: Any) -> Any:
    start = text.find(marker)
    if start < 0:
        return default
    try:
        return json.JSONDecoder().raw_decode(text[start + len(marker):].lstrip())[0]
    except (ValueError, TypeError):
        return default


def parse_log(text: str) -> dict[str, Any]:
    """Read the producer's labelled sections, never classify arbitrary log words."""
    def header(name: str) -> str:
        match = re.search(r"^" + re.escape(name) + r":\s*(.*)$", text, re.MULTILINE)
        return match.group(1).strip() if match else ""

    rows: list[dict] = []
    section = text.split("All report rows (unknown or not_recorded does not mean PASS):", 1)
    if len(section) == 2:
        for line in section[1].splitlines():
            if line.strip().startswith("{"):
                try:
                    item = json.loads(line)
                    if isinstance(item, dict) and "section" in item and "tag" in item:
                        rows.append(item)
                except ValueError:
                    pass
    details: list[str] = []
    section = text.split("Failure details:", 1)
    if len(section) == 2:
        for line in section[1].splitlines():
            if line.startswith("- "):
                details.append(line[2:])
            elif details or line.strip():
                break
    observed = _mapping(_log_json(text, "Failure action and latest observed readings (not trigger-time values):", {}))
    runtime = next((detail.removeprefix("[QC_RUNTIME_ERROR] ") for detail in details if detail.startswith("[QC_RUNTIME_ERROR] ")), "")
    runtime_type, _, runtime_message = runtime.partition(":")
    return {
        "schema_version": 1,
        "run_id": header("Run ID"), "mode": header("QC mode"), "stage": header("Stage"),
        "created_at_utc": header("Time UTC"), "failure_details": details,
        "report_rows": rows, "archive_directory": _log_json(text, "Failure archive directory:", {}),
        "runtime_error": {"type": runtime_type, "message": runtime_message.strip()} if runtime else None,
        "trace": {
            "identity": _log_json(text, "Run identity / versions:", {}),
            "tests": _log_json(text, "Test execution states:", {}),
            "last_failure": observed.get("last_failure"),
            "events": _log_json(text, "Action history:", []),
        },
        "recommendations": _log_json(text, "Checks and retest recommendations (unconfirmed causes are not part diagnoses):", []),
    }


def _business_exception(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    return {key: value[key] for key in ("action", "error", "arguments", "context") if key in value}


def parse_report(content: bytes | str, source_format: str, source_name: str) -> dict[str, Any]:
    text = content.decode("utf-8-sig", errors="strict") if isinstance(content, bytes) else content
    bundle = json.loads(text) if source_format == "json" else parse_log(text)
    if not isinstance(bundle, dict) or bundle.get("schema_version") != 1:
        raise ValueError("不支持的失败报告格式或 schema_version")
    if not isinstance(bundle.get("report_rows", []), list):
        raise ValueError("report_rows 必须是数组")
    trace = _mapping(bundle.get("trace"))
    identity = _mapping(trace.get("identity"))
    archive = _mapping(bundle.get("archive_directory"))
    raw_rows = [row for row in bundle.get("report_rows", []) if isinstance(row, dict)]
    metadata = {str(row.get("tag")): row["data"][0] for row in raw_rows
                if row.get("section") == "META_DATA" and isinstance(row.get("data"), list) and row["data"]}
    left = _mapping(_mapping(identity.get("actual_pipettes")).get("LEFT"))
    sn = str(metadata.get("test_device_id") or left.get("serial") or archive.get("serial_number") or "").strip()
    if sn.casefold() in {"unknown-sn", "unknown", "none", "n/a", "null"}:
        sn = ""
    product = normalize_product(left.get("name") or left.get("model") or identity.get("selected_pipette_type")) or product_from_serial(sn)
    report_run_id = str(bundle.get("report_run_id") or metadata.get("test_run_id") or "")
    original_test_time = (normalized_time(metadata.get("test_time_utc")) or normalized_time(archive.get("timestamp_utc"))
                          or normalized_time(report_run_id))
    test_time = original_test_time or normalized_time(bundle.get("created_at_utc"))
    failures = []
    for row in raw_rows:
        if row.get("result") != "FAIL":
            continue
        index = row.get("index", 0)
        if not isinstance(index, int):
            index = 0
        section_name, tag = str(row.get("section") or ""), str(row.get("tag") or "")
        failures.append({
            "evidence_id": str(row.get("evidence_id") or f"{section_name}/{tag}[{index}]"),
            "section": section_name, "tag": tag, "index": index, "result": "FAIL",
            "data": row.get("data") if isinstance(row.get("data"), list) else [],
            "error_codes": _strings(row.get("error_codes")), "failure_reasons": _strings(row.get("failure_reasons")),
            "elapsed_seconds": row.get("elapsed_seconds"),
        })
    # Report overview is retained for inspection but does not inflate failed-item counts.
    concrete = [row for row in failures if row["section"] != "RESULTS_OVERVIEW"]
    tests = {str(name): {key: state[key] for key in ("status", "error", "blocking_stage", "last_handled_exception") if key in state}
             for name, state in _mapping(trace.get("tests")).items() if isinstance(state, dict)}
    runtime = bundle.get("runtime_error") if isinstance(bundle.get("runtime_error"), dict) else None
    last_failure = trace.get("last_failure") if isinstance(trace.get("last_failure"), dict) else None
    reference = reference_snapshot(bundle)
    execution_errors = [state for state in tests.values() if state.get("status") in {"execution_error", "exception"}]
    # Immediate reference snapshots still retain last_failure before the producer
    # moves it to last_handled_exception. Only a matching handled event can relax
    # that inference; explicit runtime/test execution errors always take priority.
    handled_reference = reference is not None and reference.handled is True
    runtime_failed = bool(runtime or execution_errors or reference is not None and reference.handled is False
                          or last_failure and last_failure.get("error") and not handled_reference)
    test_failed = bool(failures or handled_reference or any(state.get("status") == "failed" for state in tests.values()))
    kind = "mixed" if runtime_failed and test_failed else "runtime_error" if runtime_failed else "test_failure" if test_failed else "incomplete"
    details = _strings(bundle.get("failure_details"))
    summary = list(dict.fromkeys(details or [reason for row in concrete for reason in row["failure_reasons"]]))
    if not summary:
        summary = [f"{row['section']}/{row['tag']}: {', '.join(row['error_codes']) or '测试不通过'}" for row in concrete or failures]
    if runtime and not any("QC_RUNTIME_ERROR" in item for item in summary):
        summary.insert(0, f"{runtime.get('type') or '执行异常'}: {runtime.get('message') or ''}")
    if not summary and execution_errors:
        summary = [str(state.get("error") or "测试执行异常") for state in execution_errors]
    if not summary and last_failure and last_failure.get("error"):
        summary = [str(last_failure["error"])]
    if not summary:
        summary = ["缺少明确失败判定，请查看原始报告"]
    warnings = []
    for key in ("trace_error", "report_extraction_error", "encoder_checkpoint_error"):
        if bundle.get(key):
            warnings.append(f"{key}: {bundle[key]}")
    if source_format == "log":
        warnings.append("仅有日志，等待结构化 JSON；当前依据可识别的日志字段展示")
    if not sn:
        warnings.append("设备 SN 未知，该报告独立展示")
    parse_status = "incomplete" if kind == "incomplete" or bundle.get("report_extraction_error") else "ready" if source_format == "json" else "log_only"
    recommendations = []
    for item in bundle.get("recommendations", []) if isinstance(bundle.get("recommendations"), list) else []:
        if isinstance(item, dict):
            recommendations.append({key: item.get(key, [] if key in {"evidence", "next_checks"} else "") for key in ("category", "status", "evidence", "next_checks", "retest")})
    payload = {
        "sn": sn or "unknown-SN", "known_sn": bool(sn), "product": product, "test_time": test_time,
        "run_id": str(bundle.get("run_id") or ""), "report_run_id": report_run_id,
        "mode": str(bundle.get("mode") or "unknown"), "stage": str(bundle.get("stage") or "unknown"),
        "report_role": "right_reference" if reference else "main",
        "reference_tip_volume_ul": reference.volume if reference else None,
        "reference_handled": reference.handled if reference else None,
        "kind": kind, "summary": summary, "failure_count": len(concrete or failures), "failures": failures,
        "tests": tests, "runtime_error": runtime, "last_failure": last_failure,
        "recommendations": recommendations, "warnings": warnings, "identity": identity,
        "parse_status": parse_status, "source_format": source_format, "source_name": source_name,
    }
    # Changes to upload receipts, timestamps, PASS rows and logging details are not new failures.
    semantic = {
        "sn": payload["sn"], "mode": payload["mode"], "stage": payload["stage"], "kind": kind,
        "test_time": original_test_time,
        "failures": [{key: value for key, value in row.items() if key != "elapsed_seconds"} for row in sorted(failures, key=lambda item: item["evidence_id"])],
        "summary": sorted(summary), "runtime_error": runtime, "last_failure": _business_exception(payload["last_failure"]),
        "tests": {name: {key: state[key] for key in ("status", "error", "blocking_stage") if key in state} for name, state in tests.items()
                  if state.get("status") in {"failed", "execution_error", "exception", "not_run_due_to_previous_failure"}},
    }
    payload["revision"] = digest(semantic)
    payload["semantic"] = semantic
    return payload
