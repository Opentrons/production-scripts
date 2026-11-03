from __future__ import annotations

import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from modules.test_failures import report_links as module
from modules.test_failures.report_links import ReportLinkService, normalize_report_url


SN = "P50MV3520250813A09"
RUN = "run-25-05-30-14-16-59"
URL = "https://docs.google.com/spreadsheets/d/report_alpha/edit"
OTHER_URL = "https://docs.google.com/spreadsheets/d/report_beta/edit"
SOURCE_URL = "https://docs.google.com/spreadsheets/d/master_catalog/edit#gid=123&range=D11"
REPORT = {"sn": SN, "report_run_id": RUN}


def catalog_row(url=URL, *, sn=SN, run="", row=11):
    return {"sn": sn, "report_run_id": run, "url": url, "sheet_title": "8ch P50",
            "sheet_id": 123, "row": row, "source_url": SOURCE_URL}


class FakeSource:
    cache_namespace = "synthetic-master:tabs-123:v1"

    def __init__(self, rows=None, identities=None):
        self.rows = rows if rows is not None else [catalog_row()]
        self.identities = identities if identities is not None else {URL: dict(REPORT)}
        self.catalog_calls = 0
        self.identity_calls = []
        self.catalog_error = None

    def read_catalog(self):
        self.catalog_calls += 1
        if self.catalog_error:
            raise self.catalog_error
        return copy.deepcopy(self.rows)

    def read_identity(self, url):
        self.identity_calls.append(url)
        result = self.identities[url]
        if isinstance(result, Exception):
            raise result
        return copy.deepcopy(result)


@pytest.fixture
def make_service(tmp_path):
    services = []

    def make(source=None, **kwargs):
        service = ReportLinkService(tmp_path / "links.sqlite3", source or FakeSource(), **kwargs)
        services.append(service)
        return service

    yield make
    for service in services:
        service.close(wait=True)


def finished(service, report=None, *, force=False):
    report = report or REPORT
    result = service.lookup(report, force=force)
    deadline = time.monotonic() + 3
    while result["status"] == "running" and time.monotonic() < deadline:
        time.sleep(0.005)
        result = service.lookup(report)
    assert result["status"] != "running", "Background lookup did not finish"
    return result


def test_two_stage_exact_match_keeps_report_and_public_result_independent(make_service):
    source = FakeSource([catalog_row(sn="ANOTHER-SN"), catalog_row()])
    service = make_service(source)
    report = {**REPORT, "revision": "unchanged", "evidence_version": "same"}
    before = copy.deepcopy(report)
    result = finished(service, report)
    assert report == before
    assert result == {"status": "matched", "sn": SN, "report_run_id": RUN,
                      "checked_at": result["checked_at"], "stale": False, "error_code": None,
                      "matches": [{key: catalog_row()[key] for key in ("url", "sheet_title", "sheet_id", "row", "source_url")}]}
    assert result["checked_at"]
    assert source.identity_calls == [URL]
    result["matches"].clear()
    assert service.lookup(report)["matches"]


@pytest.mark.parametrize("identity", [{"sn": SN, "report_run_id": "run-25-05-30-14-17-59"},
                                      {"sn": "OTHER-SN", "report_run_id": RUN},
                                      {"sn": SN.lower(), "report_run_id": RUN}])
def test_never_matches_only_serial_time_or_case_approximation(make_service, identity):
    source = FakeSource(identities={URL: identity})
    assert finished(make_service(source))["status"] == "not_found"


def test_catalog_explicit_run_still_requires_target_verification(make_service):
    source = FakeSource([catalog_row(run=RUN), catalog_row(OTHER_URL, run="different-run")],
                        {URL: REPORT, OTHER_URL: {"sn": SN, "report_run_id": "different-run"}})
    result = finished(make_service(source))
    assert result["status"] == "matched"
    assert source.identity_calls == [URL, OTHER_URL]


def test_tracker_run_id_cannot_override_mismatched_target_metadata(make_service):
    source = FakeSource([catalog_row(run=RUN)], {URL: {"sn": SN, "report_run_id": "newer-run"}})
    assert finished(make_service(source))["status"] == "not_found"


def test_unknown_serial_or_missing_run_does_not_start_google(make_service):
    source = FakeSource()
    service = make_service(source)
    for report in ({"sn": SN}, {"sn": "unknown-SN", "report_run_id": RUN}, {"report_run_id": RUN},
                   {"sn": SN, "report_run_id": None}):
        assert service.lookup(report)["status"] == "missing_identity"
    assert source.catalog_calls == 0


def test_only_boundary_whitespace_is_normalized(make_service):
    source = FakeSource([catalog_row(sn=f" {SN} ")], {URL: {"sn": f" {SN} ", "report_run_id": f" {RUN} "}})
    assert finished(make_service(source), {"sn": f" {SN} ", "report_run_id": f" {RUN} "})["status"] == "matched"


def test_duplicate_sharing_urls_do_not_become_ambiguity(make_service):
    source = FakeSource([catalog_row(URL + "?usp=sharing"), catalog_row(URL + "?pli=1", row=12)])
    result = finished(make_service(source))
    assert result["status"] == "matched"
    assert len(result["matches"]) == 1
    assert source.identity_calls == [URL]


def test_verified_legacy_gid_repair_uses_actual_target_and_deduplicates(make_service):
    legacy, actual = URL + "#gid=0", URL + "#gid=859846748"
    source = FakeSource([catalog_row(legacy), catalog_row(actual, row=12)],
                        {legacy: {**REPORT, "resolved_url": actual}, actual: REPORT})
    service = make_service(source)
    result = finished(service)
    assert result["status"] == "matched"
    assert [match["url"] for match in result["matches"]] == [actual]
    assert result["matches"][0]["source_url"] == SOURCE_URL
    service.close(wait=True)
    offline = FakeSource()
    offline.catalog_error = RuntimeError("offline")
    restarted = make_service(offline)
    assert restarted.lookup(REPORT) == result
    assert finished(restarted, {**REPORT, "report_run_id": "different-run"})["status"] == "not_found"
    assert offline.catalog_calls == 0
    assert offline.identity_calls == []


def test_verified_legacy_gid_repair_still_requires_exact_run(make_service):
    legacy = URL + "#gid=0"
    source = FakeSource([catalog_row(legacy)], {legacy: {**REPORT, "report_run_id": "other-run", "resolved_url": URL + "#gid=8"}})
    assert finished(make_service(source))["status"] == "not_found"


@pytest.mark.parametrize("original,resolved", [
    (URL + "#gid=0", OTHER_URL + "#gid=8"),
    (URL + "#gid=0", "https://example.invalid/report"),
    (URL + "#gid=0", URL),
    (URL + "#gid=0", URL + "#gid=0"),
    (URL + "#gid=7", URL + "#gid=8"),
])
def test_repaired_target_cannot_change_workbook_or_nonzero_gid(make_service, original, resolved):
    source = FakeSource([catalog_row(original)], {original: {**REPORT, "resolved_url": resolved}})
    result = finished(make_service(source))
    assert result["status"] == "unavailable"
    assert result["matches"] == []


def test_untrusted_repaired_target_is_rejected_when_loading_identity_cache(make_service):
    legacy = URL + "#gid=0"
    first = make_service()
    first._persist("identity", legacy, {"identity": {**REPORT, "resolved_url": OTHER_URL + "#gid=8"}, "expires_at": time.time() + 300}, time.time())
    first.close(wait=True)
    source = FakeSource([catalog_row(legacy)], {legacy: REPORT})
    assert finished(make_service(source))["status"] == "matched"
    assert source.identity_calls == [legacy]


def test_two_distinct_verified_reports_are_ambiguous(make_service):
    source = FakeSource([catalog_row(), catalog_row(OTHER_URL)], {URL: REPORT, OTHER_URL: REPORT})
    result = finished(make_service(source))
    assert result["status"] == "ambiguous"
    assert {item["url"] for item in result["matches"]} == {URL, OTHER_URL}


@pytest.mark.parametrize("failure", [RuntimeError("private-token-must-not-escape"), {}, {"sn": SN}])
def test_incomplete_candidate_prevents_false_unique_match(make_service, failure):
    source = FakeSource([catalog_row(), catalog_row(OTHER_URL)], {URL: REPORT, OTHER_URL: failure})
    result = finished(make_service(source))
    assert result["status"] == "unavailable"
    assert result["matches"] == []
    assert result["checked_at"] is None
    assert "private-token" not in str(result)


def test_force_failure_retains_previous_verified_links_as_stale(make_service):
    source = FakeSource()
    service = make_service(source)
    original = finished(service)
    source.identities[URL] = RuntimeError("access denied")
    result = finished(service, force=True)
    assert result["status"] == "unavailable"
    assert result["stale"] is True
    assert result["matches"] == original["matches"]
    assert result["checked_at"] == original["checked_at"]
    assert source.catalog_calls == 2
    assert source.identity_calls == [URL, URL]
    source.identities[URL] = REPORT
    assert finished(service, force=True)["status"] == "matched"


def test_catalog_failure_does_not_return_false_not_found_or_use_expired_catalog(make_service):
    source = FakeSource()
    service = make_service(source)
    original = finished(service)
    source.catalog_error = RuntimeError("network down")
    result = finished(service, force=True)
    assert result["status"] == "unavailable"
    assert result["error_code"] == "catalog_unavailable"
    assert result["matches"] == original["matches"]
    assert finished(service, {"sn": "NEW-SN", "report_run_id": RUN})["status"] == "unavailable"
    # Distinct folders/keys do not hammer the failing shared catalog.
    assert source.catalog_calls == 2


def test_ttl_and_forced_retry_refresh_negative_results(make_service, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(module.time, "time", lambda: clock[0])
    source = FakeSource([])
    service = make_service(source, refresh_seconds=10)
    assert finished(service)["status"] == "not_found"
    source.rows = [catalog_row()]
    assert service.lookup(REPORT)["status"] == "not_found"
    assert source.catalog_calls == 1
    clock[0] += 11
    assert finished(service)["status"] == "matched"
    assert source.catalog_calls == 2
    source.identities[URL] = {"sn": SN, "report_run_id": "new-run"}
    assert service.lookup(REPORT)["status"] == "matched"
    assert finished(service, force=True)["status"] == "not_found"
    assert source.identity_calls == [URL, URL]


def test_failure_retries_after_backoff_without_infinite_poll_jobs(make_service, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(module.time, "time", lambda: clock[0])
    source = FakeSource(identities={URL: RuntimeError("temporary")})
    service = make_service(source)
    assert finished(service)["status"] == "unavailable"
    for _ in range(20):
        assert service.lookup(REPORT)["status"] == "unavailable"
    assert source.identity_calls == [URL]
    source.identities[URL] = REPORT
    clock[0] += 31
    assert finished(service)["status"] == "matched"
    assert source.catalog_calls == 1
    assert source.identity_calls == [URL, URL]


def test_slow_google_never_blocks_lookup_and_concurrent_requests_are_deduplicated(make_service):
    entered, release = threading.Event(), threading.Event()

    class SlowSource(FakeSource):
        def read_catalog(self):
            entered.set()
            assert release.wait(2)
            return super().read_catalog()

    source = SlowSource()
    service = make_service(source)
    try:
        started = time.monotonic()
        assert service.lookup(REPORT)["status"] == "running"
        assert time.monotonic() - started < 0.2
        assert entered.wait(1)
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: service.lookup(REPORT, force=True), range(50)))
        assert all(result["status"] == "running" for result in results)
        assert len(service._pending) == 1
    finally:
        release.set()
    assert finished(service)["status"] == "matched"
    assert source.catalog_calls == 1
    assert source.identity_calls == [URL]


def test_queue_is_bounded_and_busy_response_can_retry(make_service, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(module, "MAX_PENDING", 2)

    class SlowSource(FakeSource):
        def read_catalog(self):
            assert release.wait(2)
            return super().read_catalog()

    service = make_service(SlowSource())
    try:
        assert service.lookup(REPORT)["status"] == "running"
        assert service.lookup({**REPORT, "sn": "SECOND"})["status"] == "running"
        busy = service.lookup({**REPORT, "sn": "THIRD"})
        assert busy["status"] == "unavailable"
        assert busy["error_code"] == "busy"
        assert len(service._pending) == 2
    finally:
        release.set()
    finished(service)
    assert finished(service, {**REPORT, "sn": "THIRD"})["status"] == "not_found"


def test_persisted_cache_survives_restart_and_isolated_by_source_configuration(make_service):
    first = make_service()
    result = finished(first)
    first.close(wait=True)
    offline = FakeSource()
    offline.catalog_error = RuntimeError("offline")
    restarted = make_service(offline)
    assert restarted.lookup(REPORT) == result
    assert offline.catalog_calls == 0
    changed_source = FakeSource([])
    changed_source.cache_namespace = "other-spreadsheet:tabs-456:v1"
    changed = make_service(changed_source)
    assert finished(changed)["status"] == "not_found"
    assert changed_source.catalog_calls == 1


def test_persisted_identity_cache_is_reused_for_another_run(make_service):
    first = make_service()
    finished(first)
    first.close(wait=True)
    source = FakeSource()
    source.catalog_error = RuntimeError("offline")
    source.identities[URL] = RuntimeError("offline")
    restarted = make_service(source)
    assert finished(restarted, {**REPORT, "report_run_id": "another-run"})["status"] == "not_found"
    assert source.catalog_calls == 0
    assert source.identity_calls == []


def test_disabled_service_does_not_initialize_google_or_files(tmp_path):
    service = ReportLinkService(tmp_path / "unused.sqlite3", enabled=False)
    assert service.lookup(REPORT)["status"] == "disabled"
    assert not service.cache_path.exists()
    service.close()


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://docs.google.com.evil.test/spreadsheets/d/x/edit",
                                 "http://docs.google.com/spreadsheets/d/x/edit",
                                 "https://user@docs.google.com/spreadsheets/d/x/edit",
                                 "https://docs.google.com:8443/spreadsheets/d/x/edit", "https://example.com/report"])
def test_untrusted_report_urls_are_rejected(make_service, url):
    assert normalize_report_url(url) is None
    assert finished(make_service(FakeSource([catalog_row(url)])))["error_code"] == "invalid_catalog"


def test_url_normalization_preserves_worksheet_gid():
    assert normalize_report_url(URL + "?usp=sharing&gid=123#gid=123") == URL + "#gid=123"
    assert normalize_report_url(URL + "?gid=456#gid=123") is None
    assert normalize_report_url(URL + "?gid=abc") is None
    assert normalize_report_url(URL.replace("docs.google.com", "docs.google.com:443")) == URL


def test_invalid_source_configuration_does_not_break_service(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_SHEET_ID", "invalid value")
    service = ReportLinkService(tmp_path / "links.sqlite3")
    try:
        result = finished(service)
        assert result["status"] == "unavailable"
        assert result["error_code"] == "configuration_error"
    finally:
        service.close(wait=True)


def test_corrupt_persistent_cache_does_not_break_service(tmp_path, make_service):
    (tmp_path / "links.sqlite3").write_text("corrupt sqlite data")
    assert finished(make_service())["status"] == "matched"


def test_invalid_link_marker_only_blocks_its_own_serial_and_survives_restart(make_service):
    invalid = {**catalog_row("", sn="BAD-LINK-SN"), "error_code": "invalid_link"}
    source = FakeSource([catalog_row(), invalid])
    service = make_service(source)
    assert finished(service)["status"] == "matched"
    result = finished(service, {**REPORT, "sn": "BAD-LINK-SN"})
    assert result["status"] == "unavailable"
    assert result["error_code"] == "invalid_link"
    assert result["matches"] == []
    assert source.identity_calls == [URL]
    service.close(wait=True)
    offline = FakeSource()
    offline.catalog_error = RuntimeError("offline")
    restarted = make_service(offline)
    result = finished(restarted, {"sn": "BAD-LINK-SN", "report_run_id": "another-run"})
    assert result["error_code"] == "invalid_link"
    assert offline.catalog_calls == 0


def test_invalid_link_refresh_keeps_previous_match_stale(make_service):
    source = FakeSource()
    service = make_service(source)
    original = finished(service)
    source.rows.append({**catalog_row(""), "error_code": "invalid_link"})
    result = finished(service, force=True)
    assert result["status"] == "unavailable"
    assert result["error_code"] == "invalid_link"
    assert result["stale"] is True
    assert result["matches"] == original["matches"]


def test_parallel_first_requests_share_one_service_and_shutdown_is_lazy(monkeypatch, tmp_path):
    from core import config
    module.stop_report_link_service()
    instances = []
    original = module.RoutedReportLinkService

    def create(*args, **kwargs):
        time.sleep(0.01)
        instance = original(*args, **kwargs)
        instances.append(instance)
        return instance

    monkeypatch.setattr(module, "RoutedReportLinkService", create)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setenv("PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_LINKS_ENABLED", "false")
    try:
        module.stop_report_link_service()
        assert instances == []
        with ThreadPoolExecutor(max_workers=8) as pool:
            services = list(pool.map(lambda _: module.get_report_link_service(), range(8)))
        assert len(instances) == 1
        assert all(service is instances[0] for service in services)
        module.stop_report_link_service()
        assert instances[0]._closed
        assert module.get_report_link_service() is not instances[0]
    finally:
        module.stop_report_link_service()
