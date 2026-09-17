from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from src.books.models import Book  # noqa: F401 - register foreign key target
from src.timeutils import utc_now


class MentionCategory(StrEnum):
    BOOK = "book"
    PRODUCT = "product"
    PLACE = "place"


class Mention(SQLModel, table=True):
    __tablename__ = "mentions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(nullable=False, index=True)
    job_id: UUID = Field(nullable=False, foreign_key="jobs.id", index=True)
    book_id: UUID | None = Field(default=None, foreign_key="books.id", index=True)
    title: str = Field(nullable=False)
    author: str | None = Field(default=None)
    category: str = Field(default=MentionCategory.BOOK, nullable=False)
    confidence: float | None = Field(default=None)
    google_books_url: str | None = Field(default=None)
    cover_image_url: str | None = Field(default=None)
    source_url: str = Field(nullable=False)
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)
