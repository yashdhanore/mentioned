from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Job(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    source_url: str
    source_kind: str = Field(default="unknown", index=True)
    status: str = Field(default="queued", index=True)
    current_stage: str | None = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Artifact(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    job_id: str = Field(foreign_key="job.id", index=True)
    kind: str = Field(index=True)
    path: str
    metadata_json: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class StageRun(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    job_id: str = Field(foreign_key="job.id", index=True)
    stage: str = Field(index=True)
    success: bool
    duration_ms: int
    payload_json: str | None = None
    error_text: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class TextResult(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    job_id: str = Field(foreign_key="job.id", index=True, unique=True)
    caption_text: str | None = None
    spoken_text: str | None = None
    visual_text: str | None = None
    image_text: str | None = None
    merged_text: str
    warnings_json: str | None = None
    debug_json: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class BookCandidate(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    job_id: str = Field(foreign_key="job.id", index=True)
    title: str
    author: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_json: str | None = None
    canonical_source: str | None = None
    canonical_id: str | None = None
    canonical_title: str | None = None
    canonical_author: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
