from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(..., min_length=1, max_length=2048)


class JobCreatedResponse(BaseModel):
    job_id: str
    status: str


class DeleteJobResponse(BaseModel):
    job_id: str
    deleted: bool = True


class MentionInJob(BaseModel):
    id: str
    book_id: str | None = None
    title: str
    author: str | None = None
    category: str
    confidence: float | None = None
    google_books_url: str | None = None
    cover_image_url: str | None = None


class JobResponse(BaseModel):
    job_id: str
    status: str
    source_url: str
    thumbnail_url: str | None = None
    source_creator_handle: str | None = None
    error_message: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    mentions: list[MentionInJob] = []


class JobListItem(BaseModel):
    job_id: str
    status: str
    source_url: str
    thumbnail_url: str | None = None
    source_creator_handle: str | None = None
    created_at: datetime
