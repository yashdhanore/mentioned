from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from src.timeutils import utc_now


class JobStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class JobEventType(StrEnum):
    JOB_DONE = "job_done"
    JOB_FAILED = "job_failed"


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(nullable=False, index=True)
    source_url: str = Field(nullable=False)
    thumbnail_url: str | None = Field(default=None)
    source_creator_handle: str | None = Field(default=None)
    status: str = Field(default=JobStatus.PENDING, nullable=False)
    error_message: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    finished_at: datetime | None = Field(default=None)
    locked_by: str | None = Field(default=None)
    locked_at: datetime | None = Field(default=None)
    heartbeat_at: datetime | None = Field(default=None)


class JobEvent(SQLModel, table=True):
    __tablename__ = "job_events"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(nullable=False, index=True)
    job_id: UUID = Field(
        nullable=False,
        foreign_key="jobs.id",
        ondelete="CASCADE",
        unique=True,
        index=True,
    )
    event_type: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
