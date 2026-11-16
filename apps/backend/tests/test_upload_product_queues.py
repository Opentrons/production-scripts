from __future__ import annotations

from concurrent.futures import Future
from copy import deepcopy
from datetime import datetime, timedelta
from threading import Event
from types import SimpleNamespace

from bson import ObjectId
import pytest

from core.sqlite_store import SqliteDocumentStore
from modules.uploads import scheduler as scheduler_module, upload_records
from modules.uploads.queue_routing import resolve_upload_product_group


def report(tmp_path, sn, name="report.csv"):
    path = tmp_path / name
    path.write_text(
        f",META_DATA_START,\n,test_tag,{sn}\n,test_robot_id,FLXA3020261110001\n,META_DATA_END,\n"
    )
    return str(path)


@pytest.mark.parametrize("sn,group", [
    ("P1KSV3620261110A28", "pipette"), ("P1KMV3520261106A04", "pipette"),
    ("P2HH20260101", "pipette"), ("FLXA3020261110001", "robot"),
    ("ZS10202601110001", "robot"), ("GRPV20260101", "other"),
])
def test_routing_uses_tested_product_instead_of_host_robot(tmp_path, sn, group):
    assert resolve_upload_product_group(report(tmp_path, sn)) == group


def test_routing_honors_manual_serial_override_and_saved_description(tmp_path):
    path = report(tmp_path, "P1KSV3620261110A28")
    assert resolve_upload_product_group(path, {"test_device": "FLXA3020261110001"}) == "robot"
    assert resolve_upload_product_group("missing.csv", file_desc={"model": "Robot"}) == "robot"
    assert resolve_upload_product_group("missing.csv") == "other"


class Cursor(list):
    def sort(self, key, direction=1):
        return Cursor(sorted(self, key=lambda row: row.get(key), reverse=direction < 0))

    def limit(self, count):
        return Cursor(self[:count])


class MongoQueue:
    """Mongo query semantics needed by the scheduler, without a live database."""

    def __init__(self):
        self.documents = []

    def create_index(self, *args, **kwargs):
        pass

    def insert_one(self, doc):
        doc = deepcopy(doc)
        doc["_id"] = ObjectId()
        self.documents.append(doc)
        return SimpleNamespace(inserted_id=doc["_id"])

    @staticmethod
    def matches(doc, query):
        for key, expected in query.items():
            actual = doc.get(key)
            if not isinstance(expected, dict):
                if actual != expected:
                    return False
                continue
            for op, value in expected.items():
                if op == "$in" and actual not in value:
                    return False
                if op == "$nin" and actual in value:
                    return False
                if op == "$ne" and actual == value:
                    return False
                if op == "$lte" and (actual is None or actual > value):
                    return False
        return True

    def find(self, query):
        return Cursor(deepcopy([doc for doc in self.documents if self.matches(doc, query)]))

    def find_one(self, query):
        return next(iter(self.find(query)), None)

    def update_one(self, query, update):
        for doc in self.documents:
            if self.matches(doc, query):
                doc.update(deepcopy(update.get("$set", {})))
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)


@pytest.fixture(params=["mongodb", "sqlite"])
def queue(request, monkeypatch, tmp_path):
    sqlite = request.param == "sqlite"
    collection = SqliteDocumentStore(tmp_path / "queue.sqlite3")["uploads"] if sqlite else MongoQueue()
    monkeypatch.setattr(upload_records.setting, "use_sqlite_persistence", lambda: sqlite)
    monkeypatch.setattr(upload_records, "get_upload_record_collection", lambda: collection)
    return collection


def enqueue(path):
    record_id = upload_records.create_upload_record(path)
    assert upload_records.enqueue_upload_record(record_id, csv_path=path, zip_path=None, meta={})
    return record_id


def test_each_product_claims_only_its_own_due_jobs(queue, tmp_path):
    pipette_path = report(tmp_path, "P1KSV3620261110A28", "pipette.csv")
    robot_path = report(tmp_path, "ZS10202601110001", "robot.csv")
    pipette_id = enqueue(pipette_path)
    robot_id = enqueue(robot_path)
    assert upload_records.get_upload_record(pipette_id)["product_group"] == "pipette"
    assert upload_records.get_upload_record(robot_id)["product_group"] == "robot"
    assert upload_records.get_upload_record(robot_id)["progress_stage"] == "queued"
    assert str(upload_records.claim_due_upload_record("robot-worker", "robot")["_id"]) == robot_id
    assert upload_records.get_upload_record(robot_id)["progress_stage"] == "running"
    assert upload_records.get_upload_record(pipette_id)["status"] == "queued"
    assert upload_records.claim_due_upload_record("robot-worker", "robot") is None
    assert str(upload_records.claim_due_upload_record("pipette-worker", "pipette")["_id"]) == pipette_id
    assert upload_records.schedule_upload_retry(
        robot_id, failure_stage="google_drive", failure_code="google_upload_failed", error="503",
    )
    assert upload_records.claim_due_upload_record("robot-worker", "robot") is None
    upload_records.update_upload_record(robot_id, {"next_retry_at": datetime.now() - timedelta(seconds=1)})
    assert upload_records.claim_due_upload_record("pipette-worker", "pipette") is None
    retried = upload_records.claim_due_upload_record("robot-worker", "robot")
    assert str(retried["_id"]) == robot_id
    assert retried["attempt_count"] == 2


def test_legacy_robot_job_behind_more_than_twenty_pipettes_is_not_starved(queue, tmp_path):
    paths = [report(tmp_path, "P1KSV3620261110A28", "pipette.csv")] * 25
    paths.append(report(tmp_path, "ZS10202601110001", "robot.csv"))
    ids = []
    for index, path in enumerate(paths):
        record_id = upload_records.create_upload_record(path)
        upload_records.update_upload_record(record_id, {
            "status": "queued", "job": {"csv_path": path, "meta": {}},
            "next_retry_at": datetime.now() - timedelta(minutes=30 - index),
        })
        ids.append(record_id)

    assert str(upload_records.claim_due_upload_record("robot-worker", "robot")["_id"]) == ids[-1]
    assert all(upload_records.get_upload_record(record_id)["status"] == "queued" for record_id in ids[:-1])
    assert str(upload_records.claim_due_upload_record("pipette-worker", "pipette")["_id"]) == ids[0]


def test_blocked_pipettes_leave_capacity_for_robot_other_and_notifications(monkeypatch):
    monkeypatch.setattr(scheduler_module.setting, "UPLOAD_PIPETTE_MAX_WORKERS", 2)
    monkeypatch.setattr(scheduler_module.setting, "UPLOAD_ROBOT_MAX_WORKERS", 1)
    monkeypatch.setattr(scheduler_module.setting, "UPLOAD_OTHER_MAX_WORKERS", 1)
    monkeypatch.setattr(scheduler_module.setting, "UPLOAD_SCHEDULER_POLL_SECONDS", 0.01)
    for name in ("ensure_upload_record_indexes", "recover_expired_upload_leases", "recover_expired_upload_notifications"):
        monkeypatch.setattr(scheduler_module.upload_records, name, lambda: None)
    jobs = {group: [{"group": group, "index": i} for i in range(3)] for group in ("pipette", "robot", "other")}

    def claim(owner, product_group):
        return jobs[product_group].pop(0) if jobs[product_group] else None

    monkeypatch.setattr(scheduler_module.upload_records, "claim_due_upload_record", claim)
    notices = [{"notification": True}]
    monkeypatch.setattr(scheduler_module.upload_records, "claim_due_upload_notification", lambda owner: notices.pop() if notices else None)
    scheduler = scheduler_module.UploadScheduler()
    release = Event()
    started = {group: [Event() for _ in range(3)] for group in jobs}
    notified = Event()

    def execute(record):
        started[record["group"]][record["index"]].set()
        release.wait(5)

    monkeypatch.setattr(scheduler, "_execute_upload", execute)
    monkeypatch.setattr(scheduler, "_execute_notification", lambda record: notified.set())
    try:
        scheduler.start()
        assert started["pipette"][0].wait(2)
        assert started["pipette"][1].wait(2)
        assert started["robot"][0].wait(2)
        assert started["other"][0].wait(2)
        assert notified.wait(2)
        assert not started["pipette"][2].is_set()
        assert not started["robot"][1].is_set()
        assert not started["other"][1].is_set()
        release.set()
        assert started["robot"][1].wait(2)
        assert started["pipette"][2].wait(2)
    finally:
        release.set()
        scheduler.stop()


def test_immediately_completed_pipettes_do_not_starve_later_groups(monkeypatch):
    monkeypatch.setattr(scheduler_module.setting, "UPLOAD_PIPETTE_MAX_WORKERS", 2)
    monkeypatch.setattr(scheduler_module.setting, "UPLOAD_ROBOT_MAX_WORKERS", 1)
    monkeypatch.setattr(scheduler_module.setting, "UPLOAD_OTHER_MAX_WORKERS", 1)
    claims = []

    def claim(owner, product_group):
        claims.append(product_group)
        assert len(claims) <= 4, "One product must not monopolize the poll"
        return {"group": product_group}

    def submit(fn, record):
        future = Future()
        future.set_result(None)
        return future

    monkeypatch.setattr(scheduler_module.upload_records, "claim_due_upload_record", claim)
    scheduler = scheduler_module.UploadScheduler()
    scheduler._executor = SimpleNamespace(submit=submit)
    scheduler._dispatch_uploads()
    assert claims == ["pipette", "pipette", "robot", "other"]
