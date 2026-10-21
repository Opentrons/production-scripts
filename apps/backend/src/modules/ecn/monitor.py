from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import core.config as setting
from core.persistence import get_message_database
from modules.ecn.models import EcnRecord
from modules.ecn.service import EcnService


SCAN_ITEMS = (
    "sync", "count", "sequence", "missing_ipqc", "master_links",
    "linked_number", "single_choice",
)
_NUMBER_RE = re.compile(r"\d+")


class EcnMonitorService:
    def __init__(self, ecn_service: EcnService) -> None:
        self.ecn_service = ecn_service
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def db(self):
        return get_message_database()

    @property
    def results(self):
        collection = self.db["ecn_risk_scan_results"]
        collection.create_index([("scanned_at", -1)])
        collection.create_index("scan_date")
        return collection

    @property
    def settings(self):
        collection = self.db["ecn_risk_scan_settings"]
        # MongoDB creates the `_id` index automatically; attempting to create
        # it again with `unique=True` is rejected by MongoDB 5+.
        return collection

    def get_settings(self) -> dict[str, Any]:
        item = self.settings.find_one({"_id": "default"}) or {}
        return {
            "enabled": bool(item.get("enabled", False)),
            "interval_minutes": max(5, int(item.get("interval_minutes", 1440))),
            "scan_items": [x for x in item.get("scan_items", list(SCAN_ITEMS)) if x in SCAN_ITEMS],
            "updated_at": item.get("updated_at"),
            "last_run_at": item.get("last_run_at"),
        }

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        interval = max(5, min(10080, int(payload.get("interval_minutes", 1440))))
        items = [x for x in payload.get("scan_items", list(SCAN_ITEMS)) if x in SCAN_ITEMS]
        self.settings.update_one({"_id": "default"}, {"$set": {
            "enabled": bool(payload.get("enabled", False)),
            "interval_minutes": interval, "scan_items": items,
            "updated_at": datetime.now(timezone.utc),
        }}, upsert=True)
        return self.get_settings()

    @staticmethod
    def _number(record: EcnRecord) -> int | None:
        match = _NUMBER_RE.search(record.ecn_number or record.form_number)
        return int(match.group()) if match else None

    @staticmethod
    def _date(record: EcnRecord) -> datetime | None:
        for value in (record.change_date, record.extra_fields.get("issued_date", ""), record.extra_fields.get("created_date", "")):
            if not value:
                continue
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
            except ValueError:
                try:
                    return datetime.strptime(value[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
        return None

    @staticmethod
    def _detail(category: str, message: str, record: EcnRecord | None = None, **extra: Any) -> dict[str, Any]:
        return {"category": category, "message": message, "ecn_number": getattr(record, "ecn_number", ""), **extra}

    def scan(self, scan_items: list[str] | None = None, trigger: str = "manual") -> dict[str, Any]:
        selected = [x for x in (scan_items or list(SCAN_ITEMS)) if x in SCAN_ITEMS]
        # A consistency scan always starts by bringing both source tables up to date.
        if "sync" not in selected:
            selected.insert(0, "sync")
        started = datetime.now(timezone.utc)
        process: list[str] = ["开始风险扫描"]
        details: list[dict[str, Any]] = []
        sync_records: list[dict[str, Any]] = []
        if "sync" in selected:
            for table in ("eng", "ipqc"):
                status = self.ecn_service.check_sync(table=table)
                if not status.in_sync:
                    process.append(f"{table.upper()} 数据不同步，执行同步")
                    synced = self.ecn_service.sync_from_google(table=table)
                    sync_records.append({"table": table, "missing": synced.missing_count, "extra": synced.extra_count, "changed": synced.changed_count})
                else:
                    process.append(f"{table.upper()} 数据已同步")

        eng = self.ecn_service.repository.master_records("eng")
        ipqc = self.ecn_service.repository.master_records("ipqc")
        eng_nums = {n for r in eng if (n := self._number(r)) is not None}
        ipqc_nums = {n for r in ipqc if (n := self._number(r)) is not None}
        if "count" in selected and len(eng) != len(ipqc):
            details.append(self._detail("count", f"ENG {len(eng)} 条，IPQC {len(ipqc)} 条", count_eng=len(eng), count_ipqc=len(ipqc)))
        if "sequence" in selected:
            for label, nums in (("ENG", eng_nums), ("IPQC", ipqc_nums)):
                if nums:
                    gaps = sorted(set(range(min(nums), max(nums) + 1)) - nums)
                    if gaps:
                        details.append(self._detail("sequence", f"{label} ECN 编号跳号：{', '.join(map(str, gaps))}", table=label.lower(), missing_numbers=gaps))
        if "missing_ipqc" in selected:
            for record in eng:
                number = self._number(record)
                if number is not None and number not in ipqc_nums:
                    age = datetime.now(timezone.utc) - (self._date(record) or datetime.now(timezone.utc))
                    details.append(self._detail("missing_ipqc", f"IPQC 缺少 {record.ecn_number}，已拖延 {max(0, age.days)} 天", record, delay_days=max(0, age.days)))
        if "master_links" in selected:
            for record in eng:
                if not record.record_url.strip():
                    details.append(self._detail("master_links", "ENG 总表缺少 ECN link", record))
        if "linked_number" in selected:
            for record in eng:
                linked = next((record.extra_fields.get(k, "").strip() for k in ("linked_ecn_number", "sheet_ecn_number", "aq14_bf17_ecn_number") if record.extra_fields.get(k)), "")
                if linked and self._number(record) != self._number(EcnRecord(id="x", ecn_number=linked)):
                    details.append(self._detail("linked_number", f"ECN 编号与链接表格 AQ14:BF17 不一致：{linked}", record, linked_number=linked))
        if "single_choice" in selected:
            fields = {"change_category": "变更类别", "affected_document": "受影响的程序、文件或记录", "purchased_in_transit": "外购在途物料处理", "workshop_material": "车间物料处理", "workshop_wip": "车间在制半成品处理", "workshop_finished": "车间成品处理", "raw_material_warehouse": "原材料仓库存处理", "finished_warehouse": "成品仓库存处理"}
            for record in eng:
                for key, label in fields.items():
                    value = getattr(record, key, None) or record.extra_fields.get(key, "")
                    if isinstance(value, str) and re.search(r"[,，;；/\\\n]", value.strip()):
                        details.append(self._detail("single_choice", f"{label}不是单选：{value}", record, field=key, value=value))
        grouped = [{"category": category, "count": sum(1 for d in details if d["category"] == category), "details": [d for d in details if d["category"] == category]} for category in sorted({d["category"] for d in details})]
        finished = datetime.now(timezone.utc)
        result = {"_id": uuid4().hex, "scan_date": finished.date().isoformat(), "scanned_at": finished, "started_at": started, "finished_at": finished, "trigger": trigger, "selected_items": selected, "sync_records": sync_records, "process": process + [f"扫描完成，发现 {len(details)} 项告警"], "total_alerts": len(details), "categories": grouped}
        self.results.insert_one(result)
        self.settings.update_one({"_id": "default"}, {"$set": {"last_run_at": finished}}, upsert=True)
        result["id"] = str(result.pop("_id", ""))
        return result

    def list_results(self, limit: int = 30) -> list[dict[str, Any]]:
        return [{**item, "id": str(item.pop("_id", ""))} for item in self.results.find({}).sort("scanned_at", -1).limit(max(1, min(limit, 100)))]

    def start(self) -> None:
        if self._thread and self._thread.is_alive(): return
        self._stop.clear(); self._thread = threading.Thread(target=self._run, name="ecn-risk-scheduler", daemon=True); self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(30):
            try:
                config = self.get_settings()
                if not config["enabled"]: continue
                last = config.get("last_run_at")
                if not last or datetime.now(timezone.utc) - last >= timedelta(minutes=config["interval_minutes"]):
                    self.scan(config["scan_items"], "scheduled")
            except Exception:
                # A transient MongoDB outage must not permanently kill the
                # scheduler thread; the next poll will retry.
                continue
