from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from src.books.models import Book  # noqa: F401 - register foreign key target
from src.places.models import Place  # noqa: F401 - register foreign key target
from src.timeutils import utc_now


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
    creator_handle: str | None = Field(default=None)
    thumbnail_url: str | None = Field(default=None)
    error_message: str | None = Field(default=None)
    skip_reason: str | None = Field(default=None)
    processing_started_at: datetime | None = Field(default=None)
    # sources has never had a heartbeat_at column; that column only ever existed on
    # the legacy jobs table (migration 0003), which 0017 dropped. Stale-source
    # recovery correctly keys staleness on processing_started_at alone
    # (recover_stale_sources); there is nothing to refresh or unmap here.
    processed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class SourceItem(SQLModel, table=True):
    __tablename__ = "source_items"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_id: UUID = Field(nullable=False, foreign_key="sources.id", index=True)
    book_id: UUID | None = Field(default=None, foreign_key="books.id", index=True)
    category: str = Field(default="book", nullable=False, index=True)
    title: str = Field(nullable=False)
    author: str | None = Field(default=None)
    confidence: float | None = Field(default=None)
    google_books_url: str | None = Field(default=None)
    cover_image_url: str | None = Field(default=None)
    place_id: UUID | None = Field(default=None, foreign_key="places.id", index=True)
    formatted_address: str | None = Field(default=None)
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)
    maps_url: str | None = Field(default=None)
    position: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class SavedSource(SQLModel, table=True):
    __tablename__ = "saved_sources"
    __table_args__ = (
        UniqueConstraint("owner_id", "source_id", name="saved_sources_owner_source_key"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(nullable=False, index=True)
    source_id: UUID = Field(nullable=False, foreign_key="sources.id", index=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    last_retry_at: datetime | None = Field(default=None)
    retry_burst_started_at: datetime | None = Field(default=None)
    retry_burst_count: int = Field(default=0, nullable=False)
    retry_daily_started_at: datetime | None = Field(default=None)
    retry_daily_count: int = Field(default=0, nullable=False)
