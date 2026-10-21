from __future__ import annotations

from types import SimpleNamespace

import core.database as database_module


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
    database = database_module.MongoDB(uri="mongodb://example.test:27017")

    assert database.connect() is True
    assert FakeMongoClient.attempts == 2
    assert database.get_database("ProductionsMessage").name == "ProductionsMessage"
