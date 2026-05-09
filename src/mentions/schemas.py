from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MentionResponse(BaseModel):
    id: str
    book_id: Optional[str] = None
    title: str
    author: Optional[str] = None
    category: str
    confidence: Optional[float] = None
    google_books_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    source_url: str
    created_at: datetime


class MentionListResponse(BaseModel):
    items: list[MentionResponse]
    next_cursor: Optional[str] = None


class UpdateMentionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    author: Optional[str] = Field(default=None, max_length=500)
    category: Optional[str] = Field(default=None, pattern=r"^(book|product|place)$")


class DeleteMentionResponse(BaseModel):
    id: str
    deleted: bool = True
