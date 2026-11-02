"""Read the QC tracker and verify the identity inside each linked report.

Tracker columns are discovered per tab. The tracker currently has no run-id
column, so its SN and URL are candidates, never sufficient proof of a match.
"""
from __future__ import annotations

import os
import re
from urllib.parse import parse_qs, urlparse

from core.google.client import GoogleDriver


DEFAULT_SPREADSHEET_ID = "16GY8f7p788fbwxxIEH_Azn1RB-NWl3N7cRZzz-6SA_E"
DEFAULT_SINGLE_CHANNEL_SPREADSHEET_ID = "1eHeq3W0Mr-X6nC0MkNZuuS3DLW097Xtwl2pTkIEpSOU"
SN_HEADERS = {"pipette", "pipettesn", "serialnumber", "sn", "testdeviceid", "移液器sn", "移液器序列号", "设备序列号"}
LINK_HEADERS = {"qclink", "csvlink", "link", "reportlink", "reporturl", "测试报告", "报告链接"}
RUN_HEADERS = {"reportrunid", "testrunid"}


def normalized(value: object) -> str:
    return re.sub(r"[\s_\-]+", "", str(value or "")).casefold()


def report_target(url: str) -> tuple[str, int | None]:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Unsupported report link")
    patterns = {"docs.google.com": r"/spreadsheets/d/([A-Za-z0-9_-]+)(?:/|$)",
                "drive.google.com": r"/file/d/([A-Za-z0-9_-]+)(?:/|$)"}
    match = re.match(patterns.get(parsed.hostname or "", r"(?!)"), parsed.path)
    if not match:
        raise ValueError("Unsupported report link")
    gids = parse_qs(parsed.fragment).get("gid", []) + parse_qs(parsed.query).get("gid", [])
    if any(not gid.isdigit() for gid in gids) or len(set(gids)) > 1:
        raise ValueError("Invalid report sheet gid")
    return match[1], int(gids[0]) if gids else None


def cell_urls(cell: dict) -> list[str]:
    values = [cell.get("hyperlink"), cell.get("formattedValue"),
              cell.get("userEnteredFormat", {}).get("textFormat", {}).get("link", {}).get("uri")]
    formula = cell.get("userEnteredValue", {}).get("formulaValue", "")
    match = re.match(r'^\s*=HYPERLINK\(\s*"((?:[^"]|"")+)"\s*[,;)]', formula, re.I)
    if match:
        values.append(match[1].replace('""', '"'))
    values.extend(run.get("format", {}).get("link", {}).get("uri") for run in cell.get("textFormatRuns", []))
    urls = []
    for value in values:
        if not isinstance(value, str):
            continue
        try:
            report_target(value)
        except (ValueError, TypeError):
            continue
        if value.strip() not in urls:
            urls.append(value.strip())
    return urls


def grid_rows(sheets: list[dict]) -> dict[int, dict[int, dict[int, dict]]]:
    """Combine disjoint ranges; Google omits trailing empty rows and cells."""
    result: dict[int, dict[int, dict[int, dict]]] = {}
    for sheet in sheets:
        rows = result.setdefault(int(sheet["properties"]["sheetId"]), {})
        for block in sheet.get("data", []):
            for offset, row in enumerate(block.get("rowData", [])):
                cells = rows.setdefault(block.get("startRow", 0) + offset, {})
                for col, cell in enumerate(row.get("values", [])):
                    cells[block.get("startColumn", 0) + col] = cell
    return result


def cell_value(row: dict[int, dict], column: int) -> str:
    return str(row.get(column, {}).get("formattedValue", "")).strip()


def metadata_identity(rows: dict[int, dict[int, dict]]) -> dict[str, str]:
    """Accept only an explicit metadata section, including the legacy CSV tags."""
    identities: set[tuple[str, str]] = set()
    fields: dict[str, set[str]] | None = None
    for _, row in sorted(rows.items()):
        tag = cell_value(row, 1)
        key = normalized(tag)
        if key in {"metadata", "metadatastart"}:
            fields = {"sn": set(), "report_run_id": set()}
            continue
        if fields is None:
            continue
        if key == "metadataend" or re.fullmatch(r"[-=]{3,}", tag):
            if any(len(values) != 1 for values in fields.values()):
                raise ValueError("Missing or conflicting report identity")
            identities.add((next(iter(fields["sn"])), next(iter(fields["report_run_id"]))))
            fields = None
            continue
        name = "sn" if key in {"testdeviceid", "pipette", "pipettesn", "serialnumber"} else "report_run_id" if key in {"testrunid", "reportrunid", "date"} else None
        value = cell_value(row, 2)
        if name and value:
            fields[name].add(value)
    # Never claim an identity from an incomplete/bounded-away metadata section.
    if fields is not None or len(identities) != 1:
        raise ValueError("Report metadata unavailable or ambiguous")
    sn, run_id = next(iter(identities))
    return {"sn": sn, "report_run_id": run_id}


class GoogleReportLinkSource:
    def __init__(self, driver=None, spreadsheet_id: str | None = None, sheet_gids: list[int] | None = None, *, channel: str = "8ch"):
        if channel not in {"1ch", "8ch"}:
            raise ValueError("Unsupported report tracker channel")
        self.channel = channel
        env_prefix = "PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_1CH" if channel == "1ch" else "PRODUCTION_PLATFORM_TEST_FAILURE_REPORT"
        default_id = DEFAULT_SINGLE_CHANNEL_SPREADSHEET_ID if channel == "1ch" else DEFAULT_SPREADSHEET_ID
        self.driver = driver or GoogleDriver(allow_interactive_auth=False)
        self.spreadsheet_id = spreadsheet_id or os.getenv(f"{env_prefix}_SHEET_ID", default_id).strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{10,}", self.spreadsheet_id):
            raise ValueError("Invalid report tracker spreadsheet ID")
        self.sheet_gids = sheet_gids
        if self.sheet_gids is None:
            configured = os.getenv(f"{env_prefix}_SHEET_GIDS", "").strip()
            self.sheet_gids = [int(gid.strip()) for gid in configured.split(",")] if configured else []
        self.cache_namespace = f"qc-tracker-v2:{channel}:{self.spreadsheet_id}:{','.join(map(str, sorted(self.sheet_gids)))}"

    def _read_ranges(self, spreadsheet_id: str, ranges: list[str]) -> dict[int, dict[int, dict[int, dict]]]:
        result: dict[int, dict[int, dict[int, dict]]] = {}
        for start in range(0, len(ranges), 45):
            for gid, rows in grid_rows(self.driver.read_sheet_grid_ranges(spreadsheet_id, ranges[start:start + 45])).items():
                target = result.setdefault(gid, {})
                for row, cells in rows.items():
                    target.setdefault(row, {}).update(cells)
        return result

    def read_catalog(self) -> list[dict]:
        sheets = [sheet for sheet in self.driver.get_sheet_metadata(self.spreadsheet_id)
                  if sheet.get("sheetType", "GRID") == "GRID" and (not self.sheet_gids or sheet["sheetId"] in self.sheet_gids)]
        if not sheets or self.sheet_gids and set(self.sheet_gids) - {s["sheetId"] for s in sheets}:
            raise ValueError("Configured tracker sheets unavailable")
        headers = self._read_ranges(self.spreadsheet_id, [f"{GoogleDriver._quote_sheet_title(s['title'])}!A1:{GoogleDriver.column_name(min(256, s.get('gridProperties', {}).get('columnCount', 128)))}20" for s in sheets])
        layouts = []
        ranges = []
        for sheet in sheets:
            recognized_sn = False
            found_layout = False
            for row_number, cells in sorted(headers.get(sheet["sheetId"], {}).items()):
                sn_cols = [col for col in cells if normalized(cell_value(cells, col)) in SN_HEADERS]
                recognized_sn = recognized_sn or bool(sn_cols)
                if len(sn_cols) != 1:
                    continue
                sn_col = sn_cols[0]
                link_cols = [col for col in cells if normalized(cell_value(cells, col)) in LINK_HEADERS]
                # Several existing tabs label their QC Link column "Description".
                if not link_cols and sn_col > 0 and normalized(cell_value(cells, sn_col - 1)) == "description":
                    link_cols = [sn_col - 1]
                if not link_cols:
                    continue
                run_cols = [col for col in cells if normalized(cell_value(cells, col)) in RUN_HEADERS]
                if len(run_cols) > 1:
                    raise ValueError("Ambiguous tracker run-id columns")
                layouts.append((sheet, row_number, sn_col, link_cols, run_cols))
                found_layout = True
                for col in sorted({sn_col, *link_cols, *run_cols}):
                    column = GoogleDriver.column_name(col + 1)
                    ranges.append(f"{GoogleDriver._quote_sheet_title(sheet['title'])}!{column}{row_number + 2}:{column}")
                break
            # Non-report tabs may be ignored; a recognizable report tab with a
            # changed link/header layout must not silently become "not found".
            observed_links = any(cell_urls(cell) for cells in headers.get(sheet["sheetId"], {}).values() for cell in cells.values())
            if not found_layout and (recognized_sn or observed_links or self.sheet_gids):
                raise ValueError("Tracker report columns unavailable")
        if not layouts:
            raise ValueError("Tracker SN/link columns unavailable")
        data = self._read_ranges(self.spreadsheet_id, ranges)
        catalog = []
        for sheet, header_row, sn_col, link_cols, run_cols in layouts:
            for row_number, cells in sorted(data.get(sheet["sheetId"], {}).items()):
                if row_number <= header_row:
                    continue
                sn = cell_value(cells, sn_col)
                if not sn:
                    continue
                for col in link_cols:
                    cell = cells.get(col, {})
                    urls = cell_urls(cell)
                    invalid = not urls and bool(cell_value(cells, col) or cell.get("hyperlink")
                                               or cell.get("userEnteredValue") or cell.get("textFormatRuns")
                                               or cell.get("userEnteredFormat", {}).get("textFormat", {}).get("link"))
                    for url in urls or ([""] if invalid else []):
                        catalog.append({"sn": sn, "report_run_id": cell_value(cells, run_cols[0]) if run_cols else "",
                                        "url": url, "sheet_title": sheet["title"], "sheet_id": sheet["sheetId"], "row": row_number + 1,
                                        **({"error_code": "invalid_link"} if invalid else {}),
                                        "source_url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit#gid={sheet['sheetId']}&range={GoogleDriver.column_name(col + 1)}{row_number + 1}"})
        return catalog

    def read_identity(self, url: str) -> dict[str, str]:
        spreadsheet_id, gid = report_target(url)
        sheets = [s for s in self.driver.get_sheet_metadata(spreadsheet_id) if s.get("sheetType", "GRID") == "GRID"]
        resolved_url = None
        if gid is not None:
            selected = [s for s in sheets if s["sheetId"] == gid]
            # Some legacy links retain Google's default gid=0 after Assembly QC
            # acquired another sheet ID. Only repair that obsolete default when
            # exactly one explicitly named QC tab provides the report identity.
            if not selected and gid == 0:
                qc_sheets = [s for s in sheets if normalized(s["title"]) == "assemblyqc"]
                if len(qc_sheets) == 1:
                    selected = qc_sheets
                    resolved_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit#gid={selected[0]['sheetId']}"
            sheets = selected
        else:
            qc_sheets = [s for s in sheets if normalized(s["title"]) == "assemblyqc"]
            sheets = qc_sheets or sheets
        if not sheets:
            raise ValueError("Linked report sheet unavailable")
        data = self._read_ranges(spreadsheet_id, [f"{GoogleDriver._quote_sheet_title(s['title'])}!A1:D120" for s in sheets])
        identities = [metadata_identity(data.get(sheet["sheetId"], {})) for sheet in sheets]
        if len({(i["sn"], i["report_run_id"]) for i in identities}) != 1:
            raise ValueError("Linked report identity ambiguous")
        return {**identities[0], **({"resolved_url": resolved_url} if resolved_url else {})}
