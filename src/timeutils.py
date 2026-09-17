"""Shared time helpers.

SQLModel timestamp columns in this codebase (see `src/*/models.py`) declare plain
`datetime` fields with no `timezone=True` on the Python side, so application code
must keep producing naive UTC datetimes for comparisons and writes to stay
consistent with existing rows and with values read back from the database.
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current time as a naive UTC datetime.

    Equivalent to the deprecated `datetime.utcnow()`, but built from the
    timezone-aware `datetime.now(UTC)` and then stripped of tzinfo so it stays a
    drop-in replacement for the naive datetimes this codebase already uses.
    """
    return datetime.now(UTC).replace(tzinfo=None)
