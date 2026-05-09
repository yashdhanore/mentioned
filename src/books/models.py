from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Index
from sqlmodel import Field, SQLModel


class Book(SQLModel, table=True):
    __tablename__ = "books"
    __table_args__ = (
        Index(
            "books_provider_volume_unique_idx",
            "provider",
            "provider_volume_id",
            unique=True,
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    provider: str = Field(default="google_books", nullable=False, index=True)
    provider_volume_id: str = Field(nullable=False, index=True)
    provider_etag: str | None = Field(default=None)
    provider_self_link: str | None = Field(default=None)

    title: str = Field(nullable=False)
    subtitle: str | None = Field(default=None)
    authors: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))

    publisher: str | None = Field(default=None)
    published_date: str | None = Field(default=None)
    description: str | None = Field(default=None)

    industry_identifiers: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    isbn_10: str | None = Field(default=None, index=True)
    isbn_13: str | None = Field(default=None, index=True)

    page_count: int | None = Field(default=None)
    print_type: str | None = Field(default=None)
    language: str | None = Field(default=None)
    main_category: str | None = Field(default=None)
    categories: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))

    image_links: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    cover_image_url: str | None = Field(default=None)
    preview_link: str | None = Field(default=None)
    info_link: str | None = Field(default=None)
    canonical_volume_link: str | None = Field(default=None)

    sale_info: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    access_info: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    raw_provider_payload: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
