from __future__ import annotations

import io
from concurrent.futures import CancelledError
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from modules.supplies.models import SupplementaryMaterialCreate
from modules.supplies.repository import SupplementaryMaterialRepository
from modules.supplies.scheduler import SupplementaryMaterialSyncScheduler
from modules.supplies.service import SupplementaryMaterialService, SupplementaryMaterialSyncInProgressError
from modules.supplies.source import (
    GoogleSupplementaryMaterialSource,
    SupplementaryMaterialSourceError,
    parse_material_rows,
)


def material(number, name=""):
    return SupplementaryMaterialCreate(material_number=number, english_name=name)


def test_scan_stops_at_first_completely_empty_row():
    rows = [
        ["物料编号", "英文名称", "中文名称", "EID"],
        [" abc-001 ", "Oil", "油", 3366.0],
        ["ABC-002", "", "", 0],
        [None, "  ", None, None],
        ["MUST-NOT-IMPORT", "Later"],
    ]
    result = parse_material_rows(iter(rows))
    assert [item.material_number for item in result] == ["ABC-001", "ABC-002"]
    assert [item.eid for item in result] == ["3366", "0"]


def test_headers_can_move_and_headerless_first_row_is_data():
    result = parse_material_rows([
        ["EID", "中文名称", "Part Number", "English Name"],
        [123, "胶水", "446-00119", "Glue"],
    ])
    assert result[0].model_dump() == dict(material_number="446-00119", english_name="Glue", chinese_name="胶水", eid="123")
    assert parse_material_rows([["FIRST", "First row"], ["SECOND"]])[0].material_number == "FIRST"


@pytest.mark.parametrize("bad_row", [[None, "Has a name"], [None, None, None, None, "Note in fifth column"]])
def test_partial_row_is_not_treated_as_blank(bad_row):
    with pytest.raises(SupplementaryMaterialSourceError, match="第 2 行"):
        parse_material_rows([["FIRST"], bad_row, ["THIRD"]])


@pytest.mark.parametrize("rows", [[], [[None]], [["物料编号", "英文名称"], [], ["AFTER-BLANK"]]])
def test_empty_source_is_rejected(rows):
    with pytest.raises(SupplementaryMaterialSourceError, match="没有有效料号"):
        parse_material_rows(rows)


def test_identical_duplicate_is_collapsed_and_conflict_rejected():
    assert len(parse_material_rows([["abc", "Glue"], ["ABC", "Glue"]])) == 1
    with pytest.raises(SupplementaryMaterialSourceError, match="重复且内容不一致"):
        parse_material_rows([["ABC", "Glue"], ["ABC", "Oil"]])


def excel_bytes():
    """Minimal XLSX fixture, including a different sheet which must be ignored."""
    stream = io.BytesIO()
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    worksheet = f'''<worksheet xmlns="{namespace}"><sheetData>
      <row r="1"><c r="A1" t="inlineStr"><is><t>物料编号</t></is></c></row>
      <row r="2"><c r="A2" t="inlineStr"><is><t>TARGET</t></is></c></row>
      <row r="3"/>
      <row r="4"><c r="A4" t="inlineStr"><is><t>AFTER-BLANK</t></is></c></row>
    </sheetData></worksheet>'''
    with ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
          <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
          <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
          <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
          <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
        </Types>''')
        archive.writestr("xl/workbook.xml", f'''<workbook xmlns="{namespace}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
          <sheets><sheet name="Other" sheetId="1" r:id="rId1"/><sheet name="辅料料号" sheetId="2" r:id="rId2"/></sheets></workbook>''')
        archive.writestr("xl/_rels/workbook.xml.rels", '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
          <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
        </Relationships>''')
        archive.writestr("xl/worksheets/sheet1.xml", worksheet.replace("TARGET", "WRONG-SHEET"))
        archive.writestr("xl/worksheets/sheet2.xml", worksheet)
    return stream.getvalue()


def test_excel_source_reads_only_target_sheet_and_stops_at_blank():
    driver = SimpleNamespace(
        get_file_metadata=lambda file_id: SimpleNamespace(mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        download_file_bytes=lambda file_id: (None, excel_bytes()),
    )
    source = GoogleSupplementaryMaterialSource(driver, "file-id", 921765553, "辅料料号")
    assert [item.material_number for item in source.read()] == ["TARGET"]
    missing = GoogleSupplementaryMaterialSource(driver, "file-id", 0, "Missing")
    with pytest.raises(SupplementaryMaterialSourceError, match="没有.*工作表"):
        missing.read()


def test_native_google_sheet_uses_gid():
    def read_sheet(file_id, gid):
        assert (file_id, gid) == ("file-id", 921765553)
        return SimpleNamespace(values=[["FIRST"], [], ["AFTER-BLANK"]])
    driver = SimpleNamespace(
        get_file_metadata=lambda file_id: SimpleNamespace(mime_type="application/vnd.google-apps.spreadsheet"),
        read_sheet_by_gid=read_sheet,
    )
    source = GoogleSupplementaryMaterialSource(driver, "file-id", 921765553, "辅料料号")
    assert [item.material_number for item in source.read()] == ["FIRST"]


class MemoryCollection:
    """The Mongo operations used by source sync; no live business database."""
    def __init__(self):
        self.documents = {}

    def create_index(self, *args, **kwargs):
        pass

    def find(self, selector):
        return list(self.documents.values())

    def find_one(self, selector):
        return self.documents.get(selector["_id"])

    def insert_one(self, document):
        self.documents[document["_id"]] = dict(document)

    def replace_one(self, selector, document, **kwargs):
        self.documents[selector["_id"]] = dict(document)

    def delete_one(self, selector):
        removed = self.documents.pop(selector["_id"], None)
        return SimpleNamespace(deleted_count=int(removed is not None))

    def update_one(self, selector, update, **kwargs):
        self.documents.setdefault(selector["_id"], dict(selector)).update(update["$set"])


@pytest.fixture(params=["sqlite", "mongo"])
def repository(request, tmp_path, monkeypatch):
    if request.param == "sqlite":
        return SupplementaryMaterialRepository(tmp_path / "supplies.sqlite3")
    from modules.supplies import mongo_repository
    collections = {}
    monkeypatch.setattr(mongo_repository, "get_document_collection", lambda name: collections.setdefault(name, MemoryCollection()))
    return mongo_repository.MongoSupplementaryMaterialRepository()


def test_sync_updates_in_place_removes_stale_source_rows_and_preserves_manual_rows(repository):
    now = datetime.now(timezone.utc)
    manual = repository.create(material("MANUAL", "Local only"))
    existing = repository.create(material("EXISTING", "Old name"))
    first = repository.sync_from_sheet([material("EXISTING", "New name"), material("STALE")], now)
    assert (first.created_count, first.updated_count) == (1, 1)
    assert repository.get(existing.id).english_name == "New name"
    assert repository.get(existing.id).created_at == existing.created_at
    stale_id = next(item.id for item in first.materials if item.material_number == "STALE")
    second = repository.sync_from_sheet([material("EXISTING", "New name"), material("NEW")], now + timedelta(hours=1))
    assert second.removed_ids == {stale_id}
    assert (second.created_count, second.updated_count) == (1, 0)
    assert repository.get(stale_id) is None
    assert repository.get(manual.id).english_name == "Local only"
    assert repository.get(existing.id).updated_at == now
    assert repository.get_sheet_sync_state()["synced_at"] == (now + timedelta(hours=1)).isoformat()


@pytest.mark.parametrize("invalid", [[], [material("NEW"), material("NEW")]])
def test_invalid_snapshot_preserves_data_and_last_success(repository, invalid):
    now = datetime.now(timezone.utc)
    first = repository.sync_from_sheet([material("ORIGINAL")], now)
    state = repository.get_sheet_sync_state()
    with pytest.raises(ValueError):
        repository.sync_from_sheet(invalid, now + timedelta(hours=1))
    assert repository.get(first.materials[0].id).material_number == "ORIGINAL"
    assert repository.get_sheet_sync_state() == state


def test_sync_state_survives_sqlite_reopen(tmp_path):
    path = tmp_path / "supplies.sqlite3"
    first = SupplementaryMaterialRepository(path)
    first.sync_from_sheet([material("OLD")], datetime.now(timezone.utc))
    reopened = SupplementaryMaterialRepository(path)
    plan = reopened.sync_from_sheet([material("NEW")], datetime.now(timezone.utc))
    assert len(plan.removed_ids) == 1
    assert [item.material_number for item in reopened.list()] == ["NEW"]


def test_source_failure_preserves_saved_data_and_reports_error(tmp_path):
    repository = SupplementaryMaterialRepository(tmp_path / "supplies.sqlite3")
    source = SimpleNamespace(source_url="https://example.com", read=lambda: [material("ORIGINAL")])
    service = SupplementaryMaterialService(repository, source)
    success = service.sync_from_source()
    def failed_read():
        raise RuntimeError("Source unavailable")
    source.read = failed_read
    with pytest.raises(RuntimeError, match="unavailable"):
        service.sync_from_source()
    assert [item.material_number for item in service.list()] == ["ORIGINAL"]
    assert service.sync_status().last_synced_at == success.synced_at
    assert service.sync_status().last_error == "Source unavailable"
    assert not service.sync_status().syncing
    source.read = lambda: [material("RECOVERED")]
    assert service.sync_from_source().removed_count == 1
    assert service.sync_status().last_error == ""


def test_parallel_sync_is_rejected_and_cancelled_read_never_writes(tmp_path):
    repository = SupplementaryMaterialRepository(tmp_path / "supplies.sqlite3")
    entered, release, cancelled = Event(), Event(), Event()
    def read():
        entered.set()
        assert release.wait(3)
        return [material("MUST-NOT-WRITE")]
    source = SimpleNamespace(source_url="https://example.com", read=read)
    service = SupplementaryMaterialService(repository, source)
    errors = []
    def run():
        try:
            service.sync_from_source(cancel_event=cancelled)
        except CancelledError as exc:
            errors.append(exc)
    worker = Thread(target=run)
    worker.start()
    try:
        assert entered.wait(3)
        assert service.sync_status().syncing
        with pytest.raises(SupplementaryMaterialSyncInProgressError):
            service.sync_from_source()
        cancelled.set()
    finally:
        release.set()
        worker.join(3)
    assert len(errors) == 1
    assert repository.list() == []
    assert service.sync_status().last_error == ""


def test_scheduler_runs_immediately_and_retries_after_failure():
    completed = Event()
    calls = []
    def sync(**kwargs):
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("Temporary failure")
        completed.set()
    service = SimpleNamespace(auto_sync_enabled=True, sync_from_source=sync)
    scheduler = SupplementaryMaterialSyncScheduler(service, interval_seconds=1)
    scheduler.start()
    try:
        assert completed.wait(4)
    finally:
        scheduler.stop()
    assert len(calls) == 2
    assert not scheduler._thread.is_alive()


def test_disabled_scheduler_does_not_read_source():
    scheduler = SupplementaryMaterialSyncScheduler(SimpleNamespace(auto_sync_enabled=False))
    scheduler.start()
    scheduler.stop()
    assert scheduler._thread is None
