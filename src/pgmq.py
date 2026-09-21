from __future__ import annotations

import json

from sqlmodel import Session

# Shared by src/sources/queue.py and src/push/queue.py. Each queue's read_with_poll
# vs read SQL, batch sizing, and message shape differ enough (and are read by only
# one caller each) that a single generic queue class would be a bigger abstraction
# than the duplication it removes; only this session/payload plumbing is identical.


def is_postgres_session(session: Session) -> bool:
    bind = session.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def parse_message_payload(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("queue message must be a JSON object")
