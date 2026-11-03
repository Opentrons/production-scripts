from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth.dependencies import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME, get_auth_service
from modules.auth.service import AuthService
from modules.test_failures import analysis, routes
from modules.test_failures.analysis import FailureAnalysisService
from modules.test_failures.service import ConflictError, NotFoundError, TestFailureService as FailureService
from test_test_failures import PREFIX, bearer, bundle, rewrite_json_preserving_stat, session_for, write_bundle


@pytest.fixture
def context(tmp_path):
    root = tmp_path / "reports"
    root.mkdir()
    source = write_bundle(root)
    source.with_suffix(".log").write_text("Original log", encoding="utf-8")
    reports = FailureService(root, tmp_path / "reports.sqlite3", stable_seconds=0)
    reports.scan()
    report_id = reports.list_devices()["devices"][0]["reports"][0]["id"]
    agent = FailureAnalysisService(reports, tmp_path / "analysis")
    yield reports, agent, report_id, source
    for thread in list(agent._threads.values()):
        thread.join(timeout=10)
        assert not thread.is_alive()


def wait_for(agent):
    assert agent._thread
    for thread in set([agent._thread, *agent._threads.values()]):
        thread.join(timeout=10)
        assert not thread.is_alive()


def request(agent, report_id, *, force=False):
    revision = agent.reports.repository.get_report(report_id)["revision"]
    return agent.request(report_id, revision, force=force)


def analyze(agent, report_id):
    assert request(agent, report_id)["status"] == "running"
    wait_for(agent)
    return agent.status(report_id)


def test_rules_mode_complete_reuses_cache_and_preserves_originals(context, monkeypatch):
    reports, agent, report_id, source = context
    def forbidden(*args, **kwargs):
        pytest.fail("Rules-only mode must not invoke a model")
    monkeypatch.setattr(analysis, "analyze_report", forbidden)
    before = {path.name: path.read_bytes() for path in source.parent.iterdir()}
    before_devices = reports.list_devices()["devices"]
    assert agent.status(report_id)["status"] == "idle"
    assert not agent.cache_dir.exists()
    status = analyze(agent, report_id)
    assert status["status"] == "complete", status
    assert status["mode"] == "rules_only"
    assert status["generated_at"]
    assert status["result"]["model_analysis"]["status"] == "disabled"
    assert status["result"]["evidence"]["deterministic_findings"]
    assert request(agent, report_id) == status
    assert {path.name: path.read_bytes() for path in source.parent.iterdir()} == before
    assert reports.list_devices()["devices"] == before_devices
    assert len(list(agent.cache_dir.glob("*/result-*"))) == 1


@pytest.mark.parametrize("force", [False, True])
def test_source_change_invalidates_before_rescan(context, force):
    _, agent, report_id, source = context
    analyze(agent, report_id)
    source.with_suffix(".log").write_text("Updated log", encoding="utf-8")
    status = agent.status(report_id)
    assert status["status"] == "stale" and status["result"] is None
    with pytest.raises(ConflictError):
        request(agent, report_id, force=force)


def test_content_changed_with_same_signature_is_detected(context):
    _, agent, report_id, source = context
    analyze(agent, report_id)
    log = source.with_suffix(".log")
    info = log.stat()
    log.write_bytes(b"Modified log")
    assert log.stat().st_size == info.st_size
    os.utime(log, ns=(info.st_atime_ns, info.st_mtime_ns))
    assert agent.status(report_id)["status"] == "stale"


@pytest.mark.parametrize("already_analyzed", [False, True])
def test_same_stat_json_change_rejects_old_revision_and_recovers_after_scan(context, already_analyzed):
    reports, agent, report_id, source = context
    if already_analyzed:
        assert analyze(agent, report_id)["status"] == "complete"
    previous = reports.repository.get_report(report_id)
    payload = json.loads(source.read_text())
    payload["report_rows"][0]["data"][0] = 4.5
    rewrite_json_preserving_stat(source, payload)
    before_scan = agent.status(report_id)
    assert before_scan["status"] == "stale"
    assert before_scan["result"] is None
    with pytest.raises(ConflictError):
        agent.request(report_id, previous["revision"])
    assert reports.repository.get_report(report_id)["revision"] == previous["revision"]
    reports.scan()
    updated = reports.repository.get_report(report_id)
    assert updated["revision"] != previous["revision"]
    assert updated["failures"][0]["data"] == [4.5, "FAIL"]
    with pytest.raises(ConflictError):
        agent.request(report_id, previous["revision"])
    result = analyze(agent, report_id)
    assert result["status"] == "complete"
    assert result["report_revision"] == updated["revision"]
    assert result["result"]["evidence"]["failed_rows"][0]["value"]["data"] == [4.5, "FAIL"]


def test_legacy_index_without_content_hash_rejects_changed_json_semantics(context, monkeypatch):
    reports, agent, report_id, source = context
    legacy_record = reports.repository.get_report(report_id)
    legacy_record.pop("attachment_hashes", None)
    monkeypatch.setattr(reports.repository, "get_report", lambda _id: legacy_record)
    initial = analyze(agent, report_id)
    assert initial["status"] == "complete"
    assert initial["report_revision"] == legacy_record["revision"]
    payload = json.loads(source.read_text())
    payload["report_rows"][0]["data"][0] = 4.5
    rewrite_json_preserving_stat(source, payload)
    assert agent.status(report_id)["status"] == "stale"
    with pytest.raises(ConflictError):
        agent.request(report_id, legacy_record["revision"])
    assert len(list(agent.cache_dir.glob("*/result-*"))) == 1


@pytest.mark.parametrize("include_hashes", [False, True])
@pytest.mark.parametrize("identity_field", ["run_id", "report_run_id"])
def test_changed_run_identity_is_rejected_even_when_semantic_revision_matches(
    context, monkeypatch, include_hashes, identity_field
):
    reports, agent, report_id, source = context
    record = reports.repository.get_report(report_id)
    if not include_hashes:
        record.pop("attachment_hashes", None)
        monkeypatch.setattr(reports.repository, "get_report", lambda _id: record)
    payload = json.loads(source.read_text())
    payload[identity_field] = payload[identity_field][:-1] + "x"
    rewrite_json_preserving_stat(source, payload)
    assert analysis.parse_report(source.read_bytes(), "json", source.name)["revision"] == record["revision"]
    assert agent.status(report_id)["status"] == "stale"
    with pytest.raises(ConflictError):
        agent.request(report_id, record["revision"])
    assert not agent.cache_dir.exists()


def test_updated_index_can_generate_new_result(context):
    reports, agent, report_id, source = context
    first = analyze(agent, report_id)
    payload = json.loads(source.read_text())
    payload["report_rows"][0]["data"] = [99, "FAIL"]
    source.write_text(json.dumps(payload))
    reports.scan()
    assert agent.status(report_id)["status"] == "stale"
    second = analyze(agent, report_id)
    assert second["status"] == "complete"
    assert second["report_revision"] != first["report_revision"]
    assert len(list(agent.cache_dir.glob("*/result-*"))) == 2


@pytest.mark.parametrize("force", [False, True])
def test_same_running_task_is_reused_while_different_reports_run_concurrently(context, monkeypatch, force):
    reports, agent, report_id, source = context
    released, entered = threading.Event(), threading.Event()
    original = analysis._rules_analysis
    calls = []
    def blocking(*args):
        calls.append(args[1])
        entered.set()
        assert released.wait(timeout=5)
        return original(*args)
    monkeypatch.setattr(analysis, "_rules_analysis", blocking)
    second = bundle(run_id="different-run", report_run_id="different-report-run")
    write_bundle(reports.root, second, name="second")
    reports.scan()
    other_id = next(item["id"] for item in reports.list_devices()["devices"][0]["reports"] if item["id"] != report_id)
    try:
        assert request(agent, report_id)["status"] == "running"
        assert entered.wait(timeout=5)
        assert request(agent, report_id, force=force)["status"] == "running"
        assert request(agent, other_id, force=force)["status"] == "running"
        other_instance = FailureAnalysisService(reports, agent.cache_dir)
        assert other_instance.status(report_id)["status"] == "running"
        assert request(other_instance, report_id, force=force)["status"] == "running"
        assert request(other_instance, other_id, force=force)["status"] == "running"
    finally:
        released.set()
    wait_for(agent)
    assert len(calls) == 2
    assert len(list(agent.cache_dir.glob("*/result-*"))) == 2
    assert agent.status(report_id)["status"] == "complete"
    assert agent.status(other_id)["status"] == "complete"


def test_status_returns_complete_when_worker_finishes_after_running_state_was_read(context, monkeypatch):
    _, agent, report_id, _ = context
    entered, released = threading.Event(), threading.Event()
    original_analysis = analysis._rules_analysis
    original_running = agent._is_running

    def blocked_analysis(*args):
        entered.set()
        assert released.wait(timeout=5)
        return original_analysis(*args)

    def finish_worker_before_check(key):
        released.set()
        wait_for(agent)
        return original_running(key)

    monkeypatch.setattr(analysis, "_rules_analysis", blocked_analysis)
    try:
        assert request(agent, report_id)["status"] == "running"
        assert entered.wait(timeout=5)
        monkeypatch.setattr(agent, "_is_running", finish_worker_before_check)
        status = agent.status(report_id)
        assert status["status"] == "complete"
        assert status["result"]["status"] == "complete"
        assert status["error"] is None
    finally:
        released.set()
        if agent._thread:
            wait_for(agent)


def test_source_update_during_analysis_cannot_publish(context, monkeypatch):
    _, agent, report_id, source = context
    original = analysis._rules_analysis
    def changing(*args):
        result = original(*args)
        source.with_suffix(".log").write_text("Changed during inference", encoding="utf-8")
        return result
    monkeypatch.setattr(analysis, "_rules_analysis", changing)
    status = analyze(agent, report_id)
    assert status["status"] == "stale" and status["result"] is None
    assert not list(agent.cache_dir.glob("*/result-*"))
    assert not list(agent.cache_dir.glob("*/.pending-*"))


def test_model_error_does_not_publish_and_can_retry(context, monkeypatch):
    _, agent, report_id, _ = context
    agent.model_enabled = True
    agent.mode = "model"
    def failing(*args):
        raise analysis.ModelAnalysisError("secret model text")
    monkeypatch.setattr(analysis, "analyze_report", failing)
    status = analyze(agent, report_id)
    assert status["status"] == "failed" and status["result"] is None
    assert "secret" not in status["error"]
    agent.model_enabled = False
    agent.mode = "rules_only"
    assert analyze(agent, report_id)["status"] == "complete"


def test_unknown_schema_is_unsupported_without_model(context, monkeypatch):
    reports, agent, report_id, source = context
    payload = json.loads(source.read_text())
    payload["schema_version"] = 99
    source.write_text(json.dumps(payload))
    # The scanner currently rejects this new schema. Simulate a future/historic
    # index that carries it, so the analysis adapter's own guard is exercised.
    record = reports.repository.get_report(report_id)
    record["attachment_signatures"]["json"] = list(analysis.stat_signature(source.stat()))
    record.setdefault("attachment_hashes", {})["json"] = hashlib.sha256(source.read_bytes()).hexdigest()
    monkeypatch.setattr(reports.repository, "get_report", lambda _id: record)
    agent.model_enabled = True
    monkeypatch.setattr(analysis, "analyze_report", lambda *args: pytest.fail("Unsupported input sent to model"))
    status = request(agent, report_id)
    if status["status"] == "running":
        wait_for(agent)
        status = agent.status(report_id)
    assert status["status"] == "unsupported" and status["result"] is None


def test_crash_running_marker_is_recoverable(context):
    reports, agent, report_id, _ = context
    report = reports.repository.get_report(report_id)
    fingerprint, _ = agent._fingerprint(report)
    analysis._write_json(agent._state_path(agent._key(report)), {"status": "running", "fingerprint": fingerprint, "job": "interrupted-worker"})
    assert agent.status(report_id)["status"] == "failed"
    assert analyze(agent, report_id)["status"] == "complete"


def test_configuration_changes_invalidate_cache(context):
    reports, agent, report_id, _ = context
    analyze(agent, report_id)
    new_agent = FailureAnalysisService(reports, agent.cache_dir, model_enabled=True)
    status = new_agent.status(report_id)
    assert status["status"] == "stale" and status["result"] is None


@pytest.fixture
def protocol_context(context, tmp_path):
    reports, existing, report_id, source = context
    protocol = tmp_path / "trusted_protocol.py"
    protocol.write_text("# synthetic protocol version 1\n", encoding="utf-8")
    agent = FailureAnalysisService(reports, existing.cache_dir, settings={"protocol_source_path": str(protocol)})
    yield reports, agent, report_id, source, protocol
    if agent._thread:
        wait_for(agent)


def test_trusted_protocol_change_invalidates_cache_on_existing_service_instance(protocol_context):
    _, agent, report_id, _, protocol = protocol_context
    first = analyze(agent, report_id)
    assert first["status"] == "complete"
    protocol.write_text("# synthetic protocol version 2\n", encoding="utf-8")
    stale = agent.status(report_id)
    assert stale["status"] == "stale"
    assert stale["result"] is None
    second = analyze(agent, report_id)
    assert second["status"] == "complete"
    assert second["report_revision"] == first["report_revision"]
    assert len(list(agent.cache_dir.glob("*/result-*"))) == 2


def test_trusted_protocol_change_during_analysis_does_not_publish_old_result(protocol_context, monkeypatch):
    _, agent, report_id, _, protocol = protocol_context
    original_analysis = analysis._rules_analysis

    def change_protocol_after_analysis(*args):
        result = original_analysis(*args)
        protocol.write_text("# synthetic protocol version 2\n", encoding="utf-8")
        return result

    monkeypatch.setattr(analysis, "_rules_analysis", change_protocol_after_analysis)
    status = analyze(agent, report_id)
    assert status["status"] == "stale"
    assert status["result"] is None
    assert not list(agent.cache_dir.glob("*/result-*"))
    assert not list(agent.cache_dir.glob("*/.pending-*"))


@pytest.mark.parametrize("removed_kind", ["log", "encoder"])
def test_removed_optional_attachment_can_be_analyzed_after_rescan(context, removed_kind):
    reports, agent, report_id, source = context
    encoder = source.with_suffix(".encoder.csv")
    encoder.write_text("cycle,position\n1,42\n", encoding="utf-8")
    reports.scan()
    initial = analyze(agent, report_id)
    removed = source.with_suffix(".log") if removed_kind == "log" else encoder
    removed.unlink()
    assert agent.status(report_id)["status"] == "stale"
    with pytest.raises(ConflictError):
        request(agent, report_id)
    reports.scan()
    stored = reports.repository.get_report(report_id)
    assert removed_kind not in stored["attachment_paths"]
    assert removed_kind not in stored["attachment_signatures"]
    assert removed_kind not in stored.get("attachment_hashes", {})
    status = analyze(agent, report_id)
    assert status["status"] == "complete"
    assert status["report_revision"] == initial["report_revision"]
    assert removed.name not in status["result"]["input_hashes"]


@pytest.mark.parametrize("replacement", ["missing", "incomplete", "corrupt"])
def test_invalid_json_update_cannot_mix_previous_evidence_with_new_attachments(context, replacement):
    reports, agent, report_id, source = context
    initial = analyze(agent, report_id)
    original = reports.repository.get_report(report_id)
    if replacement == "missing":
        source.unlink()
    elif replacement == "corrupt":
        source.write_text('{"schema_version": 1,', encoding="utf-8")
    else:
        payload = json.loads(source.read_text())
        payload["report_rows"] = []
        payload["trace"]["tests"] = {}
        payload["failure_details"] = []
        source.write_text(json.dumps(payload), encoding="utf-8")
    source.with_suffix(".log").write_text("New log does not describe the indexed failure", encoding="utf-8")
    reports.scan()
    current = reports.repository.get_report(report_id)
    assert current["revision"] == original["revision"]
    assert current["failures"] == original["failures"]
    status = agent.status(report_id)
    assert status["status"] in {"stale", "unsupported"}
    assert status["result"] is None
    if status["status"] == "stale":
        with pytest.raises(ConflictError):
            request(agent, report_id)
    else:
        assert request(agent, report_id)["status"] == "unsupported"
    assert len(list(agent.cache_dir.glob("*/result-*"))) == 1
    assert initial["status"] == "complete"


def test_missing_or_corrupt_result_does_not_report_complete(context):
    _, agent, report_id, _ = context
    analyze(agent, report_id)
    next(agent.cache_dir.glob("*/result-*/analysis.json")).write_text("incomplete", encoding="utf-8")
    assert agent.status(report_id)["status"] == "failed"
    assert analyze(agent, report_id)["status"] == "complete"


@pytest.mark.parametrize("field,value", [
    ("analysis_schema_version", True), ("source_report", "another.json"),
    ("report_id", "another-report"), ("report_revision", "another-revision"),
    ("source_fingerprint", "another-fingerprint"), ("input_hashes", {}),
    ("evidence", {}), ("model_analysis", {"status": "disabled"}),
    ("generated_at_utc", "not-a-date"),
])
def test_complete_json_with_invalid_schema_or_binding_is_rejected(context, field, value):
    reports, agent, report_id, _ = context
    analyze(agent, report_id)
    state_path = agent._state_path(agent._key(reports.repository.get_report(report_id)))
    state = analysis._read_json(state_path)
    result_path = state_path.parent / state["result_directory"] / "analysis.json"
    result = analysis._read_json(result_path)
    result[field] = value
    # Even a recomputed checksum cannot make malformed or cross-report data valid.
    state["result_sha256"] = analysis._digest(result)
    analysis._write_json(result_path, result)
    analysis._write_json(state_path, state)
    rejected = agent.status(report_id)
    assert rejected["status"] == "failed" and rejected["result"] is None


def test_complete_cache_rejects_modified_valid_shape_evidence(context):
    _, agent, report_id, _ = context
    analyze(agent, report_id)
    result_path = next(agent.cache_dir.glob("*/result-*/analysis.json"))
    result = analysis._read_json(result_path)
    result["evidence"]["deterministic_findings"][0]["observed"] = "Incorrect cached conclusion"
    analysis._write_json(result_path, result)
    assert agent.status(report_id)["status"] == "failed"


@pytest.mark.parametrize("replacement", ["directory", "symlink"])
def test_unreadable_or_linked_result_is_not_served(context, tmp_path, replacement):
    _, agent, report_id, _ = context
    analyze(agent, report_id)
    result_path = next(agent.cache_dir.glob("*/result-*/analysis.json"))
    saved = result_path.read_bytes()
    result_path.unlink()
    if replacement == "directory":
        result_path.mkdir()
    else:
        outside = tmp_path / "another-cache.json"
        outside.write_bytes(saved)
        result_path.symlink_to(outside)
    status = agent.status(report_id)
    assert status["status"] == "failed" and status["result"] is None


@pytest.mark.parametrize("field", ["source_report", "input_hashes", "evidence", "model_analysis"])
def test_invalid_analyzer_output_is_never_published(context, monkeypatch, field):
    _, agent, report_id, _ = context
    original = analysis._rules_analysis

    def malformed(*args):
        result = original(*args)
        result[field] = "invalid" if field == "source_report" else {}
        return result

    monkeypatch.setattr(analysis, "_rules_analysis", malformed)
    assert analyze(agent, report_id)["status"] == "failed"
    assert not list(agent.cache_dir.glob("*/result-*"))
    assert not list(agent.cache_dir.glob("*/.pending-*"))


def test_unchanged_status_reuses_verified_file_content_until_cache_expires(context, monkeypatch):
    _, agent, report_id, _ = context
    calls = []
    original = analysis.parse_report

    def counted(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(analysis, "parse_report", counted)
    assert agent.status(report_id)["status"] == "idle"
    assert len(calls) == 1
    for _ in range(3):
        assert agent.status(report_id)["status"] == "idle"
    assert len(calls) == 1
    original_clock = analysis.time.monotonic
    monkeypatch.setattr(analysis.time, "monotonic", lambda: original_clock() + analysis.FINGERPRINT_CACHE_SECONDS + 1)
    assert agent.status(report_id)["status"] == "idle"
    assert len(calls) == 2


def test_request_fingerprints_once_before_worker_and_worker_always_verifies_twice(context, monkeypatch):
    _, agent, report_id, _ = context
    original = agent._fingerprint
    calls = []

    def counted(*args, **kwargs):
        calls.append((threading.current_thread() is threading.main_thread(), bool(kwargs.get("use_cache"))))
        return original(*args, **kwargs)

    monkeypatch.setattr(agent, "_fingerprint", counted)
    assert request(agent, report_id)["status"] == "running"
    wait_for(agent)
    assert calls.count((True, True)) == 1
    assert calls.count((False, False)) == 2


def test_result_retention_cleans_only_owned_generated_directories(context):
    reports, agent, report_id, source = context
    original_files = {path.name: path.read_bytes() for path in source.parent.iterdir()}
    first = analyze(agent, report_id)
    report_key = agent._key(reports.repository.get_report(report_id))
    directory = agent.cache_dir / report_key
    old_result = next(directory.glob("result-*"))
    orphan = directory / (".pending-" + "a" * 32)
    orphan.mkdir()
    (orphan / "partial.txt").write_text("interrupted job")
    unrelated = directory / "result-manual-notes"
    unrelated.mkdir()
    (unrelated / "keep.txt").write_text("keep")
    for _ in range(4):
        assert request(agent, report_id, force=True)["status"] == "running"
        wait_for(agent)
    assert agent.status(report_id)["status"] == "complete"
    results = [path for path in directory.glob("result-*") if path != unrelated]
    assert len(results) == 3
    assert not old_result.exists()
    assert not orphan.exists()
    assert (unrelated / "keep.txt").read_text() == "keep"
    assert {path.name: path.read_bytes() for path in source.parent.iterdir()} == original_files
    assert first["status"] == "complete"


def test_rule_capacity_is_shared_across_service_instances(context, monkeypatch):
    reports, agent, report_id, _ = context
    agent.rules_concurrency = 1
    other = FailureAnalysisService(reports, agent.cache_dir, rules_concurrency=1)
    write_bundle(reports.root, bundle(run_id="other-run", report_run_id="other-report"), name="other")
    reports.scan()
    other_id = next(item["id"] for device in reports.list_devices()["devices"] for item in device["reports"] if item["id"] != report_id)
    entered, released = threading.Event(), threading.Event()
    original = analysis._rules_analysis

    def blocked(*args):
        entered.set()
        assert released.wait(timeout=5)
        return original(*args)

    monkeypatch.setattr(analysis, "_rules_analysis", blocked)
    try:
        assert request(agent, report_id)["status"] == "running"
        assert entered.wait(timeout=5)
        with pytest.raises(ConflictError, match="并发上限"):
            request(other, other_id)
    finally:
        released.set()
        wait_for(agent)
    assert request(other, other_id)["status"] == "running"
    wait_for(other)
    assert other.status(other_id)["status"] == "complete"


def test_model_pool_remains_separate_and_serial_by_default(context, monkeypatch):
    reports, rules_agent, report_id, _ = context
    model_agent = FailureAnalysisService(reports, rules_agent.cache_dir, model_enabled=True)
    other = FailureAnalysisService(reports, rules_agent.cache_dir, model_enabled=True)
    write_bundle(reports.root, bundle(run_id="other-run", report_run_id="other-report"), name="other")
    reports.scan()
    other_id = next(item["id"] for device in reports.list_devices()["devices"] for item in device["reports"] if item["id"] != report_id)
    entered, released = threading.Event(), threading.Event()

    def blocked(*args):
        entered.set()
        assert released.wait(timeout=5)
        raise analysis.ModelAnalysisError("Synthetic model unavailable")

    monkeypatch.setattr(analysis, "analyze_report", blocked)
    try:
        assert request(model_agent, report_id)["status"] == "running"
        assert entered.wait(timeout=5)
        with pytest.raises(ConflictError, match="并发上限"):
            request(other, other_id)
        # A different report's rules do not need a model slot.
        assert request(rules_agent, other_id)["status"] == "running"
        wait_for(rules_agent)
        assert rules_agent.status(other_id)["status"] == "complete"
    finally:
        released.set()
        wait_for(model_agent)


def test_validated_model_result_can_be_reused_but_bad_cached_citations_are_rejected(context, monkeypatch):
    from modules.test_failures.qc_agent import analyzer

    reports, existing, report_id, _ = context
    agent = FailureAnalysisService(reports, existing.cache_dir, model_enabled=True)
    calls = []

    def model_response(prompt, _settings):
        calls.append(prompt)
        return {"content": {"assessments": [{
            "finding_id": finding["finding_id"], "priority": 2,
            "reasoning": finding["explanation_options"][0],
            "next_question": finding["question_options"][0],
            "evidence_refs": finding["evidence_refs"],
        } for finding in prompt["findings"]]}}

    monkeypatch.setattr(analyzer, "_request_model", model_response)
    completed = analyze(agent, report_id)
    assert completed["status"] == "complete"
    assert completed["result"]["model_analysis"]["status"] == "completed"
    assert calls
    assert request(agent, report_id) == completed
    state_path = agent._state_path(agent._key(reports.repository.get_report(report_id)))
    state = analysis._read_json(state_path)
    result_path = state_path.parent / state["result_directory"] / "analysis.json"
    result = analysis._read_json(result_path)
    result["model_analysis"]["assessments"][0]["evidence_refs"] = ["nonexistent-evidence"]
    state["result_sha256"] = analysis._digest(result)
    analysis._write_json(result_path, result)
    analysis._write_json(state_path, state)
    assert agent.status(report_id)["status"] == "failed"


def test_cannot_write_analysis_into_source_directory(context):
    reports, _, _, _ = context
    with pytest.raises(ValueError):
        FailureAnalysisService(reports, reports.root / "analysis")


def test_symlink_attachment_is_not_read(context, tmp_path):
    _, agent, report_id, source = context
    outside = tmp_path / "private-secret"
    outside.write_text("DO NOT READ", encoding="utf-8")
    source.unlink()
    source.symlink_to(outside)
    assert agent.status(report_id)["status"] == "stale"
    with pytest.raises(ConflictError):
        request(agent, report_id)
    assert not agent.cache_dir.exists()


def test_manifest_artifact_paths_are_not_followed(context, tmp_path):
    reports, agent, report_id, source = context
    outside = tmp_path / "secret.json"
    outside.write_text("private secret", encoding="utf-8")
    payload = json.loads(source.read_text())
    payload["artifacts"] = [{"role": "manifest", "path": str(outside), "upload_status": "uploaded"}]
    source.write_text(json.dumps(payload))
    reports.scan()
    status = analyze(agent, report_id)
    assert status["status"] == "complete"
    assert all("secret.json" not in item["result"]["input_hashes"] for item in [status])


def test_unknown_report_id_is_not_treated_as_path(context):
    _, agent, _, source = context
    with pytest.raises(NotFoundError):
        agent.request(str(source), "unknown")
    with pytest.raises(NotFoundError):
        agent.status("../../private")


@pytest.fixture
def api(context, tmp_path):
    reports, agent, report_id, _ = context
    auth = AuthService(db_path=tmp_path / "auth.sqlite3", jwt_secret="test-secret-" * 4,
                       issuer="test", audience="test", access_token_minutes=5, refresh_token_hours=1)
    auth.initialize()
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[routes.get_service] = lambda: reports
    app.dependency_overrides[routes.get_analysis_service] = lambda: agent
    with TestClient(app) as client:
        yield client, auth, agent, PREFIX + f"/reports/{report_id}/analysis"


def test_analysis_routes_require_login(api):
    client, _, _, endpoint = api
    assert client.get(endpoint).status_code == 401
    assert client.post(endpoint).status_code == 401


def test_viewer_can_read_but_cannot_generate(api):
    client, auth, agent, endpoint = api
    _, session = session_for(auth, role="viewer")
    current = client.get(endpoint, headers=bearer(session)).json()
    assert current["status"] == "idle"
    assert client.post(endpoint, headers=bearer(session)).status_code == 403
    assert client.post(endpoint, headers=bearer(session), json={
        "report_revision": current["report_revision"], "force": True,
    }).status_code == 403
    assert agent._thread is None


def test_analysis_cookie_requires_csrf(api):
    client, auth, agent, endpoint = api
    _, session = session_for(auth)
    client.cookies.set(ACCESS_COOKIE_NAME, session.access_token)
    client.cookies.set(CSRF_COOKIE_NAME, session.csrf_token)
    assert client.post(endpoint).status_code == 403
    assert client.post(endpoint, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    response = client.post(endpoint, headers={"X-CSRF-Token": session.csrf_token}, json={"report_revision": client.get(endpoint).json()["report_revision"]})
    assert response.status_code == 202
    assert response.json()["status"] == "running"
    wait_for(agent)
    assert client.get(endpoint).json()["status"] == "complete"


def test_analysis_route_rejects_paths_and_reuses_finished_result(api):
    client, auth, agent, endpoint = api
    _, session = session_for(auth)
    headers = bearer(session)
    assert client.post(endpoint, headers=headers, json={"path": "/etc/passwd"}).status_code == 422
    assert not agent.cache_dir.exists()
    body = {"report_revision": client.get(endpoint, headers=headers).json()["report_revision"]}
    assert client.post(endpoint, headers=headers, json=body).status_code == 202
    wait_for(agent)
    result = client.post(endpoint, headers=headers, json=body)
    assert result.status_code == 200 and result.json()["status"] == "complete"
    assert client.get(PREFIX + "/reports/unknown/analysis", headers=headers).status_code == 404


def test_force_analysis_route_regenerates_without_discarding_previous_result(api, context, monkeypatch):
    client, auth, agent, endpoint = api
    reports, _, _, source = context
    _, session = session_for(auth)
    headers = bearer(session)
    original = analysis._rules_analysis
    calls = []

    def counted(*args):
        calls.append(args[1])
        return original(*args)

    monkeypatch.setattr(analysis, "_rules_analysis", counted)
    monkeypatch.setattr(analysis, "analyze_report", lambda *args: pytest.fail("Unexpected model call"))
    source_before = {path.name: path.read_bytes() for path in source.parent.iterdir()}
    devices_before = reports.list_devices()["devices"]
    body = {"report_revision": client.get(endpoint, headers=headers).json()["report_revision"]}
    assert client.post(endpoint, headers=headers, json=body).status_code == 202
    wait_for(agent)
    first = client.get(endpoint, headers=headers).json()
    assert first["status"] == "complete"
    old_result = next(agent.cache_dir.glob("*/result-*"))
    old_files = {path.relative_to(old_result): path.read_bytes() for path in old_result.rglob("*") if path.is_file()}

    assert client.get(endpoint, headers=headers).json() == first
    ordinary = client.post(endpoint, headers=headers, json=body)
    assert ordinary.status_code == 200 and ordinary.json() == first
    assert len(calls) == 1
    regenerated = client.post(endpoint, headers=headers, json={**body, "force": True})
    assert regenerated.status_code == 202 and regenerated.json()["status"] == "running"
    wait_for(agent)
    latest = client.get(endpoint, headers=headers).json()
    assert latest["status"] == "complete"
    assert latest["report_revision"] == first["report_revision"]
    assert len(calls) == 2
    assert len(list(agent.cache_dir.glob("*/result-*"))) == 2
    assert {path.relative_to(old_result): path.read_bytes() for path in old_result.rglob("*") if path.is_file()} == old_files
    assert client.post(endpoint, headers=headers, json=body).json() == latest
    assert len(calls) == 2
    assert {path.name: path.read_bytes() for path in source.parent.iterdir()} == source_before
    assert reports.list_devices()["devices"] == devices_before


def test_force_completed_report_respects_configured_capacity(api, context, monkeypatch):
    client, auth, agent, endpoint = api
    reports, _, report_id, _ = context
    agent.rules_concurrency = 1
    first = analyze(agent, report_id)
    _, session = session_for(auth)
    write_bundle(reports.root, bundle(run_id="different-run", report_run_id="different-report-run"), name="second")
    reports.scan()
    other_id = next(item["id"] for device in reports.list_devices()["devices"] for item in device["reports"] if item["id"] != report_id)
    entered, released = threading.Event(), threading.Event()
    original = analysis._rules_analysis
    calls = []

    def blocking(*args):
        calls.append(args[1])
        entered.set()
        assert released.wait(timeout=5)
        return original(*args)

    monkeypatch.setattr(analysis, "_rules_analysis", blocking)
    try:
        assert request(agent, other_id)["status"] == "running"
        assert entered.wait(timeout=5)
        response = client.post(endpoint, headers=bearer(session), json={
            "report_revision": first["report_revision"], "force": True,
        })
        assert response.status_code == 409
        assert agent.status(report_id) == first
    finally:
        released.set()
        wait_for(agent)
    assert len(calls) == 1
    assert len(list(agent.cache_dir.glob("*/result-*"))) == 2


@pytest.mark.parametrize("force", [False, True])
def test_analysis_rejects_revision_changed_since_detail_opened(api, context, force):
    client, auth, agent, endpoint = api
    reports, _, _, source = context
    _, session = session_for(auth)
    headers = bearer(session)
    old_revision = client.get(endpoint, headers=headers).json()["report_revision"]
    payload = json.loads(source.read_text())
    payload["report_rows"][0]["data"] = [42, "FAIL"]
    source.write_text(json.dumps(payload))
    reports.scan()
    response = client.post(endpoint, headers=headers, json={"report_revision": old_revision, "force": force})
    assert response.status_code == 409
    assert not agent.cache_dir.exists()
    assert agent._thread is None
    assert client.post(endpoint, headers=headers).status_code == 422


def test_analysis_route_rejects_same_stat_json_then_recovers_with_scanned_revision(api, context):
    client, auth, agent, endpoint = api
    reports, _, _, source = context
    _, session = session_for(auth)
    headers = bearer(session)
    old_revision = client.get(endpoint, headers=headers).json()["report_revision"]
    payload = json.loads(source.read_text())
    payload["report_rows"][0]["data"][0] = 4.5
    rewrite_json_preserving_stat(source, payload)
    rejected = client.post(endpoint, headers=headers, json={"report_revision": old_revision})
    assert rejected.status_code == 409
    assert not agent.cache_dir.exists()
    reports.scan()
    new_revision = client.get(endpoint, headers=headers).json()["report_revision"]
    assert new_revision != old_revision
    assert client.post(endpoint, headers=headers, json={"report_revision": old_revision}).status_code == 409
    started = client.post(endpoint, headers=headers, json={"report_revision": new_revision})
    assert started.status_code == 202
    wait_for(agent)
    completed = client.get(endpoint, headers=headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "complete"
    assert completed.json()["report_revision"] == new_revision


@pytest.mark.parametrize("force", [False, True])
def test_analysis_without_structured_attachment_is_unsupported(context, monkeypatch, force):
    reports, agent, report_id, _ = context
    record = reports.repository.get_report(report_id)
    record["attachment_paths"].pop("json")
    monkeypatch.setattr(reports.repository, "get_report", lambda _id: record)
    assert agent.status(report_id)["status"] == "unsupported"
    assert request(agent, report_id, force=force)["status"] == "unsupported"
    assert not agent.cache_dir.exists()
