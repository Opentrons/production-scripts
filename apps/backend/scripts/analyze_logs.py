#!/usr/bin/env python3
"""Analyze Opentrons application log bundles and emit JSON.

The robot's log download endpoint returns a ZIP containing files such as
``opentrons-logs/api.log`` and ``opentrons-logs/server.log``.  The files use a
syslog-like prefix and stack traces/CAN payloads continue on indented lines.
This script joins those lines before looking for failures, so a wrapped
``ExceptionInProtocolError`` is reported as one useful error rather than a
large collection of unrelated traceback lines.

Examples::

    # Slim summary of the last protocol failure
    python apps/backend/scripts/analyze_logs.py \
        ~/testing_data/logs/opentrons-app-logs-192.168.6.126-20260902-021637.zip

    # Ask production-agent to explain the root cause from Opentrons source
    python apps/backend/scripts/analyze_logs.py --agent \
        ~/testing_data/logs/opentrons-app-logs-192.168.6.126-20260902-021637.zip

    # Full diagnostic JSON (previous verbose schema)
    python apps/backend/scripts/analyze_logs.py --full --pretty \
        ~/testing_data/logs/opentrons-app-logs-192.168.6.126-20260902-021637.zip

The default output is a short keyword summary of the last protocol
failure (time + error).  Pass ``--agent`` to call production-agent, which
searches the local Opentrons checkout for the real root cause.

The full schema deliberately exposes two different classifications:

``run_kind``
    How Robot Server executed the work: ``protocol_run`` or
    ``maintenance_run`` (or ``standalone`` for a direct hardware-testing
    process).  A maintenance run has no protocol metadata in the upstream
    Robot Server source.

``test_type``
    The likely production test family: ``protocol_test`` or ``hardware_test``.
    Opentrons' ``hardware-testing`` repository implements many hardware tests
    as protocols, so a result can legitimately be ``run_kind=protocol_run``
    and ``test_type=hardware_test`` at the same time.

Only operational/test failures are included by default.  Repeated
``stop_requested`` warnings, health-polling 422s, update-server hostname
warnings, and Chromium D-Bus diagnostics are retained as noise counters but
do not hide the last meaningful test failure.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Iterator, Sequence, TextIO
from urllib.parse import urlsplit
import zipfile


DEFAULT_LOG_DIR = Path.home() / "testing_data" / "logs"
MAX_RECORD_BYTES = 128 * 1024
MAX_OUTPUT_RAW = 4_000
MAX_ERRORS_IN_DEFAULT_OUTPUT = 20
ROUTE_CONTEXT_WINDOW = timedelta(minutes=20)
PROTOCOL_CONTEXT_WINDOW = timedelta(minutes=45)
RELATED_ERROR_WINDOW = timedelta(seconds=45)

MONTHS = {name: number for number, name in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}

# The codes/classes below are stable names from Opentrons shared-data.  The
# numeric code is still parsed from the log when one is present.
ERROR_CODE_NAMES: dict[str, str] = {
    "1000": "COMMUNICATION_ERROR",
    "1001": "CANBUS_COMMUNICATION_ERROR",
    "1002": "INTERNAL_USB_COMMUNICATION_ERROR",
    "1003": "MODULE_COMMUNICATION_ERROR",
    "1004": "COMMAND_TIMED_OUT",
    "2001": "MOTION_FAILED",
    "3005": "UNEXPECTED_TIP_REMOVAL",
    "3013": "FIRMWARE_UPDATE_REQUIRED",
    "4010": "RUNTIME_PARAMETER_VALUE_REQUIRED",
}

EXCEPTION_CODES: dict[str, tuple[str, str]] = {
    "communicationerror": ("1000", "COMMUNICATION_ERROR"),
    "canbuscommunicationerror": ("1001", "CANBUS_COMMUNICATION_ERROR"),
    "internalusbcommunicationerror": ("1002", "INTERNAL_USB_COMMUNICATION_ERROR"),
    "modulecommunicationerror": ("1003", "MODULE_COMMUNICATION_ERROR"),
    "commandtimedouterror": ("1004", "COMMAND_TIMED_OUT"),
    "motionfailederror": ("2001", "MOTION_FAILED"),
    "tipnotattachederror": ("3005", "UNEXPECTED_TIP_REMOVAL"),
    "failedtipstatecheck": ("3005", "UNEXPECTED_TIP_REMOVAL"),
    "firmwareupdaterequirederror": ("3013", "FIRMWARE_UPDATE_REQUIRED"),
    "runtimeparameterrequired": ("4010", "RUNTIME_PARAMETER_VALUE_REQUIRED"),
    "runstoppederror": ("4000", "GENERAL_ERROR"),
    "executioncancellederror": ("4000", "GENERAL_ERROR"),
}
CODE_EXCEPTIONS = {
    "1000": "CommunicationError",
    "1001": "CanBusCommunicationError",
    "1002": "InternalUsbCommunicationError",
    "1003": "ModuleCommunicationError",
    "1004": "CommandTimedOutError",
    "2001": "MotionFailedError",
    "3005": "TipNotAttachedError",
    "3013": "FirmwareUpdateRequiredError",
    "4010": "RuntimeParameterRequired",
}

FIRMWARE_ERROR_NAMES = {
    "estop_detected": "ESTOP_DETECTED",
    "estop_released": "ESTOP_RELEASED",
    "stop_requested": "STOP_REQUESTED",
    "ok": "OK",
}

EXCEPTION_DETAIL_NAMES = {
    "exceptioninprotocolerror",
    "protocolcommandfailederror",
    "generalerror",
    "error",
}

HARDWARE_MARKERS = (
    "hardware-testing",
    "hardware_testing",
    "production_qc",
    "production qc",
    "gravimetric",
    "preheat",
    "pre-heating",
    "photometric",
    "assembly_qc",
    "assembly qc",
    "calibration",
    "leveling",
    "diagnostic",
    "stress test",
    "stress_test",
    "tip_overlap",
    "dropout",
    "pipette",
    "gripper",
    "gantry",
    "belt",
    "vacuum",
    "thermocycler",
    "temperature",
    "pressure",
)

PROTOCOL_TEST_MARKER = re.compile(
    r"\b(?:dropout\s*(?:&|and)\s*)?protocol[\s_-]+test\b", re.IGNORECASE
)

SYSLOG_RE = re.compile(
    r"^(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"(?P<day>\d{1,2})\s+(?P<clock>\d{2}:\d{2}:\d{2}(?:[.,]\d{1,9})?)\s+"
    r"(?P<host>\S+)\s+(?P<ident>[^:]+):\s?(?P<message>.*)$",
    re.IGNORECASE,
)
YEAR_SYSLOG_RE = re.compile(
    r"^(?P<year>\d{4})[-/]?(?P<month>\d{1,2})[-/]?(?P<day>\d{1,2})[T ]"
    r"(?P<clock>\d{2}:\d{2}:\d{2}(?:[.,]\d{1,9})?)"
    r"(?:Z|[+-]\d{2}:?\d{2})?\s+(?P<rest>.*)$"
)
ISO_RE = re.compile(
    r"^(?P<stamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[.,]\d{1,9})?(?:Z|[+-]\d{2}:?\d{2})?)\s+(?P<rest>.*)$"
)
IDENT_RE = re.compile(r"^(?P<process>.*?)(?:\[(?P<pid>\d+)\])?$")
CODE_RE = re.compile(
    r"(?i:\bError)\s+(?P<code>\d{3,5})(?:\s+(?P<name>[A-Z][A-Z0-9_]+))?"
    r"(?:\s+\((?P<exception>[^)]+)\))?\s*(?::\s*(?P<detail>[^\n]+))?",
)
EXCEPTION_RE = re.compile(r"\b(?P<name>[A-Za-z][A-Za-z0-9_]*(?:Error|Exception))\b")
FILE_RE = re.compile(r"File\s+[\"'](?P<file>[^\"']+)[\"'](?:,\s*line\s+(?P<line>\d+))?", re.IGNORECASE)
LINE_RE = re.compile(r"\[line\s+(?P<line>\d+)\]", re.IGNORECASE)
UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.IGNORECASE)
ROUTE_RE = re.compile(
    r'"(?P<method>GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+'
    r'(?P<path>\S+)\s+HTTP/[^\"]+"\s+(?P<status>\d{3})',
    re.IGNORECASE,
)
CREATED_RUN_RE = re.compile(
    r"Created\s+(?P<kind>protocol|an empty)\s+run\s+[\"'](?P<run>[0-9a-f-]{20,})[\"']",
    re.IGNORECASE,
)
ARCHIVE_IP_RE = re.compile(r"(?<!\d)((?:\d{1,3}\.){3}\d{1,3})(?!\d)")
ARCHIVE_DATE_RE = re.compile(r"(?<!\d)(?P<date>20\d{6})(?:[-_](?P<clock>\d{6}))?(?!\d)")


def _clean_text(value: str) -> str:
    """Remove terminal control characters and collapse whitespace."""

    value = value.replace("\x00", " ").replace("\ufeff", "")
    return re.sub(r"\s+", " ", value).strip()


def _shorten(value: str, limit: int = MAX_OUTPUT_RAW) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _parse_fraction(value: str) -> int:
    fraction = value.replace(",", ".").partition(".")[2]
    if not fraction:
        return 0
    return int((fraction + "000000")[:6])


def _parse_clock(value: str) -> tuple[int, int, int, int]:
    base = value.replace(",", ".").split(".", 1)[0]
    hour, minute, second = (int(part) for part in base.split(":"))
    return hour, minute, second, _parse_fraction(value)


class _TimestampResolver:
    """Add years to syslog timestamps while handling a year rollover."""

    def __init__(self, year_hint: int | None) -> None:
        self.year_hint = year_hint or datetime.now(timezone.utc).year
        self.previous: datetime | None = None

    def resolve(self, month: int, day: int, clock: str) -> datetime:
        hour, minute, second, microsecond = _parse_clock(clock)
        year = self.year_hint
        candidate = datetime(year, month, day, hour, minute, second, microsecond)
        if self.previous is not None:
            # Journald output is chronological.  A large backward jump is a
            # Dec -> Jan rollover; a large forward jump is the inverse case
            # when an archive was collected shortly after New Year.
            if candidate < self.previous - timedelta(days=180):
                candidate = candidate.replace(year=candidate.year + 1)
            elif candidate > self.previous + timedelta(days=180):
                candidate = candidate.replace(year=candidate.year - 1)
        self.previous = candidate
        return candidate


def _year_hint_from_name(name: str, override: int | None = None) -> int | None:
    if override is not None:
        return override
    match = ARCHIVE_DATE_RE.search(name)
    if match:
        return int(match.group("date")[:4])
    return None


def _split_ident(ident: str) -> tuple[str, str | None]:
    match = IDENT_RE.match(ident.strip())
    if not match:
        return ident.strip(), None
    return match.group("process").strip(), match.group("pid")


def _parse_iso_stamp(value: str) -> datetime | None:
    normalized = value.replace(",", ".")
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    # Comparisons across files are easier with naive UTC-like values.  Robot
    # syslog timestamps are UTC in the downloaded bundles; retain the raw text
    # for callers that need the exact source representation.
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


@dataclass(slots=True)
class _ParsedHeader:
    timestamp: datetime | None
    timestamp_raw: str | None
    host: str
    process: str
    pid: str | None
    message: str


def _parse_header(line: str, resolver: _TimestampResolver) -> _ParsedHeader | None:
    line = line.lstrip("\ufeff")
    match = SYSLOG_RE.match(line)
    if match:
        timestamp = resolver.resolve(
            MONTHS[match.group("month").title()], int(match.group("day")), match.group("clock")
        )
        process, pid = _split_ident(match.group("ident"))
        raw_stamp = f"{match.group('month')} {int(match.group('day')):02d} {match.group('clock')}"
        return _ParsedHeader(timestamp, raw_stamp, match.group("host"), process, pid, match.group("message"))

    # Parse full ISO-8601 records before the more permissive year-prefixed
    # fallback so timezone offsets are normalized correctly.
    iso_match = ISO_RE.match(line)
    if iso_match:
        timestamp = _parse_iso_stamp(iso_match.group("stamp"))
        if timestamp is None:
            return None
        rest = iso_match.group("rest")
        if ":" in rest:
            ident, message = rest.split(":", 1)
            process, pid = _split_ident(ident)
            return _ParsedHeader(timestamp, iso_match.group("stamp"), "", process, pid, message.lstrip())
        return _ParsedHeader(timestamp, iso_match.group("stamp"), "", "", None, rest)

    year_match = YEAR_SYSLOG_RE.match(line)
    if year_match:
        clock = year_match.group("clock")
        hour, minute, second, microsecond = _parse_clock(clock)
        timestamp = datetime(
            int(year_match.group("year")),
            int(year_match.group("month")),
            int(year_match.group("day")),
            hour,
            minute,
            second,
            microsecond,
        )
        rest = year_match.group("rest")
        if ":" in rest:
            ident, message = rest.split(":", 1)
            process, pid = _split_ident(ident)
            return _ParsedHeader(timestamp, line.split(None, 1)[0], "", process, pid, message.lstrip())
        return _ParsedHeader(timestamp, line.split(None, 1)[0], "", "", None, rest)

    return None


@dataclass(slots=True)
class LogRecord:
    timestamp: datetime | None
    timestamp_raw: str | None
    host: str
    process: str
    pid: str | None
    message: str
    raw: str
    log_file: str
    line: int
    sequence: int


def iter_log_records(
    stream: Iterable[str],
    log_file: str,
    year_hint: int | None = None,
    line_counter: list[int] | None = None,
) -> Iterator[LogRecord]:
    """Yield timestamped records, joining continuation lines into ``raw``."""

    resolver = _TimestampResolver(year_hint)
    current_header: _ParsedHeader | None = None
    current_lines: list[str] = []
    current_line = 0
    sequence = 0

    def flush() -> LogRecord | None:
        nonlocal current_header, current_lines, current_line, sequence
        if current_header is None:
            return None
        sequence += 1
        raw = "\n".join(current_lines)
        if len(raw.encode("utf-8", "ignore")) > MAX_RECORD_BYTES:
            raw = raw[:MAX_RECORD_BYTES]
        record = LogRecord(
            timestamp=current_header.timestamp,
            timestamp_raw=current_header.timestamp_raw,
            host=current_header.host,
            process=current_header.process,
            pid=current_header.pid,
            message=current_header.message,
            raw=raw,
            log_file=log_file,
            line=current_line,
            sequence=sequence,
        )
        current_header = None
        current_lines = []
        current_line = 0
        return record

    for line_number, raw_line in enumerate(stream, 1):
        if line_counter is not None:
            line_counter[0] = line_number
        line = raw_line.rstrip("\r\n")
        header = _parse_header(line, resolver)
        if header is not None:
            previous = flush()
            if previous is not None:
                yield previous
            current_header = header
            current_lines = [line]
            current_line = line_number
        elif current_header is not None:
            current_lines.append(line)
    previous = flush()
    if previous is not None:
        yield previous


@dataclass(slots=True)
class RouteEvidence:
    timestamp: datetime | None
    method: str
    path: str
    status: int
    kind: str
    run_id: str | None
    log_file: str
    line: int


def _parse_route(record: LogRecord) -> RouteEvidence | None:
    if '"' not in record.raw or not re.search(
        r'"(?:GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s|created\s+(?:protocol|an empty)\s+run',
        record.raw,
        re.IGNORECASE,
    ):
        return None
    match = ROUTE_RE.search(record.raw)
    if not match:
        created = CREATED_RUN_RE.search(record.raw)
        if not created:
            return None
        created_kind = created.group("kind").casefold()
        return RouteEvidence(
            timestamp=record.timestamp,
            method="EVENT",
            path="/maintenance_runs" if created_kind == "an empty" else "/runs",
            status=201,
            kind="maintenance_run" if created_kind == "an empty" else "protocol_run",
            run_id=created.group("run"),
            log_file=record.log_file,
            line=record.line,
        )
    path = match.group("path")
    try:
        path = urlsplit(path).path or path
        status = int(match.group("status"))
    except ValueError:
        return None
    if path == "/runs" or path.startswith("/runs/"):
        kind = "protocol_run"
    elif path == "/maintenance_runs" or path.startswith("/maintenance_runs/"):
        kind = "maintenance_run"
    else:
        kind = "other"
    run_match = UUID_RE.search(path)
    return RouteEvidence(
        timestamp=record.timestamp,
        method=match.group("method").upper(),
        path=path,
        status=status,
        kind=kind,
        run_id=run_match.group(0) if run_match else None,
        log_file=record.log_file,
        line=record.line,
    )


def _is_framework_file(path: str) -> bool:
    lowered = path.casefold()
    if "hardware-testing" in lowered or "hardware_testing" in lowered:
        return False
    return any(
        marker in lowered
        for marker in (
            "/opt/opentrons-robot-server/",
            "/opt/opentrons-update-server/",
            "/usr/lib/",
            "/site-packages/",
            "/opentrons/protocols/execution/",
            "/opentrons/protocol_engine/",
        )
    )


def _extract_protocol_file(text: str) -> tuple[str | None, int | None]:
    if "file \"" not in text.casefold() and "file '" not in text.casefold():
        return None, None
    candidates: list[tuple[str, int | None]] = []
    for match in FILE_RE.finditer(text):
        path = match.group("file")
        if not path.lower().endswith((".py", ".json", ".zip")):
            continue
        if _is_framework_file(path):
            continue
        if path in {"<protocol>", "<string>"}:
            continue
        candidates.append((Path(path).name, int(match.group("line")) if match.group("line") else None))
    if candidates:
        return candidates[-1]
    return None, None


def _extract_protocol_name(text: str) -> str | None:
    if "protocol" not in text.casefold():
        return None
    patterns = (
        r"[\"']protocolName[\"']\s*:\s*[\"']([^\"']+)",
        r"\bprotocol[_ ]name\s*[:=]\s*[\"']?([^,\n\"']+)",
    )
    for pattern in patterns:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            return _clean_text(matches[-1].group(1))
    return None


def _heuristic_protocol_name(file_name: str | None) -> str | None:
    if not file_name:
        return None
    lowered = file_name.casefold()
    names = (
        ("gravimetric", "Gravimetric"),
        ("preheat", "Pre-heating"),
        ("photometric", "Photometric"),
        ("assembly", "Assembly QC"),
        ("leveling", "Leveling"),
        ("vacuum", "Vacuum module"),
        ("tip_overlap", "Tip overlap"),
        ("calibration", "Calibration"),
    )
    for marker, name in names:
        if marker in lowered:
            return name
    return None


@dataclass(slots=True)
class SourceIndex:
    root: Path | None = None
    file_names: dict[str, str] = field(default_factory=dict)
    protocol_names: dict[str, str] = field(default_factory=dict)
    hardware_paths: set[str] = field(default_factory=set)

    def lookup(self, file_name: str | None) -> tuple[bool, str | None, str | None]:
        if not file_name:
            return False, None, None
        key = file_name.casefold()
        path = self.file_names.get(key)
        if path is None:
            return False, None, None
        return (
            path.casefold() in self.hardware_paths,
            self.protocol_names.get(key),
            path,
        )


def resolve_source_root(explicit: Path | str | None = None) -> Path | None:
    if explicit is not None:
        explicit = Path(explicit).expanduser()
        return explicit.resolve() if explicit.is_dir() else None
    candidates: list[Path] = []
    # Include the misspelled path from the original request, then common local
    # checkout locations.  The analyzer remains fully functional without any
    # source checkout.
    candidates.extend(
        [
            Path.home() / "project" / "opentorns",
            Path.home() / "project" / "opentrons",
            Path.home() / "projects" / "opentorns",
            Path.home() / "projects" / "opentrons",
        ]
    )
    for candidate in candidates:
        if candidate is not None and candidate.is_dir():
            return candidate.resolve()
    return None


def build_source_index(root: Path | None) -> SourceIndex:
    index = SourceIndex(root=root)
    if root is None:
        return index

    # The relevant upstream package is hardware-testing.  Walk only source
    # directories and skip virtual environments/node_modules to keep startup
    # predictable on a full Opentrons checkout.
    roots: list[Path] = []
    for name in ("hardware-testing", "hardware_testing"):
        candidate = root / name
        if candidate.is_dir():
            roots.append(candidate)
    if not roots and root.name.casefold() in {"hardware-testing", "hardware_testing"}:
        roots.append(root)
    if not roots:
        return index

    skip_dirs = {".git", ".venv", "node_modules", "__pycache__", "dist", "build"}
    metadata_re = re.compile(
        r"metadata\s*=\s*\{(?:(?!\n\s*\}).){0,4000}?[\"']protocolName[\"']\s*:\s*[\"']([^\"']+)",
        re.IGNORECASE | re.DOTALL,
    )
    for source_root in roots:
        for directory, dir_names, file_names in os.walk(source_root):
            dir_names[:] = [name for name in dir_names if name not in skip_dirs]
            for file_name in file_names:
                if not file_name.casefold().endswith(".py"):
                    continue
                path = Path(directory) / file_name
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")[:128_000]
                    relative = path.relative_to(root).as_posix()
                except (OSError, ValueError):
                    continue
                key = file_name.casefold()
                metadata = metadata_re.search(text)
                # Prefer a path explicitly under hardware-testing when two
                # checkouts contain the same basename.
                if (
                    key not in index.file_names
                    or "hardware-testing" in relative.casefold()
                    or (key not in index.protocol_names and metadata is not None)
                ):
                    index.file_names[key] = relative
                    if metadata:
                        index.protocol_names[key] = _clean_text(metadata.group(1))
                if "hardware-testing" in relative.casefold() or "hardware_testing" in relative.casefold():
                    index.hardware_paths.add(relative.casefold())
    return index


@dataclass(slots=True)
class ErrorEvent:
    record: LogRecord
    trigger: str
    message: str
    category: str
    severity: str
    code: str | None = None
    code_name: str | None = None
    exception: str | None = None
    protocol_file: str | None = None
    protocol_line: int | None = None
    protocol_name: str | None = None
    run_id: str | None = None
    command_id: str | None = None
    run_kind: str = "unknown"
    test_type: str = "unknown"
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    observed_timestamp: datetime | None = None


def _known_exception_names(text: str) -> list[str]:
    names: list[str] = []
    for match in EXCEPTION_RE.finditer(text):
        name = match.group("name")
        if name.casefold() in EXCEPTION_DETAIL_NAMES:
            continue
        if name not in names:
            names.append(name)
    return names


def _code_match_score(match: re.Match[str]) -> tuple[int, int]:
    code = match.group("code")
    score = 0
    if code in ERROR_CODE_NAMES:
        score += 10
    if code != "4000":
        score += 8
    if match.group("exception"):
        score += 2
    return score, match.start()


def _strip_nested_detail(detail: str) -> str:
    detail = _clean_text(detail)
    # Wrapper errors often format as ``ProtocolCommandFailedError:
    # CommandTimedOutError: ...``.  Keep the actionable innermost message.
    for _ in range(3):
        nested = re.match(r"[A-Za-z][A-Za-z0-9_]*(?:Error|Exception)(?:\s+\[line\s+\d+\])?\s*:\s*(.+)$", detail)
        if not nested:
            break
        detail = _clean_text(nested.group(1))
    return detail


def _extract_tip_state(text: str) -> str | None:
    match = re.search(r"Expected tip state\s+[^.\n]+(?:\.|$)", text, re.IGNORECASE)
    return _clean_text(match.group(0)) if match else None


def _extract_structured_command_error(record: LogRecord) -> dict[str, Any] | None:
    """Read Robot Server's persisted ``command_error`` SQL debug record.

    Newer Robot Server versions log a failed command twice: once from the API
    execution path and once while persisting the run.  The latter contains a
    compact ``errorType``/``errorCode``/``detail`` JSON object and is useful
    when the API traceback was truncated from an archive.
    """

    if Path(record.log_file).name != "server.log":
        return None
    text = record.raw
    has_error_payload = bool(
        re.search(r"[\"']error(?:type|code|info|detail)[\"']\s*[:=]", text, re.IGNORECASE)
    )
    has_command_context = bool(
        re.search(r"[\"']commandType[\"']\s*[:=]|command_error", text, re.IGNORECASE)
    )
    command_row = bool(
        re.search(
            r"\(\s*['\"]?[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}['\"]?\s*,\s*\d+\s*,\s*['\"]?[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            text,
            re.IGNORECASE,
        )
    )
    # A run-state JSON blob also contains ``status=failed`` and nested error
    # fields, but it is not a command occurrence and is commonly logged much
    # later while the UI polls the database.  Require command context here so
    # that blob cannot become the bundle's "last error".
    if not has_error_payload or not has_command_context or (not command_row and "command_error" not in text.casefold()) or not re.search(
        r"(?:command_status|status)\s*['\"]?\s*[:=,]\s*['\"]?failed\b|,\s*['\"]failed['\"]",
        text,
        re.IGNORECASE,
    ):
        return None
    code_match = re.search(r"[\"']errorCode[\"']\s*:\s*[\"']?(\d{3,5})", text, re.IGNORECASE)
    type_match = re.search(r"[\"']errorType[\"']\s*:\s*[\"']([^\"']+)", text, re.IGNORECASE)
    detail_match = re.search(r"[\"']detail[\"']\s*:\s*[\"']([^\"']*)", text, re.IGNORECASE)
    if not (code_match or type_match or detail_match):
        return None
    code = code_match.group(1) if code_match else None
    exception = type_match.group(1) if type_match else None
    code_name = ERROR_CODE_NAMES.get(code) if code else None
    if exception and exception.casefold() in EXCEPTION_CODES:
        inferred_code, inferred_name = EXCEPTION_CODES[exception.casefold()]
        code = code or inferred_code
        code_name = code_name or inferred_name
    detail = _clean_text(detail_match.group(1)) if detail_match else "Command failed"
    if not detail or detail.casefold() == "none":
        detail = "Command failed"
    uuids = UUID_RE.findall(text)
    embedded_timestamp = None
    timestamp_matches = list(re.finditer(
        r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?",
        text,
    ))
    if timestamp_matches:
        error_position = text.casefold().find("\"errortype\"")
        before_error = [match for match in timestamp_matches if error_position < 0 or match.start() <= error_position]
        chosen = (before_error or timestamp_matches)[-1]
        embedded_timestamp = _parse_iso_stamp(chosen.group(0))
    return {
        "trigger": "structured_command_failure",
        "message": _shorten(detail, 800),
        "category": _error_category(code, code_name, exception, detail, "structured_command_failure", None),
        "severity": "error",
        "code": code,
        "code_name": code_name,
        "exception": exception,
        "protocol_file": None,
        "protocol_line": None,
        "protocol_name": None,
        "command_id": uuids[1] if len(uuids) > 1 else (uuids[0] if uuids else None),
        "run_id": uuids[0] if uuids else None,
        "event_timestamp": embedded_timestamp,
    }


def _extract_error_info(record: LogRecord) -> tuple[dict[str, Any], str] | None:
    text = record.raw
    lower = text.casefold()
    if not any(
        marker in lower
        for marker in ("error", "exception", "failed", "failure", "timeout", "timed out", "fatal", "critical", "traceback")
    ):
        return None
    route = _parse_route(record)

    # Explicitly suppress known background noise.  These checks happen before
    # broad ``failed``/``exception`` matching below.
    if "stop_requested" in lower and not re.search(
        r"exception raised by protocol|execution of .* failed|homing failed|error\s+\d{3,5}",
        lower,
    ):
        return None
    structured_error = re.search(
        r"error_code[^=\n]*=\s*(?:[^()=]+\()?\s*(?:value\s*=\s*)?(?P<name>[a-z][a-z0-9_]*)",
        lower,
    )
    structured_severity = re.search(
        r"severity[^=\n]*=\s*(?:[^()=]+\()?\s*(?:value\s*=\s*)?(?P<severity>[a-z][a-z0-9_]*)",
        lower,
    )
    if structured_error and structured_error.group("name") in {
        "stop_requested",
        "estop_released",
        "ok",
    } and (not structured_severity or structured_severity.group("severity") in {"warning", "ok", "info"}):
        return None
    if "total_error_count" in lower or "overpressure_error_count" in lower:
        return None
    if record.log_file.casefold().endswith("update_server.log") and re.search(
        r"hostnamectl|exception serving|gethostname", lower
    ):
        return None
    if record.log_file.casefold().endswith("touchscreen.log") and re.search(
        r"dbus/|maxlistenersexceeded|could not fetch manifest|system.?update|no video device|"
        r"failed to fetch extension|devtools extensions|sentry logger|"
        r"unexpected handlelabware|expected to find labware info|unknown adapter|"
        r"failed to read (?:cmdline|memory info)|failed to get process tree|"
        r"\bmonitor\b.*\berror\b|enoent|"
        r"(?:opentrons-(?:robot-app|loading)\.service|main process exited|"
        r"failed to start .*\.service|failed with result 'exit-code')",
        lower,
    ):
        return None
    if "failed to disconnect from mqtt broker" in lower:
        return None
    if "publishernotifier: exception in callback" in lower and not re.search(
        r"error\s+\d{3,5}|motionfailed|communicationerror|commandtimed|tipnotattached",
        lower,
    ):
        return None
    if route is not None:
        if route.status == 422 and ("/health" in route.path or "opentrons-version" in lower):
            return None
        if route.status == 404 and route.path.endswith("/maintenance_runs/current_run"):
            return None
    # Robot Server writes the structured ``Error response`` line separately
    # from the access-log line.  A bare 404/422 therefore has no reliable
    # endpoint context and is almost always an expected UI poll (for example,
    # checking whether a maintenance run exists).  Do not let it obscure a
    # real protocol or hardware failure later in the bundle.
    if re.search(r"error response:\s*404\b", lower):
        return None
    if re.search(r"error response:\s*422\b", lower):
        return None
    if re.search(r"error response:\s*4\d{2}\b", lower):
        return None

    structured = _extract_structured_command_error(record)
    if structured is not None:
        return structured, "structured_command_failure"

    trigger = None
    trigger_patterns = (
        ("protocol_exception", r"exception raised by protocol|exceptioninprotocolerror"),
        ("command_failed", r"execution of\s+[0-9a-f-]{20,}\s+failed"),
        ("post_run_failure", r"exception during post-run finish steps"),
        ("hardware_failure", r"homing failed|motion failed|motor position timed out|sensor read .* timed out|read motor status timed out|update motor position estimation timed out|clear move group failed"),
        ("error_response", r"error response:\s*[45]\d{2}"),
        (
            "received_error",
            r"\breceived error\b|errorcode\.timeout|"
            r"errormessagepayload.*(?:unrecoverable|fatal|errorseverity)",
        ),
        (
            "explicit_error",
            r"\b(?:fatal|critical)\b|\b(?:failed|failure)\b|\b(?:timed out|timeout)\b|"
            r"^\s*(?:error|fatal|critical)\s*[:\-]",
        ),
        ("exception", r"\b[A-Za-z][A-Za-z0-9_]*(?:Error|Exception)\b"),
        ("error_code", r"\berror\s+\d{3,5}\b"),
    )
    for name, pattern in trigger_patterns:
        if re.search(pattern, lower):
            trigger = name
            break
    if trigger is None:
        return None

    # SQL/debug continuation lines in server.log can contain words such as
    # ``status=failed`` or an embedded error code without being a log failure.
    # For that file, broad keyword matches are valid only when the record's
    # timestamped header itself is an error/traceback line.
    if Path(record.log_file).name == "server.log" and trigger in {
        "explicit_error",
        "exception",
        "error_code",
    } and not re.search(
        r"error response|traceback|error\s+\d{3,5}|\b(exception|failed|failure|fatal|critical)\b",
        record.message,
        re.IGNORECASE,
    ):
        return None
    if Path(record.log_file).name == "server.log" and re.match(
        r"\s*(?:\[cached since|\[generated in|begin(?:\s|$)|commit(?:\s|$)|rollback(?:\s|$)|"
        r"select\b|insert\s+into\b|update\s+\w+\s+set\b|delete\s+from\b|\[raw sql\])",
        record.message,
        re.IGNORECASE,
    ):
        return None

    code_matches = list(CODE_RE.finditer(text))
    selected_code: re.Match[str] | None = None
    if code_matches:
        selected_code = max(code_matches, key=_code_match_score)

    exceptions = _known_exception_names(text)
    selected_exception: str | None = None
    # Prefer a specific known exception over generic wrappers.  The last
    # occurrence is normally the terminal exception line in a traceback.
    for name in reversed(exceptions):
        if name.casefold() in EXCEPTION_CODES:
            selected_exception = name
            break
    if selected_exception is None and exceptions:
        selected_exception = exceptions[-1]

    code: str | None = selected_code.group("code") if selected_code else None
    code_name: str | None = (
        selected_code.group("name").upper() if selected_code and selected_code.group("name") else None
    )
    explicit_exception = selected_code.group("exception") if selected_code else None
    exception = selected_exception or explicit_exception

    # A 4000 wrapper around a specific exception should expose the specific
    # code.  This is what turns ``GENERAL_ERROR: CommandTimedOutError`` into
    # the useful 1004/COMMAND_TIMED_OUT result.
    if selected_exception and selected_exception.casefold() in EXCEPTION_CODES:
        exception_code, exception_name = EXCEPTION_CODES[selected_exception.casefold()]
        if code is None or code == "4000" or code_name in {None, "GENERAL_ERROR"}:
            code, code_name = exception_code, exception_name
    if code is not None and code_name is None:
        code_name = ERROR_CODE_NAMES.get(code)
    if exception is None and code_name in ERROR_CODE_NAMES.values():
        exception = CODE_EXCEPTIONS.get(code)

    detail = selected_code.group("detail") if selected_code else None
    if detail:
        detail = _strip_nested_detail(detail)
    elif selected_code:
        trailing = text[selected_code.end() :].lstrip(" \t:-")
        trailing = re.sub(r"^[A-Za-z][A-Za-z0-9_]*\s*:\s*", "", trailing)
        if trailing:
            detail = _strip_nested_detail(trailing.splitlines()[0])

    # Prefer the terminal exception line's detail if the code match only
    # captured a generic wrapper.
    if selected_exception:
        exception_line_detail = None
        for line in reversed(text.splitlines()):
            match = re.search(
                rf"\b{re.escape(selected_exception)}\b\s*:\s*(.+)$", line, re.IGNORECASE
            )
            if match:
                exception_line_detail = _strip_nested_detail(match.group(1))
                break
        if exception_line_detail and (
            not detail or detail.casefold() in {"", "general error"} or detail.casefold().startswith(selected_exception.casefold())
        ):
            detail = exception_line_detail

    tip_state = _extract_tip_state(text)
    if tip_state and (code == "3005" or (exception and "tip" in exception.casefold())):
        detail = tip_state

    # Human-readable fallbacks for lines that do not carry an Error NNNN code.
    if not detail:
        if route is not None and route.status >= 400:
            response_match = re.search(r"Error response:\s*\d{3}\s*-?\s*(.*)", text, re.IGNORECASE)
            detail = _clean_text(response_match.group(1)) if response_match else _clean_text(record.message)
        else:
            special = re.search(
                r"(?:Sensor Read from [^\n]+ timed out|Motor position timed out|Read motor status timed out[^\n]*|received error[^\n]*|Stop request failed[^\n]*)",
                text,
                re.IGNORECASE,
            )
            detail = _clean_text(special.group(0)) if special else _clean_text(record.message)
    detail = _shorten(detail or "Unspecified error", 800)

    if code is None and re.search(r"(?:timed out|timeout|communication)", detail, re.IGNORECASE):
        code, code_name = "1004", "COMMAND_TIMED_OUT"

    # Firmware/CAN messages sometimes carry an enum instead of a numeric
    # Opentrons error code.  Preserve that enum so an e-stop is not reduced to
    # the unhelpful generic word "error".
    if structured_error and structured_error.group("name") not in {"stop_requested", "ok", "estop_released"}:
        enum_name = structured_error.group("name")
        code = code or enum_name.upper()
        code_name = code_name or FIRMWARE_ERROR_NAMES.get(enum_name, enum_name.upper())
        if not detail or detail.casefold().startswith("received error message"):
            detail = f"Firmware error message: {enum_name}"

    category = _error_category(code, code_name, exception, detail, trigger, route)
    severity = _error_severity(text, trigger)
    protocol_file, protocol_line = _extract_protocol_file(text)
    protocol_name = _extract_protocol_name(text)
    uuids = UUID_RE.findall(text)
    command_id = None
    command_match = re.search(
        r"Execution of\s+(?P<id>[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\s+failed",
        text,
        re.IGNORECASE,
    )
    if command_match:
        command_id = command_match.group("id")
    if protocol_line is None:
        line_match = LINE_RE.search(text)
        protocol_line = int(line_match.group("line")) if line_match else None

    info: dict[str, Any] = {
        "trigger": trigger,
        "message": detail,
        "category": category,
        "severity": severity,
        "code": code,
        "code_name": code_name,
        "exception": exception,
        "protocol_file": protocol_file,
        "protocol_line": protocol_line,
        "protocol_name": protocol_name,
        "command_id": command_id,
    }
    # ``uuids`` can include a run ID in an embedded route or traceback.  The
    # route correlation pass below will replace this with the correct run ID.
    if uuids and command_id is None and trigger == "command_failed":
        info["command_id"] = uuids[-1]
    return info, trigger


def _error_category(
    code: str | None,
    code_name: str | None,
    exception: str | None,
    message: str,
    trigger: str,
    route: RouteEvidence | None,
) -> str:
    if trigger == "error_response":
        return "server_error"
    try:
        number = int(code) if code else None
    except ValueError:
        number = None
    if number is not None:
        if 1000 <= number < 2000:
            return "hardware_communication"
        if 2000 <= number < 3000:
            return "motion_control"
        if 3000 <= number < 3100:
            if number == 3013:
                return "firmware"
            return "instrument_interaction"
        if 4000 <= number < 5000:
            if exception and exception.casefold() in {"runstoppederror", "executioncancellederror"}:
                return "protocol_cancelled"
            if number == 4010:
                return "runtime_parameter"
            return "protocol_execution"
    text = " ".join((code_name or "", exception or "", message)).casefold()
    if "estop" in text or "e-stop" in text:
        return "hardware_safety"
    if "firmware" in text:
        return "firmware"
    if "tip" in text:
        return "instrument_interaction"
    if any(word in text for word in ("motion", "homing", "motor", "encoder", "move group")):
        return "motion_control"
    if any(word in text for word in ("timeout", "timed out", "communication", "sensor")):
        return "hardware_communication"
    if "cancel" in text or "stopped" in text:
        return "protocol_cancelled"
    if trigger == "exception":
        return "application_exception"
    return "application_error"


def _error_severity(text: str, trigger: str) -> str:
    lower = text.casefold()
    if "fatal" in lower or "critical" in lower:
        return "critical"
    if "warning" in lower and trigger not in {"protocol_exception", "command_failed", "hardware_failure", "post_run_failure"}:
        return "warning"
    return "error"


def _event_sort_key(event: ErrorEvent) -> tuple[datetime, int]:
    return event.record.timestamp or datetime.min, event.record.sequence


def _nearest_route(
    event: ErrorEvent,
    routes: Sequence[RouteEvidence],
    *,
    include_other: bool = False,
) -> RouteEvidence | None:
    if event.record.timestamp is None:
        return None
    # Access-log records are useful context, but a route from a different run
    # several minutes away is not evidence that an API traceback belongs to
    # that run.  Keep the window tight for service/API records; server access
    # records themselves can use the wider window when correlating a nearby
    # structured error response.
    window = (
        ROUTE_CONTEXT_WINDOW
        if Path(event.record.log_file).name == "server.log"
        else timedelta(minutes=2)
    )
    candidates = [
        route
        for route in routes
        if route.timestamp is not None
        and abs(route.timestamp - event.record.timestamp) <= window
        and (include_other or route.kind != "other")
    ]
    if not candidates:
        return None
    # Prefer a route before the error, then the closest route.  This avoids a
    # later run's first polling request stealing an earlier failure.
    return min(
        candidates,
        key=lambda route: (
            0 if route.timestamp <= event.record.timestamp else 1,
            abs(route.timestamp - event.record.timestamp),
        ),
    )


def _classify_event(
    event: ErrorEvent,
    routes: Sequence[RouteEvidence],
    hints: Sequence[tuple[datetime | None, str, str | None, str | None, str | None]],
    source_index: SourceIndex,
    archive_hardware_hint: bool,
) -> None:
    route = _nearest_route(event, routes)
    text = " ".join(
        value
        for value in (event.record.raw, event.protocol_file, event.protocol_name)
        if value
    )
    lower = text.casefold()
    protocol_traceback = bool(
        re.search(r"exception raised by protocol|exceptioninprotocolerror|protocol_engine", lower)
    )
    # A protocol traceback is authoritative.  The server log often contains
    # unrelated polling requests around the same second, especially while the
    # UI is recovering from a failed run.
    if route is not None and route.kind != "other":
        # Keep a protocol traceback's execution kind authoritative, but still
        # borrow the nearby run UUID from the access log.  The traceback often
        # contains ``protocol_engine`` framework paths, so treating it as a
        # reason to discard the route would lose useful correlation metadata.
        if not protocol_traceback or Path(event.record.log_file).name == "server.log":
            event.run_kind = route.kind
        elif event.run_kind == "unknown":
            event.run_kind = "protocol_run"
        if route.run_id and event.run_id is None:
            event.run_id = route.run_id
        event.evidence.append(f"{route.log_file}:{route.line} {route.method} {route.path} ({route.status})")

    # Recover the protocol file/name from the nearest user traceback.  This is
    # useful for later low-level records such as a sensor timeout.
    if event.protocol_file is None and event.record.timestamp is not None:
        prior_hints = [
            hint
            for hint in hints
            if hint[0] is not None
            and hint[0] <= event.record.timestamp
            and event.record.timestamp - hint[0] <= PROTOCOL_CONTEXT_WINDOW
            and (not event.record.pid or not hint[1] or event.record.pid == hint[1])
            and hint[2]
        ]
        if prior_hints:
            hint = max(prior_hints, key=lambda value: value[0] or datetime.min)
            event.protocol_file = hint[2]
            event.protocol_name = event.protocol_name or hint[3]
            event.evidence.append("nearby protocol traceback")

    if event.protocol_file is None:
        distinct_files = {
            (hint[2], hint[3])
            for hint in hints
            if hint[2]
        }
        if len(distinct_files) == 1:
            event.protocol_file, hinted_name = next(iter(distinct_files))
            event.protocol_name = event.protocol_name or hinted_name
            event.evidence.append("single protocol file in archive")

    source_hardware, source_name, source_path = source_index.lookup(event.protocol_file)
    if source_name and not event.protocol_name:
        event.protocol_name = source_name
    if not event.protocol_name:
        event.protocol_name = _heuristic_protocol_name(event.protocol_file)
    if source_hardware:
        event.evidence.append(f"hardware-testing source: {source_path}")

    hardware_error_context = event.category in {
        "hardware_communication",
        "motion_control",
        "firmware",
        "instrument_interaction",
        "hardware_safety",
    }
    hardware_archive_context = (
        archive_hardware_hint
        and Path(event.record.log_file).name in {"api.log", "server.log"}
        and hardware_error_context
    )

    if event.run_kind == "unknown":
        if protocol_traceback:
            event.run_kind = "protocol_run"
            event.evidence.append("protocol execution traceback")
        elif re.search(r"command[_ ]?intent[^\n]*(?:protocol|PROTOCOL)", lower):
            event.run_kind = "protocol_run"
            event.evidence.append("CommandIntent.PROTOCOL")
        elif re.search(r"command[_ ]?intent[^\n]*(?:setup|SETUP)", lower):
            event.run_kind = "maintenance_run"
            event.evidence.append("CommandIntent.SETUP")
        elif re.search(r"maintenance[_ ]run|/maintenance_runs", lower):
            event.run_kind = "maintenance_run"
            event.evidence.append("maintenance-run marker")
        elif re.search(
            r"hardware[_ -]?testing|opentrons[_ -]?hardware",
            f"{event.record.process} {event.record.message}".casefold(),
        ):
            event.run_kind = "standalone"
            event.evidence.append("direct hardware-testing process")
        elif event.trigger in {"protocol_exception", "command_failed"}:
            event.run_kind = "protocol_run"
            event.evidence.append("protocol command failure marker")
        elif event.protocol_file and Path(event.record.log_file).name in {"api.log", "server.log"}:
            event.run_kind = "protocol_run"
            event.evidence.append("protocol file context")

    marker_text = " ".join(
        value
        for value in (
            event.protocol_file,
            event.protocol_name,
            event.record.process if event.protocol_file or event.protocol_name else "",
            # Keep explicit repository paths as evidence, but avoid scanning
            # every framework traceback path for generic words like pipette.
            "hardware-testing" if "hardware-testing" in lower else "",
            "production_qc" if "production_qc" in lower else "",
        )
        if value
    ).casefold()
    explicit_protocol = bool(PROTOCOL_TEST_MARKER.search(marker_text))
    hardware_marker = source_hardware or any(marker in marker_text for marker in HARDWARE_MARKERS)
    if explicit_protocol:
        event.test_type = "protocol_test"
        event.confidence = 0.96
        event.evidence.append("explicit protocol-test name")
    elif event.run_kind == "maintenance_run":
        event.test_type = "hardware_test"
        event.confidence = 0.99
        event.evidence.append("maintenance runs are hardware/manual commands")
    elif hardware_marker:
        event.test_type = "hardware_test"
        event.confidence = 0.92 if source_hardware else 0.84
        event.evidence.append("hardware-testing/production test marker")
    elif hardware_archive_context and not event.protocol_file:
        # Low-level command failures (for example TipNotAttachedError) often
        # have no user traceback of their own.  If the same bundle contains
        # only hardware-testing protocol traces, retain that family instead of
        # falling back to the generic protocol label.
        event.test_type = "hardware_test"
        event.confidence = 0.68
        event.evidence.append("archive contains hardware-testing protocol traces")
    elif event.run_kind == "protocol_run":
        event.test_type = "protocol_test"
        event.confidence = 0.82
        event.evidence.append("ordinary protocol run")
    else:
        event.test_type = "unknown"
        event.confidence = 0.35

    if event.run_kind == "unknown" and event.test_type == "hardware_test":
        event.evidence.append("execution kind not present in downloaded server log")
    event.evidence = list(dict.fromkeys(event.evidence))[:8]


def _noise_key(record: LogRecord) -> str:
    lower = record.raw.casefold()
    if "stop_requested" in lower:
        return "stop_requested warning"
    if "hostnamectl" in lower:
        return "update-server hostnamectl"
    if "dbus/" in lower:
        return "touchscreen D-Bus"
    if "opentrons-version" in lower and "422" in lower:
        return "health request missing API version"
    if "maintenance_runs/current_run" in lower and "404" in lower:
        return "no active maintenance run"
    if "total_error_count" in lower:
        return "motor usage counter"
    return "filtered background message"


def _deduplicate_events(events: Sequence[ErrorEvent]) -> list[ErrorEvent]:
    """Merge exact duplicate CAN/serial/API observations without losing time."""

    by_key: dict[tuple[Any, ...], ErrorEvent] = {}
    source_priority = {"api.log": 4, "server.log": 3, "serial.log": 2, "can_bus.log": 2}
    for event in events:
        stamp = event.record.timestamp.isoformat() if event.record.timestamp else None
        key = (stamp, event.code, event.message.casefold(), event.trigger)
        previous = by_key.get(key)
        if previous is None:
            by_key[key] = event
            continue
        previous_name = Path(previous.record.log_file).name
        current_name = Path(event.record.log_file).name
        if source_priority.get(current_name, 1) > source_priority.get(previous_name, 1):
            by_key[key] = event
    return sorted(by_key.values(), key=_event_sort_key)


def _event_to_dict(event: ErrorEvent, include_raw: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "trigger": event.trigger,
        "timestamp": _format_timestamp(event.record.timestamp),
        "time": _format_timestamp(event.record.timestamp),
        "timestamp_raw": event.record.timestamp_raw,
        "log_file": event.record.log_file,
        "line": event.record.line,
        "source": Path(event.record.log_file).name,
        "severity": event.severity,
        "reason": event.message,
        "message": event.message,
        "error_reason": event.message,
        "error_category": event.category,
        "category": event.category,
        "error_code": event.code,
        "code": event.code,
        "code_name": event.code_name,
        "error_type": event.exception,
        "exception": event.exception,
        "failure_domain": event.category,
        "protocol_file": event.protocol_file,
        "protocol_line": event.protocol_line,
        "protocol_name": event.protocol_name,
        "run_id": event.run_id,
        "command_id": event.command_id,
        "run_kind": event.run_kind,
        "execution_type": event.run_kind,
        "test_type": event.test_type,
        "test_type_label": _test_type_label(event.test_type),
        "test_kind": event.test_type.removesuffix("_test") if event.test_type.endswith("_test") else event.test_type,
        "test_family": event.test_type,
        "test_family_code": "hardware_testing" if event.test_type == "hardware_test" else event.test_type,
        "confidence": round(event.confidence, 2),
        "evidence": list(event.evidence),
    }
    if event.observed_timestamp is not None and event.observed_timestamp != event.record.timestamp:
        result["observed_timestamp"] = _format_timestamp(event.observed_timestamp)
    if include_raw:
        result["raw"] = _shorten(event.record.raw, MAX_OUTPUT_RAW)
    return result


def _format_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    # The robot log bundles use UTC (the source's API timestamps are also UTC),
    # but retain the raw syslog timestamp separately for auditability.
    return value.isoformat(timespec="microseconds") + "Z"


def _test_type_label(value: str) -> str:
    return {
        "protocol_test": "协议测试",
        "hardware_test": "hardware测试",
        "unknown": "未知",
    }.get(value, value)


def _archive_ip(path: Path) -> str | None:
    match = ARCHIVE_IP_RE.search(path.name)
    return match.group(1) if match else None


def _source_streams(path: Path) -> Iterator[tuple[str, TextIO, int | None]]:
    """Yield ``(member_name, text_stream, size)`` for a bundle or log file."""

    if path.suffix.casefold() == ".zip":
        archive = zipfile.ZipFile(path)
        try:
            infos = [
                info
                for info in archive.infolist()
                if not info.is_dir() and info.filename.casefold().endswith(".log")
            ]
            if not infos:
                raise ValueError(f"ZIP does not contain .log files: {path}")
            for info in sorted(infos, key=lambda item: item.filename.casefold()):
                binary = archive.open(info, "r")
                text = io.TextIOWrapper(binary, encoding="utf-8", errors="replace")
                try:
                    yield info.filename, text, info.file_size
                finally:
                    text.close()
        finally:
            archive.close()
        return

    if path.is_file():
        binary = path.open("rb")
        text = io.TextIOWrapper(binary, encoding="utf-8", errors="replace")
        try:
            yield path.name, text, path.stat().st_size
        finally:
            text.close()
        return

    raise FileNotFoundError(path)


@dataclass(slots=True)
class _AnalysisAccumulator:
    events: list[ErrorEvent] = field(default_factory=list)
    routes: list[RouteEvidence] = field(default_factory=list)
    hints: list[tuple[datetime | None, str, str | None, str | None, str | None]] = field(default_factory=list)
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    robot_name: str | None = None
    hosts: Counter[str] = field(default_factory=Counter)
    file_stats: dict[str, dict[str, int]] = field(default_factory=dict)
    ignored: Counter[str] = field(default_factory=Counter)
    hardware_error_state_timestamp: datetime | None = None


def _update_time_range(accumulator: _AnalysisAccumulator, timestamp: datetime | None) -> None:
    if timestamp is None:
        return
    if accumulator.first_timestamp is None or timestamp < accumulator.first_timestamp:
        accumulator.first_timestamp = timestamp
    if accumulator.last_timestamp is None or timestamp > accumulator.last_timestamp:
        accumulator.last_timestamp = timestamp


def _archive_classification(events: Sequence[ErrorEvent]) -> tuple[str, str, float, list[str]]:
    if not events:
        return "unknown", "unknown", 0.0, []
    latest = max(events, key=_event_sort_key)
    return latest.test_type, latest.run_kind, latest.confidence, latest.evidence


def _is_background_http_error(event: ErrorEvent, routes: Sequence[RouteEvidence]) -> bool:
    """Identify startup/UI health responses written as bare Error response lines."""

    if event.trigger != "error_response":
        return False
    if event.record.timestamp is None:
        return False
    # The structured error line and its access-log line are adjacent, but a
    # busy UI may issue unrelated requests in the surrounding minute.  Look
    # for a health/maintenance poll within a few seconds and require the same
    # response class when possible.
    nearby = [
        route
        for route in routes
        if route.timestamp is not None
        and abs(route.timestamp - event.record.timestamp) <= timedelta(seconds=3)
    ]
    return any(
        route.path in {"/health", "/maintenance_runs/current_run"}
        and route.status >= 400
        for route in nearby
    )


def analyze_archive(
    path: str | Path,
    *,
    source_index: SourceIndex | None = None,
    source_root: Path | None = None,
    year: int | None = None,
    all_errors: bool = False,
) -> dict[str, Any]:
    """Analyze one ZIP or one standalone log file and return a JSON object."""

    archive_path = Path(path).expanduser().resolve()
    if source_index is None:
        source_index = build_source_index(resolve_source_root(source_root))
    accumulator = _AnalysisAccumulator()
    year_hint = _year_hint_from_name(archive_path.name, year)

    for member, stream, size in _source_streams(archive_path):
        stats = accumulator.file_stats.setdefault(member, {"lines": 0, "records": 0, "bytes": size or 0})
        # ``iter_log_records`` exposes physical line numbers; count lines from
        # the stream as records are consumed without loading the whole file.
        line_counter = [0]
        for record in iter_log_records(
            stream,
            member,
            year_hint=year_hint,
            line_counter=line_counter,
        ):
            stats["records"] += 1
            stats["lines"] = max(stats["lines"], record.line)
            _update_time_range(accumulator, record.timestamp)
            if re.search(r"StatusBarState\.HARDWARE_ERROR", record.raw, re.IGNORECASE):
                accumulator.hardware_error_state_timestamp = record.timestamp
            if record.host:
                accumulator.hosts[record.host] += 1
            robot_match = re.search(r"\bRobot Name:\s*([^\s]+)", record.raw, re.IGNORECASE)
            if robot_match:
                accumulator.robot_name = _clean_text(robot_match.group(1))

            route = _parse_route(record)
            if route is not None:
                accumulator.routes.append(route)

            protocol_file, protocol_line = _extract_protocol_file(record.raw)
            protocol_name = _extract_protocol_name(record.raw)
            if protocol_file and Path(member).name in {"api.log", "server.log"}:
                accumulator.hints.append(
                    (record.timestamp, record.pid or "", protocol_file, protocol_name, record.process)
                )

            extracted = _extract_error_info(record)
            if extracted is None:
                # This counter intentionally only counts messages that contain
                # a recognizable noise marker; ordinary info records are not
                # errors and need no accounting.
                if re.search(
                    r"stop_requested|total_error_count|hostnamectl|dbus/|opentrons-version.*422|"
                    r"maintenance_runs/current_run.*404|error response:\s*4\d{2}",
                    record.raw,
                    re.IGNORECASE,
                ):
                    accumulator.ignored[_noise_key(record)] += 1
                continue
            info, trigger = extracted
            event = ErrorEvent(
                record=record,
                trigger=trigger,
                message=info["message"],
                category=info["category"],
                severity=info["severity"],
                code=info["code"],
                code_name=info["code_name"],
                exception=info["exception"],
                protocol_file=info["protocol_file"],
                protocol_line=info["protocol_line"],
                protocol_name=info["protocol_name"],
                run_id=info.get("run_id"),
                command_id=info["command_id"],
            )
            # Persisted command rows are often logged several minutes after
            # execution.  Their embedded ``createdAt`` is the occurrence time
            # and must win when choosing the last error.
            if info.get("event_timestamp") is not None:
                event.observed_timestamp = event.record.timestamp
                event.record.timestamp = info["event_timestamp"]
            accumulator.events.append(event)

        stats["lines"] = max(stats["lines"], line_counter[0])

    events = _deduplicate_events(accumulator.events)
    background_http_events = [
        event for event in events if _is_background_http_error(event, accumulator.routes)
    ]
    if background_http_events:
        for event in background_http_events:
            accumulator.ignored["background health response"] += 1
        events = [event for event in events if event not in background_http_events]
    archive_hardware_hint = any(
        any(marker in " ".join(str(value or "") for value in hint).casefold() for marker in HARDWARE_MARKERS)
        for hint in accumulator.hints
    )
    for event in events:
        _classify_event(
            event,
            accumulator.routes,
            accumulator.hints,
            source_index,
            archive_hardware_hint,
        )

    # Re-sort after classification; deduplication happened before context
    # inference so source/API duplicates cannot perturb the selected error.
    events.sort(key=_event_sort_key)
    test_events = [
        event
        for event in events
        if event.test_type != "unknown"
        or event.category not in {"application_error", "application_exception", "server_error"}
    ]
    selected = test_events[-1] if test_events else (events[-1] if events else None)
    last_observed = events[-1] if events else None
    test_type, run_kind, confidence, evidence = _archive_classification(events)
    if selected is not None:
        # The selected event's context is authoritative after nearest-route
        # correlation, even if an earlier event belonged to another run.
        test_type, run_kind, confidence, evidence = (
            selected.test_type,
            selected.run_kind,
            selected.confidence,
            selected.evidence,
        )

    output_errors = events if all_errors else events[-MAX_ERRORS_IN_DEFAULT_OUTPUT:]
    error_dicts = [_event_to_dict(event) for event in output_errors]
    related: list[dict[str, Any]] = []
    root_cause: dict[str, Any] | None = None
    if selected is not None:
        nearby = [
            event
            for event in events
            if event is not selected
            and event.record.timestamp is not None
            and selected.record.timestamp is not None
            and abs(event.record.timestamp - selected.record.timestamp) <= RELATED_ERROR_WINDOW
        ]
        related = [_event_to_dict(event, include_raw=False) for event in nearby[-6:]]
        cluster = [selected, *nearby]
        # A specific non-wrapper code is a better root-cause hint than a
        # generic 4000 wrapper or a command-level duplicate.
        root_cause_event = min(
            cluster,
            key=lambda event: (
                0 if event.code and event.code != "4000" else 1,
                0 if event.trigger in {"hardware_failure", "received_error"} else 1,
                _event_sort_key(event),
            ),
        )
        root_cause = _event_to_dict(root_cause_event, include_raw=False)

    robot_ip = _archive_ip(archive_path)
    if robot_ip is None:
        for host, _count in accumulator.hosts.most_common():
            if ARCHIVE_IP_RE.fullmatch(host):
                robot_ip = host
                break

    warnings: list[str] = []
    if source_index.root is None:
        warnings.append("Opentrons source checkout not found; used built-in test-name heuristics")
    if not events:
        warnings.append("No meaningful operational/test error was found")

    result: dict[str, Any] = {
        "schema_version": 1,
        "input": str(archive_path),
        "source": str(archive_path),
        "archive": archive_path.name,
        "robot_ip": robot_ip,
        "robot_name": accumulator.robot_name,
        "robot": {"ip": robot_ip, "name": accumulator.robot_name},
        "time_range": {
            "first": _format_timestamp(accumulator.first_timestamp),
            "last": _format_timestamp(accumulator.last_timestamp),
        },
        "last_error": _event_to_dict(selected) if selected is not None else None,
        "last_test_error": _event_to_dict(selected) if selected is not None else None,
        "last_observed_error": (
            _event_to_dict(last_observed)
            if last_observed is not None and last_observed is not selected
            else None
        ),
        "last_error_time": _format_timestamp(selected.record.timestamp) if selected is not None else None,
        "last_error_reason": selected.message if selected is not None else None,
        "last_error_code": selected.code if selected is not None else None,
        "last_error_type": selected.exception if selected is not None else None,
        "last_error_category": selected.category if selected is not None else None,
        "hardware_error_state_at": _format_timestamp(accumulator.hardware_error_state_timestamp),
        "test_type": test_type,
        "test_type_label": _test_type_label(test_type),
        "test_kind": test_type.removesuffix("_test") if test_type.endswith("_test") else test_type,
        "test_family": test_type,
        "test_family_code": "hardware_testing" if test_type == "hardware_test" else test_type,
        "run_kind": run_kind,
        "execution_type": run_kind,
        "is_hardware_test": test_type == "hardware_test" if test_type != "unknown" else None,
        "is_protocol_test": test_type == "protocol_test" if test_type != "unknown" else None,
        "classification": {
            "test_type": test_type,
            "run_kind": run_kind,
            "confidence": round(confidence, 2),
            "evidence": list(evidence),
        },
        "error_count": len(events),
        "ignored_error_count": sum(accumulator.ignored.values()),
        "ignored_errors": dict(accumulator.ignored),
        "errors": error_dicts,
        "errors_truncated": len(output_errors) != len(events),
        "related_errors": related,
        "root_cause": root_cause,
        "log_files": accumulator.file_stats,
        "source_lookup": {
            "root": str(source_index.root) if source_index.root else None,
            "used": source_index.root is not None,
        },
        "warnings": warnings,
    }
    return result


def _discover_inputs(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(path)
    archives = sorted(path.glob("*.zip"))
    if archives:
        return archives
    logs = sorted(path.rglob("*.log"))
    if logs:
        # A directory containing loose logs is analyzed as one virtual bundle
        # by the caller's directory mode.
        return logs
    return []


def _analyze_loose_log_directory(
    directory: Path,
    *,
    source_index: SourceIndex,
    year: int | None,
    all_errors: bool,
) -> dict[str, Any]:
    """Analyze loose ``*.log`` files as a single bundle."""

    # Build a temporary in-memory ZIP so the exact same parser handles loose
    # files.  This path is only used when a directory has no ZIP archives.
    import tempfile

    with tempfile.NamedTemporaryFile(prefix="opentrons-log-bundle-", suffix=".zip") as temporary:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for log_path in _discover_inputs(directory):
                if log_path.suffix.casefold() == ".log":
                    archive.write(log_path, arcname=log_path.relative_to(directory).as_posix())
        temporary.flush()
        result = analyze_archive(
            Path(temporary.name),
            source_index=source_index,
            year=year,
            all_errors=all_errors,
        )
    result["source"] = str(directory.resolve())
    result["archive"] = directory.name
    return result


def analyze_paths(
    paths: Sequence[str | Path],
    *,
    source_root: Path | None = None,
    year: int | None = None,
    all_errors: bool = False,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Analyze one path directly or return a list for multiple bundles."""

    resolved_source = resolve_source_root(source_root)
    source_index = build_source_index(resolved_source)
    expanded: list[Path] = []
    loose_directories: list[Path] = []
    for value in paths:
        path = Path(value).expanduser().resolve()
        if path.is_dir():
            discovered = _discover_inputs(path)
            if discovered and all(item.suffix.casefold() == ".log" for item in discovered):
                loose_directories.append(path)
            else:
                expanded.extend(discovered)
        else:
            expanded.append(path)
    results: list[dict[str, Any]] = []
    if loose_directories:
        results.extend(
            [
                _analyze_loose_log_directory(
                    directory,
                    source_index=source_index,
                    year=year,
                    all_errors=all_errors,
                )
                for directory in loose_directories
            ]
        )

    def analyze_one(path: Path) -> dict[str, Any]:
        return analyze_archive(
            path,
            source_index=source_index,
            year=year,
            all_errors=all_errors,
        )

    results.extend(analyze_one(path) for path in expanded)
    if len(results) == 1:
        return results[0]
    return results


def _is_protocol_failure(event: dict[str, Any] | None) -> bool:
    if not event:
        return False
    if event.get("run_kind") == "protocol_run" or event.get("execution_type") == "protocol_run":
        return True
    return event.get("trigger") in {
        "protocol_exception",
        "command_failed",
        "post_run_failure",
        "structured_command_failure",
    }


def _pick_last_protocol_failure(full: dict[str, Any]) -> dict[str, Any] | None:
    """Prefer the last protocol-run failure; fall back to last_test_error."""

    candidates = [
        event
        for event in full.get("errors") or []
        if isinstance(event, dict) and _is_protocol_failure(event)
    ]
    if candidates:
        return candidates[-1]
    last_error = full.get("last_error") or full.get("last_test_error")
    return last_error if isinstance(last_error, dict) else None


def slim_result(full: dict[str, Any]) -> dict[str, Any]:
    """Reduce the verbose analyzer payload to short keywords."""

    failure = _pick_last_protocol_failure(full)
    robot = full.get("robot") if isinstance(full.get("robot"), dict) else {}
    code = (failure or {}).get("code") or (failure or {}).get("error_code")
    code_name = (failure or {}).get("code_name")
    result: dict[str, Any] = {
        "time": (failure or {}).get("timestamp") or full.get("last_error_time"),
        "error": (failure or {}).get("message")
        or (failure or {}).get("reason")
        or full.get("last_error_reason"),
        "code": code,
        "code_name": code_name,
        "exception": (failure or {}).get("exception") or (failure or {}).get("error_type"),
        "protocol": (failure or {}).get("protocol_name"),
        "file": (failure or {}).get("protocol_file"),
        "line": (failure or {}).get("protocol_line"),
        "run": (failure or {}).get("run_kind") or (failure or {}).get("execution_type"),
        "test": (failure or {}).get("test_type") or full.get("test_type"),
        "robot": full.get("robot_name") or robot.get("name"),
        "ip": full.get("robot_ip") or robot.get("ip"),
        "archive": full.get("archive"),
    }
    # Drop empty keys so the default CLI output stays keyword-short.
    return {key: value for key, value in result.items() if value not in (None, "", [])}


def _ensure_backend_src_on_path() -> Path:
    backend_root = Path(__file__).resolve().parents[1]
    src_root = backend_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    return src_root


def _agent_prompt(slim: dict[str, Any], full: dict[str, Any]) -> str:
    failure = _pick_last_protocol_failure(full) or {}
    raw = _shorten(str(failure.get("raw") or ""), 2_500)
    evidence = {
        "summary": slim,
        "category": failure.get("category") or failure.get("error_category"),
        "trigger": failure.get("trigger"),
        "run_id": failure.get("run_id"),
        "command_id": failure.get("command_id"),
        "source_lookup": full.get("source_lookup"),
        "raw_excerpt": raw or None,
    }
    return (
        "请根据下面这份 Opentrons 机器人日志摘要，分析最后一次 protocol 失败的真实原因。\n"
        "要求：\n"
        "1. 必须先调用 get_opentrons_knowledge_status，再按错误关键字调用 "
        "search_opentrons_source / read_opentrons_source 查阅本地 Opentrons 源码。\n"
        "2. 区分日志表象错误与源码层面的真实根因；给出可验证的结论，并引用源码相对路径与行号。\n"
        "3. 回答简洁：先一句结论，再列 2-4 条关键证据/建议；不要复述整段日志。\n"
        "4. 缺少源码或证据不足时明确说明，不要编造。\n\n"
        f"日志摘要 JSON：\n{json.dumps(evidence, ensure_ascii=False, indent=2)}"
    )


def run_production_agent_analysis(slim: dict[str, Any], full: dict[str, Any]) -> dict[str, Any]:
    """Call production-agent with Opentrons source tools for root-cause analysis."""

    _ensure_backend_src_on_path()
    try:
        import core.config  # noqa: F401 - load apps/backend/.env before LLM init
        from modules.agent.models import AgentChatMessage, AgentChatRequest
        from modules.agent.service import agent_service
    except ImportError as exc:
        return {
            "ok": False,
            "error": (
                f"无法导入 production-agent: {exc} "
                "(请用仓库 .venv 运行，例如 `.venv/bin/python apps/backend/scripts/analyze_logs.py --agent ...`)"
            ),
        }

    if not agent_service.configured:
        return {
            "ok": False,
            "error": "未配置 PRODUCTION_PLATFORM_LLM_API_KEY，无法调用 production-agent",
        }

    import asyncio

    request = AgentChatRequest(
        messages=[AgentChatMessage(role="user", content=_agent_prompt(slim, full))],
        context="analyze_logs.py --agent：协议失败根因分析",
    )

    async def _collect() -> dict[str, Any]:
        parts: list[str] = []
        tools: list[str] = []
        error: str | None = None
        async for event in agent_service.stream_events(request):
            if event.type == "chunk" and event.content:
                parts.append(event.content)
            elif event.type == "error" and event.content:
                error = event.content
            elif event.type == "tool_result" and event.data:
                name = str(event.data.get("name") or event.data.get("tool") or "tool")
                if name not in tools:
                    tools.append(name)
        return {
            "ok": error is None,
            "model": agent_service.model,
            "root_cause": "".join(parts).strip() or None,
            "tools": tools,
            "error": error,
        }

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        try:
            return asyncio.run(_collect())
        except Exception as exc:  # noqa: BLE001 - surface LLM/tool failures in JSON
            return {
                "ok": False,
                "model": agent_service.model,
                "root_cause": None,
                "tools": [],
                "error": str(exc),
            }

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_collect())
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "model": agent_service.model,
            "root_cause": None,
            "tools": [],
            "error": str(exc),
        }
    finally:
        loop.close()


def enrich_with_agent(
    payload: dict[str, Any] | list[dict[str, Any]],
    *,
    full_payload: dict[str, Any] | list[dict[str, Any]],
) -> dict[str, Any] | list[dict[str, Any]]:
    """Attach production-agent root-cause text onto slim or full results."""

    if isinstance(payload, list):
        assert isinstance(full_payload, list)
        return [
            enrich_with_agent(item, full_payload=full_item)
            for item, full_item in zip(payload, full_payload)
        ]

    assert isinstance(full_payload, dict)
    slim = payload if "error" in payload or "time" in payload else slim_result(full_payload)
    agent = run_production_agent_analysis(slim, full_payload)
    enriched = dict(payload)
    if agent.get("ok") and agent.get("root_cause"):
        enriched["root_cause"] = agent["root_cause"]
        enriched["agent"] = {
            "ok": True,
            "model": agent.get("model"),
            "tools": agent.get("tools") or [],
        }
    else:
        enriched["root_cause"] = None
        enriched["agent"] = {
            "ok": False,
            "error": agent.get("error") or "production-agent 未返回结论",
            "model": agent.get("model"),
            "tools": agent.get("tools") or [],
        }
    return enriched


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        help="ZIP, .log, or directory (default: ~/testing_data/logs)",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Emit the full diagnostic JSON instead of the short keyword summary",
    )
    parser.add_argument(
        "--agent",
        action="store_true",
        help="Call production-agent with Opentrons source tools to explain the real root cause",
    )
    parser.add_argument(
        "--all-errors",
        "--include-events",
        action="store_true",
        help="With --full, include every meaningful error instead of the latest 20",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        help="Opentrons checkout used to resolve hardware-testing protocol names",
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Year for syslog timestamps without a year (normally inferred from the ZIP name)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    paths = [Path(value) for value in args.paths] or [DEFAULT_LOG_DIR]
    try:
        full = analyze_paths(
            paths,
            source_root=args.source_root,
            year=args.year,
            all_errors=args.all_errors,
        )
    except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as exc:
        # Keep command-line failures machine-readable while sending the human
        # explanation to stderr.
        print(f"analyze_logs.py: {exc}", file=sys.stderr)
        return 2

    if args.full:
        result: dict[str, Any] | list[dict[str, Any]] = full
    elif isinstance(full, list):
        result = [slim_result(item) for item in full]
    else:
        result = slim_result(full)

    if args.agent:
        result = enrich_with_agent(result, full_payload=full)
        agent_meta = result.get("agent") if isinstance(result, dict) else None
        if isinstance(result, list):
            failed = any(not (item.get("agent") or {}).get("ok") for item in result)
        else:
            failed = not (agent_meta or {}).get("ok")
        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2 if args.pretty else None,
                separators=None if args.pretty else (",", ":"),
            )
        )
        return 3 if failed else 0

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
