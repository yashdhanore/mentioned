from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


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
    book_id: Optional[str] = None
    title: str
    author: Optional[str] = None
    category: str
    confidence: Optional[float] = None
    google_books_url: Optional[str] = None
    cover_image_url: Optional[str] = None


class JobResponse(BaseModel):
    job_id: str
    status: str
    source_url: str
    thumbnail_url: Optional[str] = None
    source_creator_handle: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None
    mentions: list[MentionInJob] = []


class JobListItem(BaseModel):
    job_id: str
    status: str
    source_url: str
    thumbnail_url: Optional[str] = None
    source_creator_handle: Optional[str] = None
    created_at: datetime
