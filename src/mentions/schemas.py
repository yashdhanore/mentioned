from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MentionResponse(BaseModel):
    id: str
    book_id: str | None = None
    title: str
    author: str | None = None
    category: str
    confidence: float | None = None
    google_books_url: str | None = None
    cover_image_url: str | None = None
    source_url: str
    created_at: datetime


class MentionListResponse(BaseModel):
    items: list[MentionResponse]
    next_cursor: str | None = None


class UpdateMentionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=500)
    author: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, pattern=r"^(book|product|place)$")


class DeleteMentionResponse(BaseModel):
    id: str
    deleted: bool = True
