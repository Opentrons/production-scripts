from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = BACKEND_ROOT / "src"
DEFAULT_DATAS_DIR = BACKEND_ROOT / "datas"
DEFAULT_DATAS_CONFIG_PATH = BACKEND_ROOT / "tests" / "datas_csv_config.json"
DEFAULT_REPORT_PATH = BACKEND_ROOT / "tests" / "reports" / "datas_csv_report.json"
DATAS_CASE_PROPERTY = "datas_case"

for import_path in (BACKEND_ROOT, SRC_ROOT):
    import_path_str = str(import_path)
    if import_path_str not in sys.path:
        sys.path.insert(0, import_path_str)


def _resolve_backend_path(path_value: str | Path) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    return path


def _iter_data_case_dirs(datas_dir: Path) -> list[Path]:
    if not datas_dir.exists():
        return []
    return sorted(
        (
            child
            for child in datas_dir.iterdir()
            if child.is_dir() and not child.name.startswith(".")
        ),
        key=lambda path: path.name.casefold(),
    )


def _case_id(case_dir: Path, datas_dir: Path) -> str:
    case_name = case_dir.relative_to(datas_dir).as_posix()
    if case_name != case_name.strip():
        return repr(case_name)
    return case_name


def _display_case_name(case_name: str) -> str:
    if case_name != case_name.strip():
        return repr(case_name)
    return case_name


def _normalize_case_name(case_name: str) -> str:
    return str(case_name).strip().casefold()


def _load_datas_csv_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {"disabled_folders": []}

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise pytest.UsageError(f"Invalid datas CSV config JSON: {config_path}: {exc}") from exc

    if not isinstance(config, dict):
        raise pytest.UsageError(f"Datas CSV config must be a JSON object: {config_path}")
    disabled_folders = config.get("disabled_folders", [])
    if not isinstance(disabled_folders, list):
        raise pytest.UsageError(
            f"Datas CSV config field 'disabled_folders' must be a list: {config_path}"
        )
    return config


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    case_status_counts = Counter(case.get("status", "unknown") for case in cases)
    file_status_counts = Counter(
        file_report.get("status", "unknown")
        for case in cases
        for file_report in case.get("files", [])
    )
    parsed_files = sum(
        file_status_counts.get(status, 0)
        for status in ("passed", "uploaded", "upload_failed")
    )
    return {
        "cases": len(cases),
        "case_status": dict(sorted(case_status_counts.items())),
        "csv_files": sum(len(case.get("files", [])) for case in cases),
        "file_status": dict(sorted(file_status_counts.items())),
        "parsed_files": parsed_files,
        "failed_files": file_status_counts.get("failed", 0),
        "uploaded_files": file_status_counts.get("uploaded", 0),
        "upload_failed_files": file_status_counts.get("upload_failed", 0),
    }


def _write_markdown_report(report_path: Path, report: dict[str, Any]) -> Path:
    markdown_path = report_path.with_suffix(".md")
    summary = report["summary"]
    lines = [
        "# Datas CSV pytest report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Datas dir: `{report['datas_dir']}`",
        f"- Upload enabled: `{report['upload_enabled']}`",
        f"- Cases: `{summary['cases']}`",
        f"- CSV files: `{summary['csv_files']}`",
        f"- Parsed files: `{summary['parsed_files']}`",
        f"- Failed files: `{summary['failed_files']}`",
        f"- Uploaded files: `{summary['uploaded_files']}`",
        f"- Upload failed files: `{summary['upload_failed_files']}`",
        "",
        "| Case | Status | CSV count | Failed |",
        "| --- | --- | ---: | ---: |",
    ]
    for case in report["cases"]:
        failed_files = [
            file_report
            for file_report in case.get("files", [])
            if file_report.get("status") in {"failed", "upload_failed"}
        ]
        lines.append(
            f"| `{case['case']}` | `{case['status']}` | "
            f"{case.get('csv_count', 0)} | {len(failed_files)} |"
        )

    lines.extend(["", "## Files", ""])
    for case in report["cases"]:
        lines.extend([f"### {case['case']}", ""])
        if not case.get("files"):
            skip_reason = case.get("skip_reason")
            if skip_reason:
                lines.extend([str(skip_reason), ""])
            else:
                lines.extend(["No CSV files found.", ""])
            continue
        lines.extend(
            [
                "| File | Status | Key | SN | Model | Test type | Finished | Error |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for file_report in case["files"]:
            lines.append(
                f"| `{file_report['file']}` | `{file_report['status']}` | "
                f"`{file_report.get('upload_config_key', '')}` | "
                f"`{file_report.get('sn', '')}` | "
                f"`{file_report.get('model', '')}` | "
                f"`{file_report.get('test_type', '')}` | "
                f"`{file_report.get('finished', '')}` | "
                f"{file_report.get('error') or ''} |"
            )
        lines.append("")

    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return markdown_path


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("datas-csv")
    group.addoption(
        "--datas-dir",
        action="store",
        default=str(DEFAULT_DATAS_DIR),
        help="Directory whose direct children are collected as datas CSV test cases.",
    )
    group.addoption(
        "--datas-config",
        action="store",
        default=str(DEFAULT_DATAS_CONFIG_PATH),
        help="JSON config that can disable datas CSV folders.",
    )
    group.addoption(
        "--upload",
        action="store_true",
        default=False,
        help="Upload each successfully parsed CSV after parsing. Disabled by default.",
    )
    group.addoption(
        "--slack",
        action="store_true",
        default=False,
        help="Send Slack notifications after upload. Requires --upload.",
    )
    group.addoption(
        "--datas-report",
        action="store",
        default=str(DEFAULT_REPORT_PATH),
        help="Path for the generated datas CSV JSON report.",
    )
    group.addoption(
        "--no-datas-progress",
        action="store_true",
        default=False,
        help="Disable live datas CSV progress output.",
    )


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--slack") and not config.getoption("--upload"):
        raise pytest.UsageError("--slack requires --upload")
    config._datas_csv_report_cases = []
    config._datas_csv_report_path = None
    config._datas_csv_markdown_report_path = None


def pytest_report_teststatus(report: pytest.TestReport, config: pytest.Config):
    if report.when != "call":
        return None

    case_name = None
    for key, value in getattr(report, "user_properties", []):
        if key == DATAS_CASE_PROPERTY:
            case_name = str(value)
            break
    if not case_name:
        return None

    case_name = _display_case_name(case_name)
    if report.passed:
        return "passed", f". {case_name}\n", f"PASSED {case_name}"
    if report.skipped:
        return "skipped", f"s {case_name}\n", f"SKIPPED {case_name}"
    if report.failed:
        return "failed", f"F {case_name}\n", f"FAILED {case_name}"
    return None


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "data_case_dir" not in metafunc.fixturenames:
        return

    datas_dir = _resolve_backend_path(metafunc.config.getoption("--datas-dir"))
    case_dirs = _iter_data_case_dirs(datas_dir)
    metafunc.parametrize(
        "data_case_dir",
        case_dirs,
        ids=[_case_id(case_dir, datas_dir) for case_dir in case_dirs],
    )


@pytest.fixture
def upload_client(pytestconfig: pytest.Config):
    if not pytestconfig.getoption("--upload"):
        return None

    def upload(file_path: str):
        from upload_handler.upload import UploadData

        client = UploadData()
        client.init_upload_handler()
        return client.update_data_to_google_drive(file_path)

    return upload


@pytest.fixture
def slack_notifier(pytestconfig: pytest.Config):
    if not pytestconfig.getoption("--slack"):
        return None

    def notify(result: dict | None, csv_path: str, error_message: str | None = None) -> bool:
        from upload_handler.upload import notify_upload_result_to_slack

        return notify_upload_result_to_slack(
            result,
            csv_path,
            error_message=error_message,
        )

    return notify


@pytest.fixture
def datas_csv_report(pytestconfig: pytest.Config):
    def record(case_report: dict[str, Any]) -> None:
        pytestconfig._datas_csv_report_cases.append(case_report)

    return record


@pytest.fixture(scope="session")
def datas_csv_config(pytestconfig: pytest.Config) -> dict[str, Any]:
    config_path = _resolve_backend_path(pytestconfig.getoption("--datas-config"))
    config = _load_datas_csv_config(config_path)
    disabled_folders = {
        _normalize_case_name(folder)
        for folder in config.get("disabled_folders", [])
        if str(folder).strip()
    }
    return {
        **config,
        "config_path": str(config_path),
        "disabled_folder_keys": disabled_folders,
    }


@pytest.fixture
def datas_csv_progress(pytestconfig: pytest.Config):
    enabled = not pytestconfig.getoption("--no-datas-progress")
    terminalreporter = pytestconfig.pluginmanager.get_plugin("terminalreporter")

    def write(message: str) -> None:
        if not enabled:
            return
        line = f"[datas-csv] {message}"
        if terminalreporter is not None:
            terminalreporter.write_line(line)
            return
        print(line, flush=True)

    return write


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    config = session.config
    cases = getattr(config, "_datas_csv_report_cases", [])
    report_path = _resolve_backend_path(config.getoption("--datas-report"))
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "generated_at": _utc_now(),
        "datas_dir": str(_resolve_backend_path(config.getoption("--datas-dir"))),
        "upload_enabled": bool(config.getoption("--upload")),
        "exitstatus": exitstatus,
        "summary": _build_summary(cases),
        "cases": cases,
    }

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    markdown_path = _write_markdown_report(report_path, report)
    config._datas_csv_report_path = report_path
    config._datas_csv_markdown_report_path = markdown_path


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    report_path = getattr(config, "_datas_csv_report_path", None)
    markdown_path = getattr(config, "_datas_csv_markdown_report_path", None)
    if not report_path:
        return

    summary = _build_summary(getattr(config, "_datas_csv_report_cases", []))
    terminalreporter.write_sep("-", "datas csv report")
    terminalreporter.write_line(f"json: {report_path}")
    terminalreporter.write_line(f"markdown: {markdown_path}")
    terminalreporter.write_line(
        "cases={cases}, csv_files={csv_files}, parsed={parsed}, failed={failed}".format(
            cases=summary["cases"],
            csv_files=summary["csv_files"],
            parsed=summary["parsed_files"],
            failed=summary["failed_files"] + summary["upload_failed_files"],
        )
    )
