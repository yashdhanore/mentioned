from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.pgmq import is_postgres_session, parse_message_payload


def _session(dialect_name: str | None):
    if dialect_name is None:
        return SimpleNamespace(get_bind=lambda: None)
    bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect_name))
    return SimpleNamespace(get_bind=lambda: bind)


def test_is_postgres_session_true_for_postgresql():
    assert is_postgres_session(_session("postgresql")) is True


def test_is_postgres_session_false_for_sqlite():
    assert is_postgres_session(_session("sqlite")) is False


def test_is_postgres_session_false_for_no_bind():
    assert is_postgres_session(_session(None)) is False


def test_parse_message_payload_accepts_dict():
    assert parse_message_payload({"v": 1}) == {"v": 1}


def test_parse_message_payload_parses_json_string():
    assert parse_message_payload('{"v": 1}') == {"v": 1}


def test_parse_message_payload_rejects_non_object_json():
    with pytest.raises(ValueError, match="JSON object"):
        parse_message_payload("[1, 2, 3]")


def test_parse_message_payload_rejects_malformed_json():
    with pytest.raises(json.JSONDecodeError):
        parse_message_payload("not json")


def test_parse_message_payload_rejects_other_types():
    with pytest.raises(ValueError, match="JSON object"):
        parse_message_payload(123)
