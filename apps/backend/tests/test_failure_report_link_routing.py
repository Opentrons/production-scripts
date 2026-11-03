from __future__ import annotations

import copy

import pytest

from modules.test_failures.report_links import ReportLinkService, RoutedReportLinkService, report_channels
from test_failure_report_links import FakeSource, REPORT, URL, OTHER_URL, catalog_row, finished


@pytest.mark.parametrize("product,sn,channels", [
    ("P50S", "P50SV3-001", ("1ch",)), ("P1000S", "P1KSV3-001", ("1ch",)),
    ("p50_single_flex", "P50SV3-001", ("1ch",)), ("flex_1channel_1000", "P1000S-001", ("1ch",)),
    ("", "P1000S-001", ("1ch",)), ("Unknown", "P1KS-001", ("1ch",)),
    ("P50M", "P50MV3-001", ("8ch",)), ("P1000M", "P1KMV3-001", ("8ch",)),
    ("flex_8channel_1000", "other-serial", ("8ch",)), ("", "P1000M-001", ("8ch",)),
    ("P50S", "P50MV3-001", ("1ch", "8ch")), ("P1000M", "P1KSV3-001", ("1ch", "8ch")),
    ("Unknown", "other-serial", ("1ch", "8ch")), ("flex_96channel_1000", "P1KH-001", ("1ch", "8ch")),
])
def test_routes_using_model_and_serial_without_changing_exact_identity(product, sn, channels):
    assert report_channels({"product": product, "sn": sn}) == channels


@pytest.fixture
def routed(tmp_path):
    instances = []

    def make(sources, **kwargs):
        created = []

        def create(channel):
            created.append(channel)
            source = sources[channel]
            if isinstance(source, Exception):
                raise source
            source.cache_namespace = f"synthetic-{channel}"
            return ReportLinkService(tmp_path / "links.sqlite3", source=source)

        service = RoutedReportLinkService(tmp_path / "links.sqlite3", service_factory=create, **kwargs)
        instances.append(service)
        return service, created

    yield make
    for service in instances:
        service.close(wait=True)


def source_for(report, url=URL):
    return FakeSource([catalog_row(url, sn=report["sn"])], {url: report})


def test_single_channel_does_not_query_multi_channel_and_retains_source_position(routed):
    report = {**REPORT, "sn": "P50SV3-001", "product": "P50S", "revision": "keep"}
    original = copy.deepcopy(report)
    single = source_for(report)
    service, created = routed({"1ch": single, "8ch": RuntimeError("must not open 8ch")})
    result = finished(service, report)
    assert result["status"] == "matched"
    assert created == ["1ch"]
    assert result["matches"][0]["source_url"] == single.rows[0]["source_url"]
    assert report == original


def test_single_channel_failure_does_not_block_multi_channel(routed):
    single_report = {**REPORT, "sn": "P50S-001", "product": "P50S"}
    single = source_for(single_report)
    single.catalog_error = PermissionError("denied")
    multi = source_for(REPORT)
    service, _ = routed({"1ch": single, "8ch": multi})
    assert finished(service, single_report)["status"] == "unavailable"
    assert finished(service, REPORT)["status"] == "matched"
    assert multi.catalog_calls == 1


def test_invalid_single_channel_configuration_never_falls_back_to_multi_channel(routed):
    service, created = routed({"1ch": ValueError("invalid gid"), "8ch": source_for(REPORT)})
    result = service.lookup({**REPORT, "sn": "P50S-001"})
    assert result["status"] == "unavailable"
    assert result["error_code"] == "configuration_error"
    assert created == ["1ch"]
    assert finished(service, REPORT)["status"] == "matched"


@pytest.mark.parametrize("second_url,status,count", [(URL, "matched", 1), (OTHER_URL, "ambiguous", 2)])
def test_unknown_channel_checks_both_and_deduplicates_urls(routed, second_url, status, count):
    report = {**REPORT, "sn": "UNCLASSIFIED-SN", "product": "Unknown"}
    service, created = routed({"1ch": source_for(report), "8ch": source_for(report, second_url)})
    result = finished(service, report)
    assert result["status"] == status
    assert len(result["matches"]) == count
    assert created == ["1ch", "8ch"]
    assert result["checked_at"]


def test_conflicting_model_and_serial_checks_both_sources(routed):
    report = {**REPORT, "product": "P50S"}
    service, created = routed({"1ch": FakeSource([]), "8ch": source_for(report)})
    assert finished(service, report)["status"] == "matched"
    assert created == ["1ch", "8ch"]


def test_dual_source_incomplete_result_never_claims_unique_or_negative_and_preserves_previous(routed):
    report = {**REPORT, "sn": "UNCLASSIFIED-SN"}
    single, multi = FakeSource([]), source_for(report)
    service, _ = routed({"1ch": single, "8ch": multi})
    previous = finished(service, report)
    assert previous["status"] == "matched"
    single.catalog_error = PermissionError("denied")
    result = finished(service, report, force=True)
    assert result["status"] == "unavailable"
    assert result["matches"] == previous["matches"]
    assert result["stale"]


def test_unknown_channel_running_takes_priority_over_failure(routed):
    import threading
    report = {**REPORT, "sn": "UNCLASSIFIED-SN"}
    release, started = threading.Event(), threading.Event()
    single = source_for(report)
    original = single.read_catalog

    def slow():
        started.set()
        release.wait(2)
        return original()

    single.read_catalog = slow
    service, _ = routed({"1ch": single, "8ch": ValueError("bad configuration")})
    try:
        assert service.lookup(report)["status"] == "running"
        assert started.wait(1)
        assert service.lookup(report)["status"] == "running"
    finally:
        release.set()
    result = finished(service, report)
    assert result["status"] == "unavailable"
    assert result["matches"] == []


@pytest.mark.parametrize("enabled,report,status", [(False, REPORT, "disabled"), (True, {"sn": "P50S"}, "missing_identity")])
def test_disabled_or_missing_identity_does_not_create_sources(routed, enabled, report, status):
    service, created = routed({}, enabled=enabled)
    assert service.lookup(report)["status"] == status
    assert created == []


def test_closing_router_prevents_new_workers(routed):
    service, created = routed({"8ch": source_for(REPORT)})
    finished(service, REPORT)
    child = service._children["8ch"]
    service.close(wait=True)
    assert child._closed
    assert service.lookup({**REPORT, "sn": "P50S-001"})["error_code"] == "closed"
    assert created == ["8ch"]
