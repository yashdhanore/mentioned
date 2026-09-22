"""Shared time helpers.

Every live datetime column in this schema is `timestamptz` (confirmed across all
Alembic migrations), and sqlmodel>=0.0.45 maps `datetime` model fields to its
`UTCDateTime` type, which requires aware datetimes for writes and returns aware
UTC datetimes on read, including on SQLite. Application code must produce aware
UTC datetimes for comparisons and writes to match.
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)
