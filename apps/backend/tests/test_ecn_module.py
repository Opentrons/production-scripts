from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from core.google import GoogleDriveFile, GoogleDriverError, GoogleSheetCell, GoogleSheetData
from modules.ecn.definition import ECN_FOLDER_ID
from modules.ecn.models import EcnCreateRequest, EcnRecord, EcnUpdateRequest
from modules.ecn.service import (
    ECN_CREATED_DATE_RANGE,
    ECN_CHANGE_CATEGORY_CELLS,
    ECN_AFFECTED_DOCUMENT_CELLS,
    ECN_MASTER_SHEET_GID,
    ECN_MASTER_SPREADSHEET_ID,
    ECN_NUMBER_RANGE,
    ECN_PRODUCT_MODEL_RANGE,
    ECN_TEMPLATE_SPREADSHEET_ID,
    EcnConflictError,
    EcnService,
    EcnValidationError,
)


class MemoryEcnRepository:
    def __init__(self, records: list[EcnRecord] | None = None) -> None:
        self.records = {record.id: record for record in records or []}

    def google_count(self) -> int:
        return sum(record.origin == "google" for record in self.records.values())

    def insert_initial_google_records(self, records: list[EcnRecord]) -> int:
        inserted = 0
        for record in records:
            if record.id not in self.records:
                self.records[record.id] = record
                inserted += 1
        return inserted

    def list(self, *, search: str, page: int, page_size: int, sort_order: str):
        records = list(self.records.values())
        if search:
            query = search.casefold()
            records = [
                record for record in records
                if query in " ".join((
                    record.ecn_number,
                    record.ecn_title,
                    record.product_name,
                    record.change_item,
                )).casefold()
            ]
        records.sort(
            key=lambda record: (
                int(match.group())
                if (match := re.search(r"\d+", record.ecn_number))
                else -1,
                record.source_row,
            ),
            reverse=sort_order == "desc",
        )
        start = (page - 1) * page_size
        return records[start:start + page_size], len(records)

    def find_by_number(self, ecn_number: str):
        return next(
            (record for record in self.records.values() if record.ecn_number == ecn_number),
            None,
        )

    def max_sequence_number(self) -> int | None:
        numbers = [
            int(match.group())
            for record in self.records.values()
            if (match := re.search(r"\d+", record.ecn_number))
        ]
        return max(numbers, default=None)

    def changed_by_options(self) -> list[str]:
        return sorted({record.changed_by for record in self.records.values() if record.changed_by})

    def insert_created(self, record: EcnRecord) -> None:
        self.records[record.id] = record

    def google_records(self) -> list[EcnRecord]:
        return [record for record in self.records.values() if record.origin == "google"]

    def master_records(self) -> list[EcnRecord]:
        return [record for record in self.records.values() if record.source_row > 0]

    def find_by_id(self, record_id: str) -> EcnRecord | None:
        return self.records.get(record_id)

    def replace(self, record: EcnRecord) -> None:
        self.records[record.id] = record

    def delete(self, record_id: str) -> None:
        del self.records[record_id]


class FakeEcnDriver:
    def __init__(self, rows: list[list[GoogleSheetCell]]) -> None:
        self.rows = rows
        self.folders: dict[tuple[str, str], GoogleDriveFile] = {}
        self.created_folders: list[tuple[str, str]] = []
        self.copies: list[tuple[str, str, str]] = []
        self.sheet_writes: list[tuple[str, dict[str, str]]] = []
        self.trashed: list[str] = []
        self.deleted_rows: list[int] = []
        self.renamed_files: list[tuple[str, str]] = []
        self.issued_dates: dict[str, str] = {}
        self.checkbox_values: dict[str, dict[str, str]] = {}
        self.legacy_sheets: set[str] = set()

    def read_sheet_by_gid(self, spreadsheet_id: str, sheet_gid: int) -> GoogleSheetData:
        assert spreadsheet_id == ECN_MASTER_SPREADSHEET_ID
        assert sheet_gid == ECN_MASTER_SHEET_GID
        return GoogleSheetData(
            spreadsheet_id=spreadsheet_id,
            sheet_id=sheet_gid,
            title="ECN Records",
            cells=[[], [], [], [], *self.rows],
        )

    def get_sheet_metadata(self, spreadsheet_id: str) -> list[dict[str, str]]:
        return [{"title": "ECN" if spreadsheet_id == "record" else "工程变更通知单"}]

    def find_folder(self, parent_id: str, name: str):
        return self.folders.get((parent_id, name))

    def find_folder_by_prefix(self, parent_id: str, name_prefix: str):
        return next(
            (
                folder
                for (candidate_parent, _), folder in self.folders.items()
                if candidate_parent == parent_id and folder.name.startswith(name_prefix)
            ),
            None,
        )

    def create_folder(self, parent_id: str, name: str) -> GoogleDriveFile:
        self.created_folders.append((parent_id, name))
        folder = GoogleDriveFile(
            id=f"folder-{len(self.created_folders)}",
            name=name,
            mime_type="application/vnd.google-apps.folder",
            web_view_link=f"https://drive.google.com/drive/folders/folder-{len(self.created_folders)}",
        )
        self.folders[(parent_id, name)] = folder
        return folder

    def copy_file(self, file_id: str, parent_id: str, name: str) -> GoogleDriveFile:
        self.copies.append((file_id, parent_id, name))
        return GoogleDriveFile(
            id="new-sheet",
            name=name,
            mime_type="application/vnd.google-apps.spreadsheet",
            web_view_link="https://docs.google.com/spreadsheets/d/new-sheet/edit",
        )

    def update_spreadsheet_values(
        self,
        spreadsheet_id: str,
        values_by_range: dict[str, str],
    ) -> None:
        self.sheet_writes.append((spreadsheet_id, values_by_range))
        self.checkbox_values.setdefault(spreadsheet_id, {}).update(values_by_range)
        for range_name, value in values_by_range.items():
            if range_name.endswith("!BW18:CN21"):
                self.issued_dates[spreadsheet_id] = value

    def read_spreadsheet_values(self, spreadsheet_id: str, range_name: str) -> list[list[str]]:
        if range_name.endswith("!P24:BV24") or range_name.endswith("!B88:BD88"):
            columns = ("P24", "AC24", "AP24", "BD24", "BV24") if "24:" in range_name else ("B88", "N88", "Z88", "AN88", "BD88")
            offsets = (0, 13, 26, 40, 58) if "24:" in range_name else (0, 12, 24, 38, 54)
            row = [""] * (offsets[-1] + 1)
            title = range_name.split("!")[0]
            for column, offset in zip(columns, offsets):
                row[offset] = self.checkbox_values.get(spreadsheet_id, {}).get(f"{title}!{column}", "")
            return [row]
        if spreadsheet_id in self.legacy_sheets:
            if range_name == "'工程变更通知单'!BW18":
                raise GoogleDriverError("sheet title differs")
            assert range_name == "A1:CN30"
            return [["发出日期\nSend Date", "", self.issued_dates.get(spreadsheet_id, "")]]
        assert range_name == "'工程变更通知单'!BW18"
        return [[self.issued_dates.get(spreadsheet_id, "")]]

    def append_spreadsheet_row(self, spreadsheet_id: str, sheet_title: str, values: list[str]) -> int:
        cells = [GoogleSheetCell(value=value) for value in values]
        cells[10] = GoogleSheetCell(value="Link", hyperlink="https://docs.google.com/spreadsheets/d/new-sheet/edit")
        self.rows.append(cells)
        return len(self.rows) + 4

    def get_file_parent(self, file_id: str) -> str | None:
        if file_id == "folder-2": return "folder-1"
        if file_id == "folder-1": return ECN_FOLDER_ID
        return "folder-2"

    def get_file_metadata(self, file_id: str) -> GoogleDriveFile:
        if file_id == "new-sheet":
            return GoogleDriveFile(id=file_id, name="ECN sheet", mime_type="application/vnd.google-apps.spreadsheet")
        return next(folder for folder in self.folders.values() if folder.id == file_id)

    def trash_file(self, file_id: str) -> None:
        self.trashed.append(file_id)

    def rename_file(self, file_id: str, name: str) -> None:
        self.renamed_files.append((file_id, name))

    def delete_spreadsheet_row(self, spreadsheet_id: str, sheet_gid: int, row: int) -> None:
        self.deleted_rows.append(row)
        self.rows.pop(row - 5)

    @staticmethod
    def parse_drive_file_id(url: str) -> str | None:
        if "new-sheet" in url:
            return "new-sheet"
        return "record" if "/record/" in url else None

    @staticmethod
    def _quote_sheet_title(title: str) -> str:
        return f"'{title}'"


def source_row(
    form_number: str = "ECN-0577 913-00061 Drawing Update",
    *,
    product: str = "OT3",
    change_item: str = "D13、D18 Diode",
) -> list[GoogleSheetCell]:
    values = [
        "",
        product,
        "ECN",
        form_number,
        change_item,
        "D2.0",
        "D2.2",
        "2026/10/14",
        "Leo",
        "Frank",
        "Link",
        "ECO-123",
    ]
    cells = [GoogleSheetCell(value=value) for value in values]
    cells[10] = GoogleSheetCell(
        value="Link",
        hyperlink="https://docs.google.com/spreadsheets/d/record/edit",
    )
    return cells


def test_first_list_imports_google_master_into_repository() -> None:
    repository = MemoryEcnRepository()
    service = EcnService(repository, FakeEcnDriver([source_row()]))  # type: ignore[arg-type]

    response = service.list_records()

    assert response.bootstrapped is True
    assert response.total == 1
    assert response.storage == "mongodb"
    assert response.records[0].ecn_number == "ECN-0577"
    assert response.records[0].ecn_title == "913-00061 Drawing Update"
    assert response.records[0].record_url.endswith("/record/edit")
    assert response.next_ecn_number == "ECN-0578"
    assert response.changed_by_options == ["Leo"]


def test_sync_check_reports_changed_and_missing_rows() -> None:
    google_driver = FakeEcnDriver([
        source_row(),
        source_row("ECN-0578 Software Update", product="Pipette"),
    ])
    stored = EcnService._parse_source_row(5, source_row(change_item="Old value"))
    assert stored is not None
    repository = MemoryEcnRepository([stored])
    service = EcnService(repository, google_driver)  # type: ignore[arg-type]

    result = service.check_sync()

    assert result.in_sync is False
    assert result.google_total == 2
    assert result.mongodb_total == 1
    assert result.changed[0].changed_fields == ["change_item"]
    assert result.missing_in_mongodb[0].ecn_number == "ECN-0578"


def test_create_ecn_creates_year_folder_record_folder_and_template_copy() -> None:
    repository = MemoryEcnRepository()
    driver = FakeEcnDriver([source_row("ECN-0576 Existing")])
    service = EcnService(repository, driver)  # type: ignore[arg-type]

    result = service.create_ecn(
        EcnCreateRequest(
            ecn_number="ecn-0577",
            ecn_title="913-00061   Drawing Update",
            product_model="Flex",
            change_item="  D13、D18   Diode  ",
            change_date=date(2026, 10, 18),
            changed_by="Leo",
            change_category="drawing",
            affected_document="sop",
        )
    )

    year = datetime.now(ZoneInfo("Asia/Shanghai")).year
    assert driver.created_folders[0][1] == f"{year} ECN"
    assert driver.created_folders[1][1] == "ECN-0577 913-00061 Drawing Update"
    assert driver.copies == [
        (
            ECN_TEMPLATE_SPREADSHEET_ID,
            "folder-2",
            "ECN-0577 913-00061 Drawing Update",
        )
    ]
    assert result.record.origin == "created"
    assert result.record.product_name == "Flex"
    assert result.record.change_item == "D13、D18 Diode"
    assert result.record.change_date == "2026/10/18"
    assert result.record.changed_by == "Leo"
    assert result.record.change_category == "drawing"
    assert result.record.affected_document == "sop"
    assert result.spreadsheet_url.endswith("/new-sheet/edit")
    assert repository.find_by_number("ECN-0577") is not None
    sheet_id, written = driver.sheet_writes[0]
    assert sheet_id == "new-sheet"
    assert written[ECN_PRODUCT_MODEL_RANGE] == "Flex"
    assert written[ECN_NUMBER_RANGE] == "ECN-0577"
    assert written[ECN_CREATED_DATE_RANGE] == "2026/10/18"
    for option, cell in ECN_CHANGE_CATEGORY_CELLS.items():
        assert written[f"'工程变更通知单'!{cell}"] == ("TRUE" if option == "drawing" else "FALSE")
    for option, cell in ECN_AFFECTED_DOCUMENT_CELLS.items():
        assert written[f"'工程变更通知单'!{cell}"] == ("TRUE" if option == "sop" else "FALSE")
    assert driver.rows[-1][4].value == "D13、D18 Diode"
    assert driver.rows[-1][7].value == "2026/10/18"
    assert driver.rows[-1][8].value == "Leo"
    listed = service.list_records().records[0]
    assert (listed.change_item, listed.change_date, listed.changed_by) == (
        "D13、D18 Diode", "2026/10/18", "Leo",
    )
    assert service.check_sync().in_sync is True


def test_list_uses_issued_date_from_ecn_spreadsheet() -> None:
    repository = MemoryEcnRepository()
    driver = FakeEcnDriver([source_row()])
    driver.issued_dates["record"] = "2026/10/16"
    service = EcnService(repository, driver)  # type: ignore[arg-type]

    response = service.list_records()

    assert response.records[0].change_date == "2026/10/16"
    assert repository.find_by_number("ECN-0577").change_date == "2026/10/14"  # type: ignore[union-attr]


def test_list_reads_issued_date_from_older_sheet_title() -> None:
    driver = FakeEcnDriver([source_row()])
    driver.legacy_sheets.add("record")
    driver.issued_dates["record"] = "7/21/2026"
    service = EcnService(MemoryEcnRepository(), driver)  # type: ignore[arg-type]

    assert service.list_records().records[0].change_date == "7/21/2026"


def test_edit_details_prefill_choices_from_existing_sheet() -> None:
    driver = FakeEcnDriver([source_row()])
    driver.legacy_sheets.add("record")
    driver.issued_dates["record"] = "7/21/2026"
    driver.checkbox_values["record"] = {"'ECN'!AP24": "TRUE", "'ECN'!N88": "TRUE"}
    service = EcnService(MemoryEcnRepository(), driver)  # type: ignore[arg-type]
    record_id = service.list_records().records[0].id

    details = service.get_record_for_edit(record_id)

    assert details.change_date == "7/21/2026"
    assert details.change_category == "drawing"
    assert details.affected_document == "bom"


def test_create_ecn_normalizes_number_without_separator_before_database_insert() -> None:
    repository = MemoryEcnRepository()
    driver = FakeEcnDriver([source_row("ECN-0094 Existing")])
    service = EcnService(repository, driver)  # type: ignore[arg-type]

    result = service.create_ecn(
        EcnCreateRequest(
            ecn_number="ECN0095",
            ecn_title="Drawing Update",
            product_model="OT-2",
            changed_by="Leo",
        )
    )

    assert result.record.ecn_number == "ECN-0095"
    assert result.record.id == "created:ECN-0095"
    assert repository.find_by_number("ECN-0095") == result.record
    assert driver.created_folders[1][1] == "ECN-0095 Drawing Update"


def test_create_ecn_rejects_duplicate_number_before_drive_mutation() -> None:
    existing = EcnService._parse_source_row(5, source_row())
    assert existing is not None
    repository = MemoryEcnRepository([existing])
    driver = FakeEcnDriver([source_row()])
    service = EcnService(repository, driver)  # type: ignore[arg-type]

    with pytest.raises(EcnConflictError, match="ECN 编号已存在"):
        service.create_ecn(EcnCreateRequest(
            ecn_number="ECN-0577",
            ecn_title="Duplicate",
            product_model="Flex",
            changed_by="Leo",
        ))

    assert driver.created_folders == []
    assert driver.copies == []


@pytest.mark.parametrize("requested_number", ["ECN-0589", "ECN0589"])
def test_create_ecn_rejects_skipped_number_before_drive_mutation(
    requested_number: str,
) -> None:
    repository = MemoryEcnRepository()
    driver = FakeEcnDriver([source_row("ECN-0557 Existing")])
    service = EcnService(repository, driver)  # type: ignore[arg-type]

    with pytest.raises(EcnValidationError, match="当前应为 ECN-0558"):
        service.create_ecn(
            EcnCreateRequest(
                ecn_number=requested_number,
                ecn_title="Skipped number",
                product_model="Flex",
                changed_by="Leo",
            )
        )

    assert driver.created_folders == []
    assert driver.copies == []


def test_reserved_number_only_rows_are_not_imported() -> None:
    reserved = [GoogleSheetCell(value=value) for value in [
        "", "", "ECN", "ECN-0578", "", "", "", "", "", "", "Link", "",
    ]]

    assert EcnService._parse_source_row(574, reserved) is None


def test_list_records_supports_number_ascending_and_descending() -> None:
    repository = MemoryEcnRepository()
    service = EcnService(repository, FakeEcnDriver([
        source_row("ECN-999 Earlier"),
        source_row("ECN-1000 Later"),
    ]))  # type: ignore[arg-type]

    ascending = service.list_records(sort_order="asc")
    descending = service.list_records(sort_order="desc")

    assert [record.ecn_number for record in ascending.records] == ["ECN-999", "ECN-1000"]
    assert [record.ecn_number for record in descending.records] == ["ECN-1000", "ECN-999"]


def test_delete_only_latest_removes_master_row_folder_and_mongo_record() -> None:
    repository = MemoryEcnRepository()
    driver = FakeEcnDriver([source_row("ECN-0576 Existing")])
    service = EcnService(repository, driver)  # type: ignore[arg-type]
    created = service.create_ecn(EcnCreateRequest(
        ecn_number="ECN-0577", ecn_title="New", product_model="Flex", changed_by="Leo",
    )).record
    assert created.source_row == 6
    with pytest.raises(EcnConflictError, match="只能删除"):
        service.delete_ecn(next(record.id for record in repository.records.values() if record.ecn_number == "ECN-0576"))
    assert driver.trashed == []

    service.delete_ecn(created.id)

    assert driver.trashed == ["new-sheet", "folder-2"]
    assert driver.deleted_rows == [6]
    assert repository.find_by_id(created.id) is None
    assert service.list_records().next_ecn_number == "ECN-0577"


def test_delete_latest_ignores_master_rows_without_an_ecn_number() -> None:
    legacy_row = [GoogleSheetCell(value=value) for value in (
        "", "OT3", "Note", "Legacy row", "", "", "", "", "", "", "", "",
    )]
    repository = MemoryEcnRepository()
    driver = FakeEcnDriver([legacy_row, source_row("ECN-0576 Existing")])
    service = EcnService(repository, driver)  # type: ignore[arg-type]
    created = service.create_ecn(EcnCreateRequest(
        ecn_number="ECN-0577", ecn_title="New", product_model="Flex", changed_by="Leo",
    )).record

    service.delete_ecn(created.id)

    assert repository.find_by_id(created.id) is None
    assert driver.deleted_rows == [7]


def test_new_record_stays_in_sync_with_master_sheet() -> None:
    repository = MemoryEcnRepository()
    service = EcnService(repository, FakeEcnDriver([source_row("ECN-0576 Existing")]))  # type: ignore[arg-type]
    service.create_ecn(EcnCreateRequest(ecn_number="ECN-0577", ecn_title="New", product_model="Flex", changed_by="Leo"))

    assert service.check_sync().in_sync is True


def test_edit_updates_master_sheet_and_mongo() -> None:
    record = EcnService._parse_source_row(5, source_row())
    assert record is not None
    repository = MemoryEcnRepository([record])
    driver = FakeEcnDriver([source_row()])
    service = EcnService(repository, driver)  # type: ignore[arg-type]

    updated = service.update_ecn(record.id, EcnUpdateRequest(
        ecn_title="Updated title", product_name="Flex", change_item="Motor",
        before_change="A", after_change="B", change_date="2026/10/19",
        changed_by="Leo", approved_by="Frank", duro_number="ECO-1",
    ))

    assert updated.ecn_number == "ECN-0577"
    assert repository.find_by_id(record.id) == updated
    assert next(values for sheet_id, values in driver.sheet_writes if sheet_id == ECN_MASTER_SPREADSHEET_ID)["'ECN Records'!D5"] == "ECN-0577 Updated title"


def test_edit_created_ecn_updates_shared_form_options_and_issued_date() -> None:
    repository = MemoryEcnRepository()
    driver = FakeEcnDriver([source_row("ECN-0576 Existing")])
    service = EcnService(repository, driver)  # type: ignore[arg-type]
    created = service.create_ecn(EcnCreateRequest(
        ecn_number="ECN-0577", ecn_title="Initial", product_model="Flex",
        change_item="Original", changed_by="Leo", change_category="drawing",
        affected_document="sop",
    )).record

    updated = service.update_ecn(created.id, EcnUpdateRequest(
        ecn_title="Updated", product_name="Flex", change_item="Motor",
        before_change="A", after_change="B", change_date="2026/10/20",
        changed_by="Leo", change_category="software", affected_document="bom",
        approved_by="Frank", duro_number="ECO-1",
    ))

    assert updated.change_category == "software"
    assert updated.affected_document == "bom"
    assert service.list_records().records[0].change_date == "2026/10/20"
    sheet_id, written = driver.sheet_writes[-1]
    assert sheet_id == "new-sheet"
    assert written[ECN_CREATED_DATE_RANGE] == "2026/10/20"
    assert written["'工程变更通知单'!P24"] == "TRUE"
    assert written["'工程变更通知单'!AP24"] == "FALSE"
    assert written["'工程变更通知单'!N88"] == "TRUE"
    assert written["'工程变更通知单'!Z88"] == "FALSE"
    assert driver.renamed_files == [
        ("folder-2", "ECN-0577 Updated"), ("new-sheet", "ECN-0577 Updated"),
    ]
    details = service.get_record_for_edit(created.id)
    assert details.change_category == "software"
    assert details.affected_document == "bom"
