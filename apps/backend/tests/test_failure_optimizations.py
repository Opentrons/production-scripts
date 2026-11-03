"""Regressions for independent folder evidence, audit history and immutable IO."""
from __future__ import annotations

import json
import os

import pytest

from modules.test_failures import scanner
from modules.test_failures import service as service_module
from modules.test_failures.service import NotFoundError
from test_test_failures import (
    bundle, categorized_evidence, confirm, evidence, only_device,
    rewrite_json_preserving_stat, write_bundle,
)


def test_analysis_default_matches_all_filters_on_one_evidence_package(categorized_evidence):
    _, service = categorized_evidence
    result = service.list_devices(kind="runtime_error", product="P50M")
    device = result["devices"][0]
    matching = [report for report in device["reports"] if report["id"] in device["matched_report_ids"]]
    assert len(matching) == 1
    assert matching[0]["kind"] == "runtime_error"
    assert len(device["reports"]) == 2  # retain the whole folder for audit/confirmation
    assert service.list_devices(q="cohort-red pressure", kind="runtime_error")["devices"] == []
    sn_query = service.list_devices(q="FACET-A", mode="volume_qc")["devices"][0]
    assert sn_query["matched_report_ids"] == device["matched_report_ids"]


def test_confirmation_history_exposes_exact_version_and_keeps_original_note(evidence):
    root, _, service = evidence
    source = write_bundle(root)
    service.scan()
    before = only_device(service)
    saved = confirm(service, before, "保留原因、措施与备注")
    report = before["reports"][0]
    history = service.list_confirmations(before["id"])["items"][0]
    assert history["coverage"] == [{
        "report_id": report["id"], "revision": report["revision"],
        "report_folder": before["report_folder"], "source_name": source.name,
        "report_role": "main", "test_time": report["test_time"],
        "current": True, "metadata_recorded": True,
    }]
    assert saved["device"]["reports"][0]["covered_by"] == [saved["confirmation"]["id"]]
    source.write_text(json.dumps(bundle(failure_details=["New independent failure in same report"])))
    service.scan()
    latest = only_device(service)
    assert latest["reports"][0]["confirmation_status"] == "pending"
    assert latest["reports"][0]["covered_by"] == []
    history = service.list_confirmations(before["id"])["items"][0]
    assert history["text"] == saved["confirmation"]["text"]
    assert history["coverage"][0]["revision"] == report["revision"]
    assert history["coverage"][0]["current"] is False


def test_summary_exposes_omitted_count_while_search_retains_all_evidence(evidence):
    root, _, service = evidence
    write_bundle(root, bundle(failure_details=[f"Distinct failure {index:02d}" for index in range(16)]))
    service.scan()
    device = only_device(service)
    assert len(device["summary"]) == 10
    assert device["summary_total"] >= 16
    assert device["summary_omitted"] == device["summary_total"] - 10
    assert service.list_devices(q="Distinct failure 15")["total"] == 1


@pytest.mark.parametrize("with_log", [False, True])
def test_unchanged_invalid_json_not_reparsed_but_error_remains_and_recovers(evidence, monkeypatch, with_log):
    root, _, service = evidence
    source = write_bundle(root)
    if with_log:
        source.with_suffix('.log').write_text('Failure details:\n- Pressure outside tolerance\n')
    source.write_text('{invalid-json')
    original = service.scanner._parse
    calls = []
    def counted(relative, kind, checksum):
        calls.append(kind)
        return original(relative, kind, checksum)
    monkeypatch.setattr(service.scanner, '_parse', counted)
    for _ in range(3):
        assert service.scan()['parse_errors'] >= 1
    assert calls.count('json') == 1
    source.write_text(json.dumps(bundle()))
    assert service.scan()['parse_errors'] == 0
    assert calls.count('json') == 2
    assert only_device(service)['reports'][0]['source_format'] == 'json'


def test_scanner_hash_cache_reuses_read_but_invalidates_even_with_restored_mtime(evidence, monkeypatch):
    root, _, service = evidence
    source = write_bundle(root)
    service.scan()
    before = only_device(service)['reports'][0]['revision']
    original = scanner.open_source
    reads = []
    class CountingReader:
        def __init__(self, *args):
            self.handle = original(*args)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.handle.close()
        def fileno(self):
            return self.handle.fileno()
        def read(self, *args):
            value = self.handle.read(*args)
            reads.append(len(value))
            return value
    monkeypatch.setattr(scanner, 'open_source', CountingReader)
    service.scanner._fingerprint(str(source.relative_to(root)))
    assert reads == []
    payload = json.loads(source.read_text())
    payload['report_rows'][0]['data'][0] = 4.5
    rewrite_json_preserving_stat(source, payload)
    service.scan()
    assert sum(reads) > 0
    assert only_device(service)['reports'][0]['revision'] != before


def test_same_stat_attachment_rewrite_is_unavailable_and_rejected(evidence):
    root, _, service = evidence
    source = write_bundle(root)
    log = source.with_suffix('.log')
    log.write_bytes(b'original')
    service.scan()
    report_id = only_device(service)['reports'][0]['id']
    assert next(a for a in service.get_report(report_id)['attachments'] if a['kind'] == 'log')['available']
    info = log.stat()
    log.write_bytes(b'modified')
    os.utime(log, ns=(info.st_atime_ns, info.st_mtime_ns))
    assert not next(a for a in service.get_report(report_id)['attachments'] if a['kind'] == 'log')['available']
    with pytest.raises(NotFoundError):
        service.preview_attachment(report_id, 'log')
    with pytest.raises(NotFoundError):
        service.open_attachment(report_id, 'log')


def test_attachment_download_is_immutable_after_open(evidence):
    root, _, service = evidence
    source = write_bundle(root)
    log = source.with_suffix('.log')
    log.write_bytes(b'original')
    service.scan()
    report_id = only_device(service)['reports'][0]['id']
    handle, filename = service.open_attachment(report_id, 'log')
    with handle:
        log.write_bytes(b'modified')
        assert handle.read() == b'original'
    assert filename == log.name


def test_attachment_changes_refresh_evidence_without_reopening_confirmation(evidence):
    root, _, service = evidence
    source = write_bundle(root)
    service.scan()
    before = confirm(service, only_device(service))['device']
    log = source.with_suffix('.log')
    log.write_text('Additional attachment')
    service.scan()
    after = only_device(service)
    old_report, new_report = before['reports'][0], after['reports'][0]
    assert after['unconfirmed_count'] == 0
    assert after['version'] == before['version']
    assert old_report['revision'] == new_report['revision']
    assert old_report['evidence_version'] != new_report['evidence_version']
    assert service.get_report(new_report['id'])['evidence_version'] == new_report['evidence_version']
    service.scan()
    assert only_device(service)['reports'][0]['evidence_version'] == new_report['evidence_version']


def test_detail_verifies_without_copying_all_attachments(evidence, monkeypatch):
    root, _, service = evidence
    write_bundle(root)
    service.scan()
    report_id = only_device(service)['reports'][0]['id']
    def forbidden(*args, **kwargs):
        pytest.fail('Detail metadata must not create attachment snapshots')
    monkeypatch.setattr(service_module.tempfile, 'SpooledTemporaryFile', forbidden)
    assert service.get_report(report_id)['attachments'][0]['available'] is True


def test_mount_failure_clears_old_diagnostics_and_retains_last_success(evidence):
    root, _, service = evidence
    write_bundle(root)
    good = service.scan()
    root.rename(root.with_name('unmounted'))
    failed = service.scan()
    assert failed['source_status'] == 'unavailable'
    assert failed['last_successful_scan_at'] == good['last_successful_scan_at']
    assert failed['error']
    assert failed['errors'] == []
    assert failed['pending_files'] == failed['parse_errors'] == 0
    assert len(service.list_devices()['devices']) == 1  # historical evidence survives
