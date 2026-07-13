from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from upload_handler.parsers.registry import extract_csv


DATAS_CASE_PROPERTY = "datas_case"
REQUIRED_PARSE_KEYS = ("upload_config_key",)


def _find_csv_files(case_dir: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in case_dir.rglob("*")
            if path.is_file() and path.suffix.lower() == ".csv"
        ),
        key=lambda path: path.relative_to(case_dir).as_posix().casefold(),
    )


def _normalize_parse_error(parse_result: dict[str, Any] | None) -> str:
    if parse_result is None:
        return "Parser did not return a result. Check metadata, model, test name, and parser definition."
    if parse_result.get("failed") is True:
        return str(parse_result.get("error") or "CSV parser marked the file as failed.")
    error = parse_result.get("error")
    if error not in (None, "", "False"):
        return str(error)
    return ""


def _file_report(
    csv_file: Path,
    case_dir: Path,
    parse_result: dict[str, Any] | None,
) -> dict[str, Any]:
    parse_result = parse_result or {}
    return {
        "file": csv_file.relative_to(case_dir).as_posix(),
        "status": "passed",
        "upload_config_key": parse_result.get("upload_config_key", ""),
        "sn": parse_result.get("sn", ""),
        "model": parse_result.get("model", ""),
        "test_type": parse_result.get("test_type", ""),
        "finished": parse_result.get("finished", ""),
        "error": "",
    }


def _validate_parse_result(
    csv_file: Path,
    parse_result: dict[str, Any] | None,
) -> list[str]:
    error = _normalize_parse_error(parse_result)
    if error:
        return [f"{csv_file.name}: {error}"]

    missing_keys = [key for key in REQUIRED_PARSE_KEYS if not parse_result.get(key)]
    if missing_keys:
        missing = ", ".join(missing_keys)
        return [f"{csv_file.name}: missing parse key(s): {missing}"]

    return []


def test_z_stage_manual_meta_sn_overrides_csv_sn() -> None:
    csv_file = (
        Path(__file__).resolve().parents[1]
        / "datas"
        / "Flex"
        / "z-stage-test-qc-ot3_run-26-06-02-07-49-43.csv"
    )
    user_sn = "ZS102026060199"
    parse_result = extract_csv(
        str(csv_file),
        meta={
            "test_device_id": user_sn,
            "serial-number": user_sn,
            "test_type": "z_stage_test",
        },
    )

    assert parse_result is not None
    assert parse_result["upload_config_key"] == "robot_update_z_stage"
    assert parse_result["sn"] == user_sn
    assert parse_result["model"] == "Robot"


def test_datas_case_csv_parse(
    data_case_dir: Path,
    upload_client,
    slack_notifier,
    datas_csv_report,
    datas_csv_progress,
    datas_csv_config,
    request,
) -> None:
    request.node.user_properties.append((DATAS_CASE_PROPERTY, data_case_dir.name))
    csv_files = _find_csv_files(data_case_dir)
    datas_csv_progress(
        f"case start: {data_case_dir.name} ({len(csv_files)} csv file(s))"
    )
    case_report: dict[str, Any] = {
        "case": data_case_dir.name,
        "path": str(data_case_dir),
        "status": "passed",
        "csv_count": len(csv_files),
        "files": [],
    }
    disabled_folder_key = data_case_dir.name.strip().casefold()
    if disabled_folder_key in datas_csv_config["disabled_folder_keys"]:
        config_path = datas_csv_config["config_path"]
        skip_reason = f"Disabled by datas CSV config: {config_path}"
        case_report["status"] = "disabled"
        case_report["skip_reason"] = skip_reason
        datas_csv_report(case_report)
        datas_csv_progress(f"case disabled: {data_case_dir.name} ({config_path})")
        pytest.skip(skip_reason)

    if not csv_files:
        case_report["status"] = "skipped"
        case_report["skip_reason"] = "No CSV files found."
        datas_csv_report(case_report)
        datas_csv_progress(f"case skipped: {data_case_dir.name} (no csv files)")
        pytest.skip("No CSV files found.")

    failures: list[str] = []
    for csv_file in csv_files:
        relative_csv_file = csv_file.relative_to(data_case_dir).as_posix()
        datas_csv_progress(f"parse start: {data_case_dir.name}/{relative_csv_file}")
        parse_result = extract_csv(str(csv_file))
        file_report = _file_report(csv_file, data_case_dir, parse_result)
        parse_failures = _validate_parse_result(csv_file, parse_result)
        if parse_failures and upload_client is None:
            file_report["status"] = "failed"
            file_report["error"] = "; ".join(parse_failures)
            failures.extend(parse_failures)
            case_report["files"].append(file_report)
            datas_csv_progress(
                f"parse failed: {data_case_dir.name}/{relative_csv_file} - {file_report['error']}"
            )
            continue

        if parse_failures:
            datas_csv_progress(
                f"parse failed before business upload: {data_case_dir.name}/{relative_csv_file} - "
                f"{'; '.join(parse_failures)}"
            )
        else:
            datas_csv_progress(
                "parse ok: {case}/{file} key={key} sn={sn} model={model} "
                "test_type={test_type} finished={finished}".format(
                    case=data_case_dir.name,
                    file=relative_csv_file,
                    key=file_report["upload_config_key"],
                    sn=file_report["sn"],
                    model=file_report["model"],
                    test_type=file_report["test_type"],
                    finished=file_report["finished"],
                )
            )

        if upload_client is not None:
            datas_csv_progress(f"upload start: {data_case_dir.name}/{relative_csv_file}")
            upload_result = upload_client(str(csv_file))
            file_report["upload"] = upload_result
            if upload_result.get("finished") is True:
                file_report["status"] = "uploaded"
                datas_csv_progress(
                    f"upload ok: {data_case_dir.name}/{relative_csv_file}"
                )
                if slack_notifier is not None:
                    slack_notifier(upload_result, str(csv_file))
                    datas_csv_progress(
                        f"slack ok: {data_case_dir.name}/{relative_csv_file}"
                    )
            else:
                file_report["status"] = "upload_failed"
                file_report["error"] = str(upload_result.get("error") or "Upload failed.")
                if slack_notifier is not None:
                    slack_notifier(
                        upload_result,
                        str(csv_file),
                        error_message=file_report["error"],
                    )
                    datas_csv_progress(
                        f"slack fail sent: {data_case_dir.name}/{relative_csv_file}"
                    )
                failures.append(f"{csv_file.name}: {file_report['error']}")
                datas_csv_progress(
                    f"upload failed: {data_case_dir.name}/{relative_csv_file} - {file_report['error']}"
                )

        case_report["files"].append(file_report)

    if failures:
        case_report["status"] = "failed"
    elif upload_client is not None:
        case_report["status"] = "uploaded"

    datas_csv_report(case_report)
    datas_csv_progress(
        f"case done: {data_case_dir.name} status={case_report['status']}"
    )
    assert not failures, "\n".join(failures)
