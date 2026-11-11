from __future__ import annotations

import runpy
from types import SimpleNamespace

import pytest

import core.config as setting
import core.database as database_module
from core import persistence


class FakeMongoClient:
    attempts = 0

    def __init__(self, *_args, **_kwargs) -> None:
        type(self).attempts += 1
        self.admin = self
        self.closed = False

    def command(self, command: str):
        assert command == "ping"
        if type(self).attempts < 2:
            raise TimeoutError("temporary timeout")
        return {"ok": 1}

    def close(self) -> None:
        self.closed = True

    def __getitem__(self, name: str):
        return SimpleNamespace(name=name)


def test_mongodb_connect_retries_transient_failure(monkeypatch) -> None:
    FakeMongoClient.attempts = 0
    monkeypatch.setattr(database_module, "MongoClient", FakeMongoClient)
    monkeypatch.setattr(database_module, "MONGO_CONNECT_ATTEMPTS", 3)
    monkeypatch.setattr(database_module, "MONGO_CONNECT_RETRY_DELAY_MS", 0)
    monkeypatch.setattr(setting, "IS_DEV_ENV", False)
    database = database_module.MongoDB(uri="mongodb://example.test:27017")

    assert database.connect() is True
    assert FakeMongoClient.attempts == 2
    assert database.get_database("ProductionsMessage").name == "ProductionsMessage"


@pytest.mark.parametrize("name", ["ProductionsMessage", "ProductionsData2026", "TestPlan", "CustomQA"])
@pytest.mark.parametrize("is_dev", [False, True])
def test_all_mongodb_database_names_are_isolated(monkeypatch, name, is_dev) -> None:
    monkeypatch.setattr(setting, "IS_DEV_ENV", is_dev)
    database = database_module.MongoDB()
    database.client = FakeMongoClient()

    expected = f"{name}_dev" if is_dev else name
    assert database.get_database(name).name == expected
    assert database.get_database(expected).name == expected


def test_business_persistence_uses_isolated_database_even_with_production_override(monkeypatch) -> None:
    monkeypatch.setattr(setting, "IS_DEV_ENV", True)
    monkeypatch.setattr(setting, "MESSAGE_COLLECTION", "ProductionsMessage")
    monkeypatch.setattr(database_module.mongodb, "client", FakeMongoClient())

    assert persistence.get_message_database().name == "ProductionsMessage_dev"


@pytest.mark.parametrize("run_env", ["dev", "local", "development", "server", "production"])
def test_runtime_profile_resolves_configured_and_default_databases(monkeypatch, run_env) -> None:
    monkeypatch.setenv("PRODUCTION_PLATFORM_RUN_ENV", run_env)
    monkeypatch.setenv("PRODUCTION_PLATFORM_MESSAGE_DATABASE", "CustomMessage")
    config = runpy.run_path(setting.__file__)

    suffix = "_dev" if run_env in {"dev", "local", "development"} else ""
    assert config["MESSAGE_COLLECTION"] == f"CustomMessage{suffix}"
    assert config["DATA_DB_NAME"] == f"ProductionsData2026{suffix}"
