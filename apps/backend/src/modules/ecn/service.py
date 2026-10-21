from __future__ import annotations

import re
import threading
from time import monotonic
from datetime import datetime, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

from core.google import GoogleDriver, GoogleDriverError, GoogleSheetCell, GoogleSheetData
from core.logging import get_logger
from modules.ecn.definition import (
    ECN_FOLDER_ID,
    ECN_NUMBER_PATTERN,
    normalize_ecn_number,
)
from modules.ecn.models import (
    EcnCreateRequest,
    EcnCreateResponse,
    EcnRecord,
    EcnRecordsResponse,
    EcnSyncCheckResponse,
    EcnSyncDifference,
    EcnUpdateRequest,
)


ECN_MASTER_SPREADSHEET_ID = "1dIRCFaHSGF_15vgGRQMUHLtOZxzcOQFxoTqtlG70RM4"
ECN_MASTER_SHEET_GID = 1267645756
ECN_IPQC_MASTER_SPREADSHEET_ID = "1xgRKoCkzJYbPPZ6NP8ca3TNyvpm751TZipibw_N2i5M"
ECN_IPQC_MASTER_SHEET_GID = 199104664
ECN_MASTER_SOURCE_URL = (
    f"https://docs.google.com/spreadsheets/d/{ECN_MASTER_SPREADSHEET_ID}/edit"
    f"?gid={ECN_MASTER_SHEET_GID}#gid={ECN_MASTER_SHEET_GID}"
)
ECN_TEMPLATE_SPREADSHEET_ID = "1tzEyiacSsxiNM1mR9jkPbtT9Y5-rtWPU-LspZ6kPihU"
ECN_TEMPLATE_SHEET_TITLE = "工程变更通知单"
ECN_PRODUCT_MODEL_RANGE = f"'{ECN_TEMPLATE_SHEET_TITLE}'!M14:AD17"
ECN_NUMBER_RANGE = f"'{ECN_TEMPLATE_SHEET_TITLE}'!AQ14:BF17"
ECN_ISSUED_DATE_RANGE = f"'{ECN_TEMPLATE_SHEET_TITLE}'!BW18:CN21"
# Keep the old name for callers that use the template range directly.
ECN_CREATED_DATE_RANGE = ECN_ISSUED_DATE_RANGE
ECN_ISSUED_DATE_READ_RANGE = f"'{ECN_TEMPLATE_SHEET_TITLE}'!BW18"
ISSUED_DATE_CACHE_SECONDS = 60
logger = get_logger(__name__)
ISSUED_DATE_LABELS = ("发出日期", "Send Date")
ISSUED_DATE_PATTERN = re.compile(
    r"(?:20\d{2}[年./-]\d{1,2}[月./-]\d{1,2}|\d{1,2}/\d{1,2}/20\d{2})"
)
ECN_CHANGE_CATEGORY_CELLS = {
    "software": "P24", "material": "AC24", "drawing": "AP24",
    "process": "BD24", "other": "BV24",
}
ECN_AFFECTED_DOCUMENT_CELLS = {
    "drawing": "B88", "bom": "N88", "sop": "Z88", "sip": "AN88", "other": "BD88",
}
SOURCE_FIELDS = (
    "ecn_number",
    "ecn_title",
    "product_name",
    "category",
    "form_number",
    "change_item",
    "before_change",
    "after_change",
    "change_date",
    "changed_by",
    "approved_by",
    "record_url",
    "duro_number",
)


class EcnValidationError(ValueError):
    pass


class EcnConflictError(RuntimeError):
    pass


class EcnRepository(Protocol):
    def google_count(self) -> int: ...
    def insert_initial_google_records(self, records: list[EcnRecord]) -> int: ...
    def list(
        self,
        *,
        search: str,
        page: int,
        page_size: int,
        sort_order: str,
        status: str = "",
    ) -> tuple[list[EcnRecord], int]: ...
    def status_options(self, table: str = "eng") -> list[str]: ...
    def max_sequence_number(self) -> int | None: ...
    def changed_by_options(self) -> list[str]: ...
    def find_by_number(self, ecn_number: str) -> EcnRecord | None: ...
    def insert_created(self, record: EcnRecord) -> None: ...
    def google_records(self) -> list[EcnRecord]: ...
    def master_records(self) -> list[EcnRecord]: ...
    def find_by_id(self, record_id: str) -> EcnRecord | None: ...
    def replace(self, record: EcnRecord) -> None: ...
    def delete(self, record_id: str) -> None: ...


class EcnService:
    def __init__(self, repository: EcnRepository, driver: GoogleDriver) -> None:
        self.repository = repository
        self.driver = driver
        self._bootstrap_lock = threading.Lock()
        self._creation_lock = threading.Lock()
        self._issued_date_cache: dict[str, tuple[float, str]] = {}
        self._issued_date_lock = threading.Lock()

    @staticmethod
    def _master(table: str) -> tuple[str, int, str]:
        if table == "ipqc":
            return ECN_IPQC_MASTER_SPREADSHEET_ID, ECN_IPQC_MASTER_SHEET_GID, f"https://docs.google.com/spreadsheets/d/{ECN_IPQC_MASTER_SPREADSHEET_ID}/edit?gid={ECN_IPQC_MASTER_SHEET_GID}#gid={ECN_IPQC_MASTER_SHEET_GID}"
        return ECN_MASTER_SPREADSHEET_ID, ECN_MASTER_SHEET_GID, ECN_MASTER_SOURCE_URL

    def list_records(
        self,
        *,
        search: str = "",
        status: str = "",
        page: int = 1,
        page_size: int = 50,
        sort_order: str = "desc",
        refresh_issued_dates: bool = True,
        table: str = "eng",
    ) -> EcnRecordsResponse:
        bootstrapped = self.ensure_bootstrapped(table=table)
        list_kwargs = dict(search=search.strip(), page=page, page_size=page_size, sort_order=sort_order)
        if status.strip():
            list_kwargs["status"] = status.strip()
        if table != "eng":
            list_kwargs["table"] = table
        records, total = self.repository.list(**list_kwargs)
        # Loading the issued date from every child Google Sheet here turns a
        # paginated MongoDB read into one serial Google API request per row.
        # HTTP callers should leave this disabled and use the MongoDB snapshot;
        # details/edit still refresh the date on demand.
        listed_records = (
            [self._with_sheet_issued_date(record) for record in records]
            if refresh_issued_dates
            else records
        )
        return EcnRecordsResponse(
            records=listed_records,
            total=total,
            page=page,
            page_size=page_size,
            bootstrapped=bootstrapped,
            next_ecn_number=self._next_ecn_number(table=table),
            changed_by_options=self.repository.changed_by_options(table) if table != "eng" else self.repository.changed_by_options(),
            status_options=self.repository.status_options(table) if hasattr(self.repository, "status_options") else [],
            source_url=self._master(table)[2],
            table=table,
        )

    def ensure_bootstrapped(self, *, table: str = "eng") -> bool:
        google_count = self.repository.google_count(table) if table != "eng" else self.repository.google_count()
        if google_count > 0:
            return False
        with self._bootstrap_lock:
            google_count = self.repository.google_count(table) if table != "eng" else self.repository.google_count()
            if google_count > 0:
                return False
            records = self._read_google_records(table=table)
            if not records:
                return False
            self.repository.insert_initial_google_records(records)
            return True

    def check_sync(self, *, table: str = "eng") -> EcnSyncCheckResponse:
        google_records = self._read_google_records(table=table)
        mongo_records = self.repository.master_records(table) if table != "eng" else self.repository.master_records()
        google_by_row = {record.source_row: record for record in google_records}
        mongo_by_row = {record.source_row: record for record in mongo_records}

        missing = [
            self._difference(record)
            for row, record in google_by_row.items()
            if row not in mongo_by_row
        ]
        extra = [
            self._difference(record)
            for row, record in mongo_by_row.items()
            if row not in google_by_row
        ]
        changed: list[EcnSyncDifference] = []
        for row in sorted(google_by_row.keys() & mongo_by_row.keys()):
            google_record = google_by_row[row]
            mongo_record = mongo_by_row[row]
            changed_fields = [
                field
                for field in SOURCE_FIELDS
                if getattr(google_record, field) != getattr(mongo_record, field)
            ]
            if changed_fields:
                changed.append(self._difference(google_record, changed_fields))

        return EcnSyncCheckResponse(
            in_sync=not missing and not extra and not changed,
            google_total=len(google_records),
            mongodb_total=len(mongo_records),
            missing_count=len(missing),
            extra_count=len(extra),
            changed_count=len(changed),
            missing_in_mongodb=missing[:100],
            extra_in_mongodb=extra[:100],
            changed=changed[:100],
            checked_at=datetime.now(timezone.utc),
            source_url=self._master(table)[2],
        )

    def sync_from_google(self, *, table: str = "eng") -> EcnSyncCheckResponse:
        logger.info("ECN 同步任务开始: table=%s", table)
        records = self._read_google_records(table=table)
        if hasattr(self.repository, "sync_google_records"):
            self.repository.sync_google_records(records, table)
        else:
            self.repository.insert_initial_google_records(records)
        logger.info("ECN 同步任务完成: table=%s, records=%s", table, len(records))
        return self.check_sync(table=table)

    def get_record_for_edit(self, record_id: str) -> EcnRecord:
        record = self.repository.find_by_id(record_id)
        if record is None:
            raise EcnValidationError("ECN 记录不存在")
        record = self._with_sheet_issued_date(record)
        sheet_id = self.driver.parse_drive_file_id(record.record_url)
        if not sheet_id:
            return record
        try:
            titles = {item.get("title") for item in self.driver.get_sheet_metadata(sheet_id)}
            sheet_title = next((name for name in (ECN_TEMPLATE_SHEET_TITLE, "ECN") if name in titles), "")
            if not sheet_title:
                return record
            categories = self.driver.read_spreadsheet_values(sheet_id, f"'{sheet_title}'!P24:BV24")
            documents = self.driver.read_spreadsheet_values(sheet_id, f"'{sheet_title}'!B88:BD88")
        except GoogleDriverError:
            return record
        category_cells = categories[0] if categories else []
        document_cells = documents[0] if documents else []
        category = next((option for option, column in zip(ECN_CHANGE_CATEGORY_CELLS, (0, 13, 26, 40, 58))
                         if len(category_cells) > column and category_cells[column].strip().upper() == "TRUE"), None)
        document = next((option for option, column in zip(ECN_AFFECTED_DOCUMENT_CELLS, (0, 12, 24, 38, 54))
                         if len(document_cells) > column and document_cells[column].strip().upper() == "TRUE"), None)
        return record.model_copy(update={"change_category": category, "affected_document": document})

    def create_ecn(self, payload: EcnCreateRequest, *, table: str = "eng") -> EcnCreateResponse:
        logger.info("ECN 创建任务开始: number=%s, title=%s", payload.ecn_number, payload.ecn_title)
        ecn_number = normalize_ecn_number(payload.ecn_number, allow_bare=False)
        if not ecn_number or not ECN_NUMBER_PATTERN.fullmatch(payload.ecn_number.strip()):
            raise EcnValidationError("ECN 编号格式应为 ECN-0577 或 ECN0577")
        title = re.sub(r"\s+", " ", payload.ecn_title).strip()
        if not title:
            raise EcnValidationError("ECN 标题不能为空")
        if any(character in title for character in ("\x00", "\r", "\n")):
            raise EcnValidationError("ECN 标题不能包含换行或控制字符")
        product_model = re.sub(r"\s+", " ", payload.product_model).strip()
        if not product_model:
            raise EcnValidationError("产品型号不能为空")
        if any(character in product_model for character in ("\x00", "\r", "\n")):
            raise EcnValidationError("产品型号不能包含换行或控制字符")
        changed_by = re.sub(r"\s+", " ", payload.changed_by).strip()
        if not changed_by:
            raise EcnValidationError("变更人不能为空")
        change_item = re.sub(r"\s+", " ", payload.change_item).strip()
        before_change = re.sub(r"\s+", " ", payload.before_change).strip()
        after_change = re.sub(r"\s+", " ", payload.after_change).strip()

        with self._creation_lock:
            master_id, master_gid, _ = self._master(table)
            self.ensure_bootstrapped(table=table)
            existing = self.repository.find_by_number(ecn_number, table) if table != "eng" else self.repository.find_by_number(ecn_number)
            if existing is not None:
                raise EcnConflictError(f"ECN 编号已存在: {ecn_number}")
            expected_number = self._next_ecn_number(table=table)
            if ecn_number != expected_number:
                raise EcnValidationError(
                    f"ECN 编号必须连续，当前应为 {expected_number}"
                )

            local_now = datetime.now(ZoneInfo("Asia/Shanghai"))
            change_date = (payload.change_date or local_now.date()).strftime("%Y/%m/%d")
            year = local_now.year
            year_folder_name = f"{year} ECN"
            year_folder = self.driver.find_folder(ECN_FOLDER_ID, year_folder_name)
            year_folder_created = year_folder is None
            if year_folder is None:
                logger.info("ECN 创建任务: 正在创建年份目录 %s", year_folder_name)
                year_folder = self.driver.create_folder(ECN_FOLDER_ID, year_folder_name)

            folder_name = f"{ecn_number} {title}"
            existing_folder = self.driver.find_folder_by_prefix(
                year_folder.id,
                f"{ecn_number} ",
            )
            if existing_folder is not None:
                raise EcnConflictError(f"Google Drive 目录已存在: {existing_folder.name}")
            ecn_folder = self.driver.create_folder(year_folder.id, folder_name)
            logger.info("ECN 创建任务: 正在复制 ECN 模板到目录 %s", folder_name)
            spreadsheet = self.driver.copy_file(
                ECN_TEMPLATE_SPREADSHEET_ID,
                ecn_folder.id,
                folder_name,
            )
            checkbox_values = {
                f"'{ECN_TEMPLATE_SHEET_TITLE}'!{cell}": "TRUE" if payload.change_category == option else "FALSE"
                for option, cell in ECN_CHANGE_CATEGORY_CELLS.items()
            }
            checkbox_values.update({
                f"'{ECN_TEMPLATE_SHEET_TITLE}'!{cell}": "TRUE" if payload.affected_document == option else "FALSE"
                for option, cell in ECN_AFFECTED_DOCUMENT_CELLS.items()
            })
            self.driver.update_spreadsheet_values(
                spreadsheet.id,
                {
                    ECN_PRODUCT_MODEL_RANGE: product_model,
                    ECN_NUMBER_RANGE: ecn_number,
                    ECN_ISSUED_DATE_RANGE: change_date,
                    **checkbox_values,
                },
            )
            logger.info("ECN 创建任务: ECN 子表格初始化完成，正在追加总表行")
            master = self.driver.read_sheet_by_gid(master_id, master_gid)
            master_values = [
                "", product_model, "ECN", folder_name, change_item, before_change,
                after_change, change_date, changed_by, "",
                f'=HYPERLINK("https://docs.google.com/spreadsheets/d/{spreadsheet.id}/edit","Link")', "",
            ]
            # The master sheet's usable-row rule is the D column: find the
            # last row whose D cell has content, then write immediately after
            # it. This avoids append() choosing a distant formatted row and
            # avoids reusing an unrelated blank row in the middle of the list.
            populated_rows = [
                row_number
                for row_number, row in enumerate(master.cells[4:], start=5)
                if len(row) > 3 and (row[3].value or "").strip()
            ]
            source_row = (max(populated_rows) + 1) if populated_rows else 5
            write_row = getattr(self.driver, "write_spreadsheet_row", None)
            if callable(write_row):
                source_row = write_row(
                    master_id, master.title, source_row, master_values,
                )
            else:
                # Compatibility for lightweight drivers used by older callers.
                source_row = self.driver.append_spreadsheet_row(
                    master_id, master.title, master_values,
                )
            logger.info("ECN 创建任务: 总表新增第 %s 行，F/G 已写入", source_row)
            now = datetime.now(timezone.utc)
            record = EcnRecord(
                id=f"created:{ecn_number}" if table == "eng" else f"created:{table}:{ecn_number}",
                table=table,
                source_row=source_row,
                ecn_number=ecn_number,
                ecn_title=title,
                product_name=product_model,
                change_item=change_item,
                before_change=before_change,
                after_change=after_change,
                change_date=change_date,
                changed_by=changed_by,
                change_category=payload.change_category,
                affected_document=payload.affected_document,
                category="ECN",
                form_number=folder_name,
                record_url=spreadsheet.web_view_link or (
                    f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}/edit"
                ),
                folder_id=ecn_folder.id,
                origin="created",
                created_at=now,
                updated_at=now,
            )
            self.repository.insert_created(record)
            logger.info("ECN 创建任务完成: number=%s, source_row=%s", ecn_number, source_row)
            return EcnCreateResponse(
                record=record,
                year_folder_created=year_folder_created,
                folder_url=ecn_folder.web_view_link or (
                    f"https://drive.google.com/drive/folders/{ecn_folder.id}"
                ),
                spreadsheet_url=record.record_url,
            )

    def update_ecn(self, record_id: str, payload: EcnUpdateRequest) -> EcnRecord:
        with self._creation_lock:
            record = self.repository.find_by_id(record_id)
            if record is None:
                raise EcnValidationError("ECN 记录不存在")
            values = {key: re.sub(r"\s+", " ", value).strip() if isinstance(value, str) else value
                      for key, value in payload.model_dump(exclude_unset=True).items()}
            if not values["ecn_title"]:
                raise EcnValidationError("ECN 标题不能为空")
            updated = record.model_copy(update={
                **values,
                "form_number": f"{record.ecn_number} {values['ecn_title']}",
                "updated_at": datetime.now(timezone.utc),
            })
            sheet_id = self.driver.parse_drive_file_id(record.record_url)
            sheet_values: dict[str, str] = {}
            options_changed = any(
                key in values and getattr(updated, key) != getattr(record, key)
                for key in ("change_category", "affected_document")
            )
            date_changed = updated.change_date != record.change_date
            if sheet_id and (record.origin == "created" or options_changed or date_changed):
                sheet_title = ECN_TEMPLATE_SHEET_TITLE
                if record.origin != "created":
                    titles = {item.get("title") for item in self.driver.get_sheet_metadata(sheet_id)}
                    sheet_title = next((name for name in (ECN_TEMPLATE_SHEET_TITLE, "ECN") if name in titles), "")
                    if not sheet_title:
                        raise EcnConflictError("找不到 ECN 子表格工作表")
                if record.origin == "created":
                    sheet_values[f"'{sheet_title}'!M14:AD17"] = values["product_name"]
                if date_changed:
                    sheet_values[f"'{sheet_title}'!BW18:CN21"] = values["change_date"]
                if "change_category" in values and (record.origin == "created" or options_changed):
                    sheet_values.update({
                        f"'{sheet_title}'!{cell}": "TRUE" if values["change_category"] == option else "FALSE"
                        for option, cell in ECN_CHANGE_CATEGORY_CELLS.items()
                    })
                if "affected_document" in values and (record.origin == "created" or options_changed):
                    sheet_values.update({
                        f"'{sheet_title}'!{cell}": "TRUE" if values["affected_document"] == option else "FALSE"
                        for option, cell in ECN_AFFECTED_DOCUMENT_CELLS.items()
                    })
            if record.source_row:
                master_id, master_gid, _ = self._master(record.table)
                sheet = self.driver.read_sheet_by_gid(master_id, master_gid)
                self._assert_source_row(sheet, record)
                row = record.source_row
                title = self.driver._quote_sheet_title(sheet.title)
                columns = {"product_name": "B", "form_number": "D", "change_item": "E",
                           "before_change": "F", "after_change": "G", "change_date": "H",
                           "changed_by": "I", "approved_by": "J", "duro_number": "L"}
                self.driver.update_spreadsheet_values(master_id, {
                    f"{title}!{column}{row}": str(getattr(updated, field))
                    for field, column in columns.items()
                })
            if sheet_id and sheet_values:
                self.driver.update_spreadsheet_values(sheet_id, sheet_values)
                with self._issued_date_lock:
                    self._issued_date_cache.pop(sheet_id, None)
            if record.origin == "created":
                if not sheet_id:
                    raise EcnConflictError("找不到 ECN 子表格")
                if updated.ecn_title != record.ecn_title:
                    folder_id = self._resolve_folder_id(record)
                    if not folder_id:
                        raise EcnConflictError("无法确认 ECN 对应目录")
                    self.driver.rename_file(folder_id, updated.form_number)
                    self.driver.rename_file(sheet_id, updated.form_number)
            self.repository.replace(updated)
            return updated

    def _with_sheet_issued_date(self, record: EcnRecord) -> EcnRecord:
        sheet_id = self.driver.parse_drive_file_id(record.record_url)
        if not sheet_id:
            return record
        with self._issued_date_lock:
            cached = self._issued_date_cache.get(sheet_id)
            if cached and monotonic() - cached[0] < ISSUED_DATE_CACHE_SECONDS:
                issued_date = cached[1]
            else:
                try:
                    rows = self.driver.read_spreadsheet_values(sheet_id, ECN_ISSUED_DATE_READ_RANGE)
                except GoogleDriverError:
                    try:
                        rows = self.driver.read_spreadsheet_values(sheet_id, "A1:CN30")
                    except GoogleDriverError:
                        return record
                    issued_date = self._find_issued_date(rows)
                else:
                    issued_date = rows[0][0].strip() if rows and rows[0] else ""
                self._issued_date_cache[sheet_id] = (monotonic(), issued_date)
        return record.model_copy(update={"change_date": issued_date})

    @staticmethod
    def _find_issued_date(rows: list[list[str]]) -> str:
        for row in rows:
            for index, cell in enumerate(row):
                if any(label in cell for label in ISSUED_DATE_LABELS):
                    for candidate in row[index + 1:]:
                        value = candidate.strip()
                        if ISSUED_DATE_PATTERN.search(value):
                            return value
        return ""

    def delete_ecn(self, record_id: str) -> None:
        with self._creation_lock:
            logger.info("ECN 删除任务开始: record_id=%s", record_id)
            record = self.repository.find_by_id(record_id)
            if record is None:
                raise EcnValidationError("ECN 记录不存在")
            logger.info("ECN 删除任务: 已找到记录 number=%s, title=%s", record.ecn_number, record.ecn_title)
            latest = self.repository.max_sequence_number(record.table) if record.table != "eng" else self.repository.max_sequence_number()
            record_match = re.fullmatch(r"ECN-(\d+)", record.ecn_number)
            if record_match is None or int(record_match.group(1)) != latest:
                raise EcnConflictError("只能删除编号最大的最后一条 ECN")
            logger.info("ECN 删除任务: 已确认这是最新编号 %s", record.ecn_number)
            folder_id = self._resolve_folder_id(record)
            if not folder_id:
                raise EcnConflictError("无法确认 ECN 对应目录，已取消删除")
            logger.info("ECN 删除任务: 已定位 ECN 目录 folder_id=%s", folder_id)
            sheet_id = self.driver.parse_drive_file_id(record.record_url)
            if not sheet_id or self.driver.get_file_parent(sheet_id) != folder_id:
                raise EcnConflictError("无法确认 ECN 子表格属于对应目录，已取消删除")
            logger.info("ECN 删除任务: 已确认子表格归属 sheet_id=%s", sheet_id)
            sheet_file = self.driver.get_file_metadata(sheet_id)
            if sheet_file.mime_type != "application/vnd.google-apps.spreadsheet":
                raise EcnConflictError("对应文件不是 Google 表格，已取消删除")

            # The MongoDB record and the ECN child sheet/folder are the primary
            # deletion targets. Do not block these deletions on the optional
            # presence or consistency of a row in the Google master sheet.
            logger.info("ECN 删除任务: 正在删除 ECN 子表 sheet_id=%s", sheet_id)
            self.driver.trash_file(sheet_id)
            logger.info("ECN 删除任务: ECN 子表已移入回收站 sheet_id=%s", sheet_id)
            logger.info("ECN 删除任务: 正在删除 ECN 目录 folder_id=%s", folder_id)
            self.driver.trash_file(folder_id)
            logger.info("ECN 删除任务: ECN 目录已移入回收站 folder_id=%s", folder_id)
            logger.info("ECN 删除任务: 正在删除 MongoDB 记录 number=%s", record.ecn_number)
            self.repository.delete(record_id)
            logger.info("ECN 删除任务: MongoDB 记录已删除 number=%s", record.ecn_number)

            # The master sheet is a secondary index. It may already be missing
            # or have been edited independently, so remove a matching row only
            # when one is present. A read failure must not undo the completed
            # primary deletion.
            try:
                logger.info("ECN 删除任务: 正在检查 Google 总表 number=%s", record.ecn_number)
                master_id, master_gid, _ = self._master(record.table)
                master_sheet = self.driver.read_sheet_by_gid(
                    master_id, master_gid,
                )
                matches = [
                    parsed.source_row
                    for row_number, row in enumerate(master_sheet.cells[4:], start=5)
                    if (parsed := self._parse_source_row(row_number, row, table=record.table)) is not None
                    and parsed.ecn_number == record.ecn_number
                ]
                source_row = record.source_row if record.source_row in matches else (matches[0] if matches else 0)
                if source_row:
                    logger.info("ECN 删除任务: 找到 Google 总表行 row=%s，正在删除", source_row)
                    self.driver.delete_spreadsheet_row(
                        master_id, master_gid, source_row,
                    )
                    logger.info("ECN 删除任务: Google 总表行已删除 row=%s", source_row)
                else:
                    logger.info("ECN 删除任务: Google 总表未找到 %s，跳过总表清理", record.ecn_number)
            except GoogleDriverError as exc:
                logger.warning("ECN 主表清理跳过: number=%s, error=%s", record.ecn_number, exc)
            logger.info("ECN 删除任务完成: number=%s", record.ecn_number)

    def _resolve_folder_id(self, record: EcnRecord) -> str | None:
        folder_id = record.folder_id or self.driver.get_file_parent(record.record_url)
        if not folder_id:
            return None
        year_folder_id = self.driver.get_file_parent(folder_id)
        if not year_folder_id or self.driver.get_file_parent(year_folder_id) != ECN_FOLDER_ID:
            return None
        folder = self.driver.get_file_metadata(folder_id)
        return folder_id if folder.name.startswith(record.ecn_number) else None

    @staticmethod
    def _assert_source_row(sheet: GoogleSheetData, record: EcnRecord) -> None:
        if record.source_row > len(sheet.cells):
            raise EcnConflictError("Google 总表行已变化，请先核对同步")
        current = EcnService._parse_source_row(record.source_row, sheet.cells[record.source_row - 1], table=record.table)
        if current is None or current.ecn_number != record.ecn_number:
            raise EcnConflictError("Google 总表行与 ECN 编号不一致，请先核对同步")

    def _next_ecn_number(self, *, table: str = "eng") -> str:
        latest = self.repository.max_sequence_number(table) if table != "eng" else self.repository.max_sequence_number()
        return f"ECN-{(latest or 0) + 1:04d}"

    def _read_google_records(self, *, table: str = "eng") -> list[EcnRecord]:
        master_id, master_gid, _ = self._master(table)
        sheet = self.driver.read_sheet_by_gid(master_id, master_gid)
        if table == "ipqc":
            return self._read_ipqc_records(sheet)
        records: list[EcnRecord] = []
        for source_row, row in enumerate(sheet.cells[4:], start=5):
            record = self._parse_source_row(source_row, row, table=table)
            if record is not None:
                records.append(record)
        return records

    def _read_ipqc_records(self, sheet: GoogleSheetData) -> list[EcnRecord]:
        """Read IPQC rows using the actual field titles in row 4."""
        if len(sheet.cells) < 4:
            return []
        headers = {
            self._header_key(cell.value): index
            for index, cell in enumerate(sheet.cells[3])
            if self._header_key(cell.value)
        }
        aliases = {
            "serial": ("序号", "编号", "no", "no."),
            "ecn_number": ("ecn编号", "ecn单号", "编号", "ecnno", "ecnnumber"),
            "ecn_title": ("ec标题", "ecn标题", "标题", "变更标题", "变更内容"),
            "product_name": ("产品型号", "产品名称", "产品", "机型", "productmodel"),
            "category": ("变更类别", "类别", "类型", "category"),
            "issuer": ("发行人", "ecn发行人", "issuer"),
            "purpose": ("变更目的", "目的", "purpose"),
            "handling": ("处置方式", "处理方式", "handling"),
            "change_item": ("变更项目", "变更项", "changeitem", "变更内容"),
            "before_change": ("变更前", "变更前内容", "beforechange"),
            "after_change": ("变更后", "变更后内容", "afterchange"),
            "change_date": ("变更日期", "发出日期", "日期", "changedate", "issueddate"),
            "actual_date": ("执行日期", "实际执行日期", "ecn实际执行日期", "actualdate"),
            "verify_date": ("验证日期", "verifydate"),
            "status": ("状态", "status"),
            "notes": ("备注", "说明", "notes", "note"),
            "changed_by": ("变更人", "变更者", "changedby", "owner"),
            "approved_by": ("批准人", "审核人", "approvedby"),
            "record_url": ("链接", "表格链接", "sheet链接", "url", "link"),
            "duro_number": ("duro编号", "duroeco", "eco编号", "dco编号"),
        }
        columns = {
            field: next((headers[key] for alias in names if (key := self._header_key(alias)) in headers), None)
            for field, names in aliases.items()
        }
        records: list[EcnRecord] = []
        for source_row, row in enumerate(sheet.cells[4:], start=5):
            # The IPQC master sheet may contain formatting or formulas well
            # below the actual records. Column Q is the populated-row marker;
            # the first empty Q cell marks the end of the data table.
            if len(row) <= 16 or not (row[16].value or "").strip():
                break
            values = {
                field: (row[index].value or "").strip()
                if index is not None and index < len(row) else ""
                for field, index in columns.items()
            }
            link_index = columns.get("record_url")
            if link_index is not None and link_index < len(row) and row[link_index].hyperlink:
                values["record_url"] = row[link_index].hyperlink or values["record_url"]
            extra_fields = {field: value for field, value in values.items() if value}
            if not any(values.values()):
                continue
            ecn_number = normalize_ecn_number(values["ecn_number"] or values["ecn_title"])
            if not ecn_number:
                continue
            form_number = values["ecn_number"] or ecn_number
            title = values["ecn_title"]
            if not title and form_number:
                title = form_number
            records.append(EcnRecord(
                id=f"google:{sheet.spreadsheet_id}:{sheet.sheet_id}:{source_row}",
                table="ipqc", source_row=source_row, ecn_number=ecn_number,
                ecn_title=title, product_name=values["product_name"],
                category=values["category"] or "ECN", form_number=form_number,
                change_item=values["change_item"], before_change=values["before_change"],
                after_change=values["after_change"], change_date=values["change_date"],
                changed_by=values["changed_by"], approved_by=values["approved_by"],
                record_url=values["record_url"], duro_number=values["duro_number"],
                origin="google", extra_fields=extra_fields,
            ))
        return records

    @staticmethod
    def _header_key(value: str) -> str:
        return re.sub(r"[\s_\-:/：（）()]+", "", (value or "").strip().lower())

    @staticmethod
    def _parse_source_row(source_row: int, row: list[GoogleSheetCell], *, table: str = "eng") -> EcnRecord | None:
        cells = [*row, *([GoogleSheetCell()] * max(0, 12 - len(row)))]
        values = [re.sub(r"\s+", " ", cell.value or "").strip() for cell in cells]
        if not any(values[1:12]):
            return None
        form_number = values[3]
        ecn_number = normalize_ecn_number(form_number)
        ecn_title = ""
        if ecn_number:
            match = ECN_NUMBER_PATTERN.search(form_number)
            if match:
                ecn_title = form_number[match.end():].strip(" -_:：－—")
        link_cell = cells[10]
        record_url = link_cell.hyperlink or ""
        if not record_url and values[10].startswith(("https://", "http://")):
            record_url = values[10]
        meaningful_values = (
            ecn_title,
            values[1],
            values[4],
            values[5],
            values[6],
            values[7],
            values[8],
            values[9],
            record_url,
            values[11],
        )
        if not any(meaningful_values):
            return None
        master_id, master_gid, _ = EcnService._master(table)
        return EcnRecord(
            id=f"google:{master_id}:{master_gid}:{source_row}",
            table=table,
            source_row=source_row,
            ecn_number=ecn_number,
            ecn_title=ecn_title,
            product_name=values[1],
            category=values[2],
            form_number=form_number,
            change_item=values[4],
            before_change=values[5],
            after_change=values[6],
            change_date=values[7],
            changed_by=values[8],
            approved_by=values[9],
            record_url=record_url,
            duro_number=values[11],
            origin="google",
        )

    @staticmethod
    def _difference(
        record: EcnRecord,
        changed_fields: list[str] | None = None,
    ) -> EcnSyncDifference:
        return EcnSyncDifference(
            source_row=record.source_row,
            ecn_number=record.ecn_number,
            form_number=record.form_number,
            changed_fields=changed_fields or [],
        )
