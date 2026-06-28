from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from src.books.models import Book  # noqa: F401 - register foreign key target
from src.places.models import Place  # noqa: F401 - register foreign key target


class SourceStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Source(SQLModel, table=True):
    __tablename__ = "sources"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_key: str = Field(nullable=False, unique=True, index=True)
    platform: str = Field(nullable=False, index=True)
    source_type: str = Field(nullable=False)
    external_id: str = Field(nullable=False)
    canonical_url: str = Field(nullable=False)
    status: str = Field(default=SourceStatus.PENDING, nullable=False, index=True)
    creator_handle: Optional[str] = Field(default=None)
    thumbnail_url: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    skip_reason: Optional[str] = Field(default=None)
    processing_started_at: Optional[datetime] = Field(default=None)
    processed_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class SourceItem(SQLModel, table=True):
    __tablename__ = "source_items"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_id: UUID = Field(nullable=False, foreign_key="sources.id", index=True)
    book_id: Optional[UUID] = Field(default=None, foreign_key="books.id", index=True)
    category: str = Field(default="book", nullable=False, index=True)
    title: str = Field(nullable=False)
    author: Optional[str] = Field(default=None)
    confidence: Optional[float] = Field(default=None)
    google_books_url: Optional[str] = Field(default=None)
    cover_image_url: Optional[str] = Field(default=None)
    place_id: Optional[UUID] = Field(default=None, foreign_key="places.id", index=True)
    formatted_address: Optional[str] = Field(default=None)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    maps_url: Optional[str] = Field(default=None)
    position: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class SavedSource(SQLModel, table=True):
    __tablename__ = "saved_sources"
    __table_args__ = (
        UniqueConstraint("owner_id", "source_id", name="saved_sources_owner_source_key"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(nullable=False, index=True)
    source_id: UUID = Field(nullable=False, foreign_key="sources.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    last_retry_at: Optional[datetime] = Field(default=None)
    retry_burst_started_at: Optional[datetime] = Field(default=None)
    retry_burst_count: int = Field(default=0, nullable=False)
    retry_daily_started_at: Optional[datetime] = Field(default=None)
    retry_daily_count: int = Field(default=0, nullable=False)
