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

    @staticmethod
    def _log(logs: list[dict[str, Any]], step: str, title: str, status: str, message: str, **extra: Any) -> None:
        """Append one structured event so the UI can show an auditable scan timeline."""
        event = {
            "at": datetime.now(timezone.utc), "step": step, "title": title,
            "status": status, "message": message,
        }
        for key in ("checked_count", "alert_count", "issues"):
            if key in extra:
                event[key] = extra.pop(key)
        if extra:
            event["details"] = extra
        logs.append(event)

    def scan(self, scan_items: list[str] | None = None, trigger: str = "manual") -> dict[str, Any]:
        selected = [x for x in (list(SCAN_ITEMS) if scan_items is None else scan_items) if x in SCAN_ITEMS]
        # A consistency scan always starts by bringing both source tables up to date.
        if "sync" not in selected:
            selected.insert(0, "sync")
        started = datetime.now(timezone.utc)
        process: list[str] = ["开始风险扫描"]
        process_logs: list[dict[str, Any]] = []
        details: list[dict[str, Any]] = []
        sync_records: list[dict[str, Any]] = []
        self._log(process_logs, "start", "开始扫描", "info", f"触发方式：{trigger}；选择 {len(selected)} 个扫描项目")
        if "sync" in selected:
            for table in ("eng", "ipqc"):
                status = self.ecn_service.check_sync(table=table)
                if not status.in_sync:
                    process.append(f"{table.upper()} 数据不同步，执行同步")
                    synced = self.ecn_service.sync_from_google(table=table)
                    sync_item = {"table": table, "missing": synced.missing_count, "extra": synced.extra_count, "changed": synced.changed_count,
                                 "missing_records": [item.model_dump() for item in synced.missing_in_mongodb],
                                 "extra_records": [item.model_dump() for item in synced.extra_in_mongodb],
                                 "changed_records": [item.model_dump() for item in synced.changed]}
                    sync_records.append(sync_item)
                    self._log(process_logs, "sync", f"同步 {table.upper()} 数据", "warning", f"发现差异并完成同步：缺少 {synced.missing_count}，多出 {synced.extra_count}，变化 {synced.changed_count}", **sync_item)
                else:
                    process.append(f"{table.upper()} 数据已同步")
                    sync_records.append({"table": table, "missing": 0, "extra": 0, "changed": 0})
                    self._log(process_logs, "sync", f"{table.upper()} 数据同步", "success", f"Google {status.google_total} 条与 MongoDB {status.mongodb_total} 条一致", checked_count=status.google_total)

        eng = self.ecn_service.repository.master_records("eng")
        ipqc = self.ecn_service.repository.master_records("ipqc")
        eng_nums = {n for r in eng if (n := self._number(r)) is not None}
        ipqc_nums = {n for r in ipqc if (n := self._number(r)) is not None}
        self._log(process_logs, "load", "读取扫描数据", "success", f"已读取 ENG {len(eng)} 条、IPQC {len(ipqc)} 条，提取 ECN 编号 {len(eng_nums)} / {len(ipqc_nums)}")
        if "count" in selected:
            count_issue = self._detail("count", f"ENG {len(eng)} 条，IPQC {len(ipqc)} 条", count_eng=len(eng), count_ipqc=len(ipqc))
            if len(eng) != len(ipqc):
                details.append(count_issue)
                self._log(process_logs, "count", "核对 ENG / IPQC 数量", "warning", count_issue["message"], checked_count=len(eng) + len(ipqc), issues=[count_issue])
            else:
                self._log(process_logs, "count", "核对 ENG / IPQC 数量", "success", f"数量一致，均为 {len(eng)} 条", checked_count=len(eng) + len(ipqc))
        if "sequence" in selected:
            sequence_issues: list[dict[str, Any]] = []
            for label, nums in (("ENG", eng_nums), ("IPQC", ipqc_nums)):
                if nums:
                    gaps = sorted(set(range(min(nums), max(nums) + 1)) - nums)
                    if gaps:
                        issue = self._detail("sequence", f"{label} ECN 编号跳号：{', '.join(map(str, gaps))}", table=label.lower(), missing_numbers=gaps)
                        details.append(issue); sequence_issues.append(issue)
                        self._log(process_logs, "sequence", f"核对 {label} ECN 编号连续性", "warning", issue["message"], checked_count=len(nums), issues=[issue])
                    else:
                        self._log(process_logs, "sequence", f"核对 {label} ECN 编号连续性", "success", f"编号 {min(nums)} - {max(nums)} 连续，无跳号", checked_count=len(nums))
                else:
                    self._log(process_logs, "sequence", f"核对 {label} ECN 编号连续性", "info", "没有可用 ECN 编号，跳过连续性判断", checked_count=0)
        if "missing_ipqc" in selected:
            missing_issues: list[dict[str, Any]] = []
            for record in eng:
                number = self._number(record)
                if number is not None and number not in ipqc_nums:
                    age = datetime.now(timezone.utc) - (self._date(record) or datetime.now(timezone.utc))
                    issue = self._detail("missing_ipqc", f"IPQC 缺少 {record.ecn_number}，已拖延 {max(0, age.days)} 天", record, delay_days=max(0, age.days))
                    details.append(issue); missing_issues.append(issue)
            self._log(process_logs, "missing_ipqc", "核对 ENG 与 IPQC ECN 编号", "warning" if missing_issues else "success", f"发现 {len(missing_issues)} 个 ENG 编号未出现在 IPQC" if missing_issues else "ENG 中的 ECN 编号全部存在于 IPQC", checked_count=len(eng_nums), issues=missing_issues)
        if "master_links" in selected:
            link_issues: list[dict[str, Any]] = []
            for record in eng:
                if not record.record_url.strip():
                    issue = self._detail("master_links", "ENG 总表缺少 ECN link", record)
                    details.append(issue); link_issues.append(issue)
            self._log(process_logs, "master_links", "核对 ENG 总表 ECN link", "warning" if link_issues else "success", f"发现 {len(link_issues)} 条记录缺少 link" if link_issues else f"已核对 {len(eng)} 条记录，link 均存在", checked_count=len(eng), issues=link_issues)
        if "linked_number" in selected:
            linked_issues: list[dict[str, Any]] = []
            for record in eng:
                linked = next((record.extra_fields.get(k, "").strip() for k in ("linked_ecn_number", "sheet_ecn_number", "aq14_bf17_ecn_number") if record.extra_fields.get(k)), "")
                if linked and self._number(record) != self._number(EcnRecord(id="x", ecn_number=linked)):
                    issue = self._detail("linked_number", f"ECN 编号与链接表格 AQ14:BF17 不一致：{linked}", record, linked_number=linked)
                    details.append(issue); linked_issues.append(issue)
            self._log(process_logs, "linked_number", "核对 link 表格 AQ14:BF17 编号", "warning" if linked_issues else "success", f"发现 {len(linked_issues)} 条编号不一致" if linked_issues else f"已核对 {len(eng)} 条记录，未发现编号不一致", checked_count=len(eng), issues=linked_issues)
        if "single_choice" in selected:
            fields = {"change_category": "变更类别", "affected_document": "受影响的程序、文件或记录", "purchased_in_transit": "外购在途物料处理", "workshop_material": "车间物料处理", "workshop_wip": "车间在制半成品处理", "workshop_finished": "车间成品处理", "raw_material_warehouse": "原材料仓库存处理", "finished_warehouse": "成品仓库存处理"}
            single_choice_issues: list[dict[str, Any]] = []
            for record in eng:
                for key, label in fields.items():
                    value = getattr(record, key, None) or record.extra_fields.get(key, "")
                    if isinstance(value, str) and re.search(r"[,，;；/\\\n]", value.strip()):
                        issue = self._detail("single_choice", f"{label}不是单选：{value}", record, field=key, value=value)
                        details.append(issue); single_choice_issues.append(issue)
            self._log(process_logs, "single_choice", "核对单选字段", "warning" if single_choice_issues else "success", f"发现 {len(single_choice_issues)} 个字段不是单选" if single_choice_issues else f"已核对 {len(eng)} 条记录的单选字段，全部正常", checked_count=len(eng) * len(fields), issues=single_choice_issues)
        grouped = [{"category": category, "count": sum(1 for d in details if d["category"] == category), "details": [d for d in details if d["category"] == category]} for category in sorted({d["category"] for d in details})]
        finished = datetime.now(timezone.utc)
        final_status = "warning" if details else "success"
        # The start event is a completed audit step by the time a result is
        # persisted. Keep no stale "running" state in historical reports.
        if process_logs:
            process_logs[0]["status"] = "success"
            process_logs[0]["message"] = f"扫描已启动，随后完成 {len(selected)} 个扫描项目"
        self._log(process_logs, "complete", "扫描完成", final_status, f"共完成 {len(selected)} 个扫描项目，发现 {len(details)} 项告警", alert_count=len(details))
        result = {"_id": uuid4().hex, "scan_date": finished.date().isoformat(), "scanned_at": finished, "started_at": started, "finished_at": finished, "trigger": trigger, "selected_items": selected, "sync_records": sync_records, "process": process + [f"扫描完成，发现 {len(details)} 项告警"], "process_logs": process_logs, "total_alerts": len(details), "categories": grouped}
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
