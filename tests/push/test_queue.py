from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from src.push.queue import PushNotificationMessage, read_push_notification_messages


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
        if "pgmq.read" in sql:
            return _MappingsResult(self._rows)
        if "pgmq.archive" in sql:
            self.archived.append(params["msg_id"])
            return _ScalarResult(True)
        raise AssertionError(f"unexpected statement: {sql}")


def _row(msg_id: int, read_ct: int, message) -> dict:
    return {"msg_id": msg_id, "read_ct": read_ct, "message": message}


def _read(session) -> list[PushNotificationMessage]:
    return read_push_notification_messages(session, visibility_timeout_seconds=1800)


def test_read_push_notification_messages_returns_valid_messages():
    source_id = uuid4()
    session = FakePostgresSession([_row(1, 1, json.dumps({"v": 1, "source_id": str(source_id)}))])

    messages = _read(session)

    assert messages == [PushNotificationMessage(msg_id=1, source_id=source_id, read_count=1)]
    assert session.archived == []


def test_read_push_notification_messages_archives_unsupported_version_without_raising():
    source_id = uuid4()
    session = FakePostgresSession([_row(2, 1, json.dumps({"v": 2, "source_id": str(source_id)}))])

    messages = _read(session)

    assert messages == []
    assert session.archived == [2]


def test_read_push_notification_messages_archives_malformed_body_without_raising():
    session = FakePostgresSession([_row(3, 1, "not json")])

    messages = _read(session)

    assert messages == []
    assert session.archived == [3]
