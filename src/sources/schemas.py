from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CreateSavedSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(..., min_length=1, max_length=2048)


class SourceItemResponse(BaseModel):
    id: str
    book_id: Optional[str] = None
    title: str
    author: Optional[str] = None
    category: str
    confidence: Optional[float] = None
    google_books_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    position: int


class SavedSourceResponse(BaseModel):
    id: str
    source_id: str
    source_key: str
    status: str
    source_url: str
    thumbnail_url: Optional[str] = None
    source_creator_handle: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    items: list[SourceItemResponse] = []


class DeleteSavedSourceResponse(BaseModel):
    id: str
    deleted: bool = True
