"""Reference snapshots must remain independent, attributable evidence packages."""

import hashlib
import json
from pathlib import Path

import pytest

from modules.test_failures.analysis import FailureAnalysisService
from modules.test_failures.parser import digest, parse_report
from modules.test_failures.service import TestFailureService as FailureService
from test_failure_analysis import analyze
from test_qc_agent_evidence import reference_checkpoint
from test_test_failures import bundle, write_bundle


def checkpoint(handled=True, volume=50):
    base = bundle()
    snapshot = reference_checkpoint(handled, volume)
    snapshot["trace"]["identity"] = base["trace"]["identity"]
    return base | snapshot


def parsed(payload):
    return parse_report(json.dumps(payload), "json", "qc.json")


@pytest.mark.parametrize("handled,kind", [(True, "test_failure"), (False, "runtime_error")])
def test_immediate_reference_snapshot_classification(handled, kind):
    report = parsed(checkpoint(handled))
    assert report["report_role"] == "right_reference"
    assert report["reference_tip_volume_ul"] == 50
    assert report["reference_handled"] is handled
    assert report["kind"] == kind
    assert report["sn"] == bundle()["archive_directory"]["serial_number"]
    # Structured workflow failure does not invent failed DUT measurement rows.
    assert report["failure_count"] == 0


@pytest.mark.parametrize("explicit_error", ["runtime", "execution_error", "exception"])
def test_explicit_errors_still_override_handled_reference(explicit_error):
    payload = checkpoint()
    if explicit_error == "runtime":
        payload["runtime_error"] = {"type": "RuntimeError", "message": "another failure"}
    else:
        payload["trace"]["tests"]["LIQUID-PROBE"]["status"] = explicit_error
    assert parsed(payload)["kind"] == "mixed"


@pytest.mark.parametrize("case", ["final", "left", "volume", "later", "text_bool", "no_event"])
def test_earlier_or_unverified_handled_event_cannot_hide_current_failure(case):
    payload = checkpoint()
    if case == "final":
        payload["stage"] = "result-summary"
    elif case == "left":
        payload["trace"]["last_failure"]["arguments"]["args"][0] = "LEFT"
    elif case == "volume":
        payload["trace"]["last_failure"]["context"][-1]["arguments"]["tip_volume"] = 200
    elif case == "later":
        payload["trace"]["last_failure"]["id"] = 8
    elif case == "text_bool":
        payload["trace"]["events"][0]["handled"] = "true"
    else:
        payload["trace"]["events"] = []
    report = parsed(payload)
    assert report["kind"] == "runtime_error"
    assert report["reference_handled"] is None


def test_log_action_history_preserves_handled_reference_classification():
    payload = checkpoint()
    text = "\n".join([
        "Time UTC: " + payload["created_at_utc"],
        "Run ID: " + payload["run_id"],
        "QC mode: assembly_qc", "Stage: right-reference-50ul",
        "Failure details:", *["- " + value for value in payload["failure_details"]], "",
        "Run identity / versions:", json.dumps(payload["trace"]["identity"]),
        "Test execution states:", json.dumps(payload["trace"]["tests"]),
        "Failure action and latest observed readings (not trigger-time values):",
        json.dumps({"last_failure": payload["trace"]["last_failure"]}),
        "All report rows (unknown or not_recorded does not mean PASS):",
        "Action history:", json.dumps(payload["trace"]["events"], indent=2),
    ])
    report = parse_report(text, "log", "qc.right-reference-50ul.log")
    assert report["parse_status"] == "log_only"
    assert report["reference_handled"] is True
    assert report["kind"] == "test_failure"
    old_log = parse_report(text.split("Action history:")[0], "log", "qc.log")
    assert old_log["reference_handled"] is None
    assert old_log["kind"] == "runtime_error"


def test_same_run_packages_analyze_independently_and_late_encoder_affects_only_snapshot(tmp_path):
    root = tmp_path / "reports"
    for name, payload in [("qc", bundle()), ("qc.right-reference-50ul", checkpoint()),
                          ("qc.right-reference-200ul", checkpoint(False, 200))]:
        source = write_bundle(root, payload, name=name)
        source.with_suffix(".log").write_text("Evidence for " + name)
    reports = FailureService(root, tmp_path / "index.sqlite3", stable_seconds=0)
    reports.scan()
    devices = reports.list_devices()["devices"]
    assert len(devices) == 1
    summaries = devices[0]["reports"]
    assert len(summaries) == 3
    assert summaries[0]["report_role"] == "main"
    assert len({item["run_group_id"] for item in summaries}) == 1
    expected_folder = source.parent.relative_to(root).as_posix()
    assert devices[0]["report_folder"] == expected_folder
    assert {item["report_folder"] for item in summaries} == {expected_folder}
    agent = FailureAnalysisService(reports, tmp_path / "analysis")
    results = {}
    for item in summaries:
        result = analyze(agent, item["id"])
        assert result["status"] == "complete", result
        assert result["report_revision"] == item["revision"]
        assert result["mode"] == "rules_only"
        results[item["id"]] = result
    assert len(list(agent.cache_dir.glob("*/result-*"))) == 3
    main, first, second = summaries
    before_main = reports.repository.get_report(main["id"])
    reference = reports.repository.get_report(first["id"])
    encoder = root / (reference["source_group"] + ".encoder.csv")
    encoder.write_text("time,position\n0,1\n")
    reports.scan()
    assert reports.repository.get_report(main["id"]) == before_main
    assert agent.status(main["id"])["status"] == "complete"
    assert agent.status(second["id"])["status"] == "complete"
    assert agent.status(first["id"])["status"] == "stale"
    refreshed = analyze(agent, first["id"])
    assert refreshed["status"] == "complete"
    assert refreshed["report_revision"] == first["revision"]
    assert reports.list_devices()["devices"][0]["reports"][0]["id"] == main["id"]


def test_same_run_reference_packages_and_analysis_are_isolated_by_folder(tmp_path):
    root = tmp_path / "reports"
    sources = {}
    for folder, position in (("first-upload", 11), ("second-upload", 22)):
        directory = root / folder
        directory.mkdir(parents=True)
        for stem, payload in (("qc", bundle()), ("qc.right-reference-50ul", checkpoint())):
            source = directory / (stem + ".json")
            source.write_text(json.dumps(payload), encoding="utf-8")
            source.with_suffix(".log").write_text(f"Synthetic evidence for {folder}/{stem}", encoding="utf-8")
            source.with_suffix(".encoder.csv").write_text(f"time,position\n0,{position}\n", encoding="utf-8")
            sources[folder, stem] = source

    reports = FailureService(root, tmp_path / "index.sqlite3", stable_seconds=0)
    assert reports.scan()["parse_errors"] == 0
    rows = {item["report_folder"]: item for item in reports.list_devices()["devices"]}
    assert set(rows) == {"first-upload", "second-upload"}
    assert len({item["sn"] for item in rows.values()}) == 1
    assert len({item["id"] for item in rows.values()}) == 2
    summaries = [report for item in rows.values() for report in item["reports"]]
    assert len({item["id"] for item in summaries}) == 4
    assert len({item["run_group_id"] for item in summaries}) == 2
    for folder, device in rows.items():
        assert len(device["reports"]) == 2
        assert [item["report_role"] for item in device["reports"]] == ["main", "right_reference"]
        assert {item["report_folder"] for item in device["reports"]} == {folder}
        assert len({item["run_group_id"] for item in device["reports"]}) == 1

    first = rows["first-upload"]
    reports.confirm_device(first["id"], "Reviewed first upload only", first["version"], "synthetic-user")
    rows = {item["report_folder"]: item for item in reports.list_devices()["devices"]}
    assert rows["first-upload"]["unconfirmed_count"] == 0
    assert rows["second-upload"]["unconfirmed_count"] == 2
    assert reports.list_confirmations(rows["second-upload"]["id"])["items"] == []

    agent = FailureAnalysisService(reports, tmp_path / "analysis")
    ids = {}
    for folder, device in rows.items():
        expected_position = 11 if folder == "first-upload" else 22
        for summary in device["reports"]:
            stem = "qc" if summary["report_role"] == "main" else "qc.right-reference-50ul"
            source = sources[folder, stem]
            ids[folder, stem] = summary["id"]
            record = reports.repository.get_report(summary["id"])
            assert {Path(value).parent.as_posix() for value in record["attachment_paths"].values()} == {folder}
            assert reports.preview_attachment(summary["id"], "log")["text"] == f"Synthetic evidence for {folder}/{stem}"
            result = analyze(agent, summary["id"])
            assert result["status"] == "complete", result
            assert result["report_id"] == summary["id"]
            assert result["report_revision"] == summary["revision"]
            for kind in (".json", ".log", ".encoder.csv"):
                attachment = source.with_suffix(kind)
                assert result["result"]["input_hashes"][attachment.name] == hashlib.sha256(attachment.read_bytes()).hexdigest()
            assert result["result"]["evidence"]["encoder_summary"]["columns"][1]["maximum"] == expected_position
    assert len(list(agent.cache_dir.glob("*/result-*"))) == 4

    # A late attachment change only invalidates its precise folder/package cache.
    changed_id = ids["first-upload", "qc.right-reference-50ul"]
    sources["first-upload", "qc.right-reference-50ul"].with_suffix(".encoder.csv").write_text("time,position\n0,33\n")
    assert reports.scan()["parse_errors"] == 0
    assert agent.status(changed_id)["status"] == "stale"
    assert all(agent.status(report_id)["status"] == "complete" for report_id in ids.values() if report_id != changed_id)
    changed = analyze(agent, changed_id)
    assert changed["result"]["evidence"]["encoder_summary"]["columns"][1]["maximum"] == 33
    after = {item["report_folder"]: item for item in reports.list_devices()["devices"]}
    assert after["first-upload"]["version"] == rows["first-upload"]["version"]
    assert after["first-upload"]["unconfirmed_count"] == 0
    assert after["second-upload"]["version"] == rows["second-upload"]["version"]


def test_folder_migration_reuses_only_the_original_owners_analysis_cache(tmp_path):
    root = tmp_path / "reports"
    first_source = root / "first-upload" / "qc.json"
    first_source.parent.mkdir(parents=True)
    first_source.write_text(json.dumps(bundle()), encoding="utf-8")
    first_source.with_suffix(".log").write_text("Original owner log", encoding="utf-8")
    reports = FailureService(root, tmp_path / "index.sqlite3", stable_seconds=0)
    reports.scan()
    owner = reports.list_devices()["devices"][0]["reports"][0]
    agent = FailureAnalysisService(reports, tmp_path / "analysis")
    original = analyze(agent, owner["id"])
    assert original["status"] == "complete", original

    second_source = root / "second-upload" / "qc.json"
    second_source.parent.mkdir()
    second_source.write_bytes(first_source.read_bytes())
    second_source.with_suffix(".log").write_text("Independent second log", encoding="utf-8")
    # A schema-2 index collapsed matching run IDs in different folders. Its
    # current payload and previous analysis still belong to the first source.
    with reports.repository.connection() as connection:
        payload = json.loads(connection.execute("SELECT payload FROM failure_reports WHERE id=?", (owner["id"],)).fetchone()[0])
        payload.pop("report_folder", None)
        old_identity = digest([payload["run_id"], payload["mode"], payload["report_run_id"]])
        connection.execute("UPDATE failure_reports SET identity_key=?,payload=? WHERE id=?",
                           (old_identity, json.dumps(payload), owner["id"]))
        connection.execute("INSERT INTO failure_sources VALUES (?,?,?,?)",
                           (reports.repository.root_key, "second-upload/qc", owner["id"], "old-cross-folder-signature"))
        connection.execute("UPDATE failure_index_versions SET version=2 WHERE root_key=?", (reports.repository.root_key,))

    assert reports.scan()["parse_errors"] == 0
    rows = {item["report_folder"]: item for item in reports.list_devices()["devices"]}
    assert set(rows) == {"first-upload", "second-upload"}
    retained = rows["first-upload"]["reports"][0]
    separated = rows["second-upload"]["reports"][0]
    assert retained["id"] == owner["id"]
    assert retained["revision"] == separated["revision"] == owner["revision"]
    assert separated["id"] != owner["id"]
    assert agent.status(owner["id"]) == original
    assert agent.status(separated["id"])["status"] == "idle"
    assert reports.preview_attachment(owner["id"], "log")["text"] == "Original owner log"
    assert reports.preview_attachment(separated["id"], "log")["text"] == "Independent second log"
    independent = analyze(agent, separated["id"])
    assert independent["status"] == "complete", independent
    assert independent["report_id"] == separated["id"]
    assert independent["result"]["input_hashes"]["qc.log"] != original["result"]["input_hashes"]["qc.log"]
    assert agent.status(owner["id"]) == original
    assert len(list(agent.cache_dir.glob("*/result-*"))) == 2
