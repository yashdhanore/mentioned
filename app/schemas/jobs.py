from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateJobRequest(StrictModel):
    url: str = Field(min_length=1, max_length=2048)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)


class JobLinks(BaseModel):
    self: str
    result: str


class JobResponse(BaseModel):
    job_id: str
    source_url: str
    source_kind: str
    status: str
    current_stage: str | None
    progress: float
    attempt_count: int
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    links: JobLinks


class JobListResponse(BaseModel):
    items: list[JobResponse]
    next_cursor: str | None
