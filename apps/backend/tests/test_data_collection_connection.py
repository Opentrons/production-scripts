from __future__ import annotations

import pytest

from modules.data_analysis import data as data_service


@pytest.fixture
def unavailable_mongodb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_service.mongodb, "client", None)
    monkeypatch.setattr(data_service.mongodb, "connect", lambda: False)


def test_collection_endpoints_report_database_connection_failure(unavailable_mongodb: None) -> None:
    expected_error = data_service.TEST_DATA_DATABASE_ERROR

    assert data_service.get_collections()["error"] == expected_error
    assert data_service.get_collection_filter_options(data_service.ALL_COLLECTIONS_KEY)["error"] == expected_error
    assert data_service.get_collection_data(data_service.ALL_COLLECTIONS_KEY)["error"] == expected_error
    assert data_service.get_test_data()["error"] == expected_error
