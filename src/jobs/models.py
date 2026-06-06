from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


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
    thumbnail_url: Optional[str] = Field(default=None)
    source_creator_handle: Optional[str] = Field(default=None)
    status: str = Field(default=JobStatus.PENDING, nullable=False)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    finished_at: Optional[datetime] = Field(default=None)
    locked_by: Optional[str] = Field(default=None)
    locked_at: Optional[datetime] = Field(default=None)
    heartbeat_at: Optional[datetime] = Field(default=None)


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
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
