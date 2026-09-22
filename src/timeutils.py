"""Every datetime column is `timestamptz`, and sqlmodel maps `datetime` fields to
`UTCDateTime`, which rejects naive datetimes on write and returns aware UTC ones on
read, SQLite included. So application code must only produce aware UTC datetimes.
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)
