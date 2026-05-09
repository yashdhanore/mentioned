from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, SQLModel


class JobStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    owner_id: str = Field(nullable=False, index=True)
    source_url: str = Field(nullable=False)
    status: str = Field(default=JobStatus.PENDING, nullable=False)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    finished_at: Optional[datetime] = Field(default=None)
    locked_by: Optional[str] = Field(default=None)
    locked_at: Optional[datetime] = Field(default=None)
    heartbeat_at: Optional[datetime] = Field(default=None)
