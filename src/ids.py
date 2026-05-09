from __future__ import annotations

from uuid import UUID


def parse_uuid(value: str | UUID) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(value)
