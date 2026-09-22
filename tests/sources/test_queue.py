from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from src.sources.queue import SourceExtractionMessage, read_source_extraction_messages


class _MappingsResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class FakePostgresSession:
    def __init__(self, rows):
        self._rows = rows
        self.archived: list[int] = []

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "pgmq.read_with_poll" in sql:
            return _MappingsResult(self._rows)
        if "pgmq.archive" in sql:
            self.archived.append(params["msg_id"])
            return _ScalarResult(True)
        raise AssertionError(f"unexpected statement: {sql}")


class FakeSqliteSession:
    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))


def _row(msg_id: int, read_ct: int, message) -> dict:
    return {"msg_id": msg_id, "read_ct": read_ct, "message": message}


def _read(session) -> list[SourceExtractionMessage]:
    return read_source_extraction_messages(
        session, visibility_timeout_seconds=1800, max_poll_seconds=5, poll_interval_ms=100
    )


def test_read_source_extraction_messages_returns_valid_messages():
    source_id = uuid4()
    session = FakePostgresSession([_row(1, 1, json.dumps({"v": 1, "source_id": str(source_id)}))])

    messages = _read(session)

    assert messages == [SourceExtractionMessage(msg_id=1, source_id=source_id, read_count=1)]
    assert session.archived == []


def test_read_source_extraction_messages_archives_unsupported_version_without_raising():
    source_id = uuid4()
    session = FakePostgresSession([_row(2, 1, json.dumps({"v": 2, "source_id": str(source_id)}))])

    messages = _read(session)

    assert messages == []
    assert session.archived == [2]


def test_read_source_extraction_messages_archives_malformed_body_without_raising():
    session = FakePostgresSession([_row(3, 1, "not json")])

    messages = _read(session)

    assert messages == []
    assert session.archived == [3]


def test_read_source_extraction_messages_archives_missing_source_id_without_raising():
    session = FakePostgresSession([_row(4, 1, json.dumps({"v": 1}))])

    messages = _read(session)

    assert messages == []
    assert session.archived == [4]


def test_read_source_extraction_messages_skips_a_good_message_after_a_bad_one():
    source_id = uuid4()
    session = FakePostgresSession(
        [
            _row(5, 1, "not json"),
            _row(6, 1, json.dumps({"v": 1, "source_id": str(source_id)})),
        ]
    )

    messages = _read(session)

    assert messages == [SourceExtractionMessage(msg_id=6, source_id=source_id, read_count=1)]
    assert session.archived == [5]


def test_read_source_extraction_messages_returns_empty_on_sqlite():
    messages = _read(FakeSqliteSession())

    assert messages == []
