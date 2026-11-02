from __future__ import annotations

import csv
import hashlib
import io
import logging
import os
import threading
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime

from core import config
from .filesystem import content_signature, open_source, source_stat, stat_signature
from .parser import digest
from .products import normalize_product
from .repository import ConflictError, NotFoundError, Repository, evidence_version, now
from .scanner import Scanner


logger = logging.getLogger(__name__)
PREVIEW_BYTES = 256 * 1024


def _confirmation_counts(devices: list[dict]) -> dict[str, int]:
    pending = sum(bool(device["unconfirmed_count"]) for device in devices)
    return {"total": len(devices), "pending": pending, "confirmed": len(devices) - pending}


class TestFailureService:
    __test__ = False

    def __init__(self, root: Path, database_path: Path, stable_seconds: float = 2):
        self.root = Path(root).expanduser().resolve()
        self.repository = Repository(database_path, digest(str(self.root)))
        self.scanner = Scanner(self.root, self.repository, stable_seconds)
        self._scan_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._state = {"running": False, "last_scan_at": None, "last_successful_scan_at": None, "source_status": "unknown", "error": None, "errors": [], "pending_files": 0, "parse_errors": 0}
        self._scan_thread: threading.Thread | None = None
        self._available_cache: dict[tuple, float] = {}
        self._available_lock = threading.Lock()

    def scan_status(self) -> dict:
        with self._state_lock:
            return {**self._state, "errors": [dict(item) for item in self._state["errors"]]}

    def _perform_scan(self) -> dict:
        try:
            result = self.scanner.scan()
            with self._state_lock:
                scanned_at = now()
                self._state.update(result, error=None, last_scan_at=scanned_at, last_successful_scan_at=scanned_at,
                                   source_status="degraded" if result["parse_errors"] or result["pending_files"] else "available")
        except Exception as exc:
            logger.warning("Test failure scan failed: %s", exc)
            with self._state_lock:
                self._state.update(error=str(exc), last_scan_at=now(), source_status="unavailable", errors=[], pending_files=0, parse_errors=0)
        finally:
            with self._state_lock:
                self._state["running"] = False
            self._scan_lock.release()
        return self.scan_status()

    def _claim_scan(self) -> bool:
        if not self._scan_lock.acquire(blocking=False):
            return False
        with self._state_lock:
            self._state["running"] = True
        return True

    def scan(self) -> dict:
        return self._perform_scan() if self._claim_scan() else self.scan_status()

    def request_scan(self) -> dict:
        if self._claim_scan():
            self._scan_thread = threading.Thread(target=self._perform_scan, name="test-failure-scan", daemon=True)
            self._scan_thread.start()
        return self.scan_status()

    @staticmethod
    def _test_date(value: str | None) -> str:
        if not value:
            return ""
        try:
            return datetime.fromisoformat(value).astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
        except ValueError:
            return ""

    def list_devices(self, *, q: str = "", product: str = "", date_from: str = "", date_to: str = "", mode: str = "", kind: str = "", confirmation: str = "all", page: int = 1, page_size: int = 20) -> dict:
        if confirmation not in {"all", "pending", "confirmed"}:
            raise ValueError("返修确认筛选无效")
        for date in (date_from, date_to):
            if date:
                datetime.strptime(date, "%Y-%m-%d")
        if date_from and date_to and date_from > date_to:
            raise ValueError("开始日期不能晚于结束日期")
        all_devices = self.repository.devices(q=q)
        options = {"products": sorted({item["product"] for item in all_devices}), "modes": sorted({report["mode"] for item in all_devices for report in item["reports"]})}
        base = []
        by_product: dict[str, list[dict]] = {name: [] for name in options["products"]}

        def matches(report: dict) -> bool:
            date = self._test_date(report.get("test_time"))
            return (not mode or report["mode"] == mode) and (not kind or report["kind"] == kind) and (not date_from or bool(date) and date >= date_from) and (not date_to or bool(date) and date <= date_to)

        for device in all_devices:
            device.pop("_history", None)
            query_ids = set(device.pop("_query_report_ids", []))
            device["matched_report_ids"] = [report["id"] for report in device["reports"] if report["id"] in query_ids and matches(report)]
            if not device["matched_report_ids"]:
                continue
            base.append(device)
            by_product[device["product"]].append(device)

        product = normalize_product(product)
        product_devices = by_product.get(product, []) if product else base
        facets = {
            "all": _confirmation_counts(base),
            "products": [{"product": name, **_confirmation_counts(devices)} for name, devices in by_product.items()],
            "confirmation": _confirmation_counts(product_devices),
        }
        selected = product_devices
        if confirmation != "all":
            selected = [device for device in product_devices if bool(device["unconfirmed_count"]) == (confirmation == "pending")]
        page, page_size = max(1, page), max(1, min(page_size, 100))
        state = self.scan_status()
        return {"devices": selected[(page - 1) * page_size:page * page_size], "total": len(selected), "page": page, "page_size": page_size,
                "summary": {"devices": len(selected), "pending": sum(bool(item["unconfirmed_count"]) for item in selected),
                            "reports": sum(item["report_count"] for item in selected), "parse_errors": state["parse_errors"]},
                "options": options, "facets": facets, "scan": state}

    def get_report(self, report_id: str) -> dict:
        report = self.repository.get_report(report_id)
        indexed = dict(report)
        report["evidence_version"] = evidence_version(indexed)
        paths = report.pop("attachment_paths", {})
        report.pop("attachment_signatures", None)
        report.pop("attachment_hashes", None)
        report.pop("semantic", None)
        report.pop("source_group", None)
        report.pop("known_sn", None)
        report["attachments"] = []
        for kind in ("json", "log", "encoder"):
            relative = paths.get(kind)
            available, size = False, 0
            if relative:
                try:
                    info = source_stat(self.root, relative)
                    cache_key = (relative, content_signature(info), tuple(indexed.get("attachment_signatures", {}).get(kind, [])), indexed.get("attachment_hashes", {}).get(kind))
                    with self._available_lock:
                        checked_at = self._available_cache.get(cache_key)
                    if checked_at is not None and time.monotonic() - checked_at < 30:
                        size, available = info.st_size, True
                    else:
                        with self.open_attachment(report_id, kind, _snapshot_content=False)[0] as handle:
                            size = handle.seek(0, os.SEEK_END)
                            available = True
                        with self._available_lock:
                            if len(self._available_cache) >= 1024:
                                self._available_cache.pop(next(iter(self._available_cache)))
                            self._available_cache[cache_key] = time.monotonic()
                except (OSError, NotFoundError):
                    pass
            report["attachments"].append({"kind": kind, "name": Path(relative).name if relative else "", "available": available, "size": size})
        latest = self.repository.get_report(report_id)
        if any(latest.get(key) != indexed.get(key) for key in ("revision", "attachment_paths", "attachment_signatures", "attachment_hashes")):
            raise ConflictError("报告版本已更新，请刷新详情后重试")
        return report

    def open_attachment(self, report_id: str, kind: str, *, verify_content: bool = True, _snapshot_content: bool = True):
        if kind not in {"json", "log", "encoder"}:
            raise NotFoundError("附件类型无效")
        report = self.repository.get_report(report_id)
        relative = report.get("attachment_paths", {}).get(kind)
        if not relative:
            raise NotFoundError("附件尚未上传或不可用")
        try:
            handle = open_source(self.root, relative)
            before = os.fstat(handle.fileno())
            if list(stat_signature(before)) != report.get("attachment_signatures", {}).get(kind):
                handle.close()
                raise NotFoundError("附件已变化，请等待重新扫描后查看对应报告")
            if not verify_content:
                # Internal analysis callers perform their own bounded read/hash.
                return handle, Path(relative).name
            snapshot = None
            try:
                if _snapshot_content:
                    snapshot = tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b")
                checksum = hashlib.sha256()
                size = 0
                while chunk := handle.read(256 * 1024):
                    size += len(chunk)
                    if size > before.st_size:
                        raise NotFoundError("读取期间附件发生变化，请重新扫描")
                    checksum.update(chunk)
                    if snapshot is not None:
                        snapshot.write(chunk)
                expected = report.get("attachment_hashes", {}).get(kind)
                if (not expected or checksum.hexdigest() != expected or size != before.st_size
                        or content_signature(os.fstat(handle.fileno())) != content_signature(before)):
                    raise NotFoundError("附件内容与索引不一致，请重新扫描后查看")
                latest = self.repository.get_report(report_id)
                if any(latest.get(key) != report.get(key) for key in ("revision", "attachment_paths", "attachment_signatures", "attachment_hashes")):
                    raise NotFoundError("报告版本已更新，请刷新详情后查看附件")
                if snapshot is not None:
                    handle.close()
                    snapshot.seek(0)
                    return snapshot, Path(relative).name
                # Detail availability only: bytes have been verified but aren't
                # displayed. Downloads/previews always return an immutable copy.
                handle.seek(0)
                return handle, Path(relative).name
            except BaseException:
                handle.close()
                if snapshot is not None:
                    snapshot.close()
                raise
        except OSError as exc:
            raise NotFoundError("附件不存在或已不可用") from exc

    def preview_attachment(self, report_id: str, kind: str) -> dict:
        handle, _ = self.open_attachment(report_id, kind)
        with handle:
            content = handle.read(PREVIEW_BYTES + 1)
        truncated = len(content) > PREVIEW_BYTES
        text = content[:PREVIEW_BYTES].decode("utf-8-sig", errors="replace")
        if kind != "encoder":
            return {"kind": kind, "text": text, "truncated": truncated}
        try:
            reader = csv.reader(io.StringIO(text))
            columns = next(reader, [])
            rows = []
            for row in reader:
                if len(rows) >= 200:
                    truncated = True
                    break
                rows.append(row)
            return {"kind": kind, "columns": columns, "rows": rows, "truncated": truncated}
        except csv.Error as exc:
            raise ValueError("编码器 CSV 无法预览") from exc

    def list_confirmations(self, device_id: str) -> dict:
        return self.repository.confirmations(device_id)

    def confirm_device(self, device_id: str, text: str, version: str, created_by: str, created_by_name: str = "") -> dict:
        return self.repository.confirm(device_id, text, version, created_by, created_by_name)


@lru_cache(maxsize=1)
def get_service() -> TestFailureService:
    return TestFailureService(
        Path(os.getenv("PRODUCTION_PLATFORM_TEST_FAILURE_DIR", "/opt/pipette_assembly_qc_log")),
        Path(config.DATA_DIR) / "defect-search" / "test-failures.sqlite3",
    )
