from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, SQLModel


class MentionCategory(StrEnum):
    BOOK = "book"
    PRODUCT = "product"
    PLACE = "place"


class Mention(SQLModel, table=True):
    __tablename__ = "mentions"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    owner_id: str = Field(nullable=False, index=True)
    job_id: str = Field(nullable=False, foreign_key="jobs.id", index=True)
    title: str = Field(nullable=False)
    author: Optional[str] = Field(default=None)
    category: str = Field(default=MentionCategory.BOOK, nullable=False)
    confidence: Optional[float] = Field(default=None)
    google_books_url: Optional[str] = Field(default=None)
    cover_image_url: Optional[str] = Field(default=None)
    source_url: str = Field(nullable=False)
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
