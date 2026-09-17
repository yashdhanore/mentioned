from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateSavedSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(..., min_length=1, max_length=2048)


class SourceItemResponse(BaseModel):
    id: str
    book_id: str | None = None
    title: str
    author: str | None = None
    category: str
    confidence: float | None = None
    google_books_url: str | None = None
    cover_image_url: str | None = None
    place_id: str | None = None
    formatted_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    maps_url: str | None = None
    position: int


class SavedSourceResponse(BaseModel):
    id: str
    source_id: str
    source_key: str
    status: str
    source_url: str
    thumbnail_url: str | None = None
    source_creator_handle: str | None = None
    error_message: str | None = None
    skip_reason: str | None = None
    created_at: datetime
    items: list[SourceItemResponse] = Field(default_factory=list)


class DeleteSavedSourceResponse(BaseModel):
    id: str
    deleted: bool = True
