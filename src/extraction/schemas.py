from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedMention:
    title: str
    author: str | None = None
    category: str = "book"
    confidence: float = 0.5


@dataclass
class PipelineResult:
    mentions: list[ExtractedMention] = field(default_factory=list)
    error: str | None = None


@dataclass
class GoogleBook:
    provider_volume_id: str
    title: str
    provider_etag: str | None = None
    provider_self_link: str | None = None
    subtitle: str | None = None
    authors: list[str] = field(default_factory=list)
    publisher: str | None = None
    published_date: str | None = None
    description: str | None = None
    industry_identifiers: list[dict[str, Any]] = field(default_factory=list)
    page_count: int | None = None
    print_type: str | None = None
    language: str | None = None
    main_category: str | None = None
    categories: list[str] = field(default_factory=list)
    image_links: dict[str, str] = field(default_factory=dict)
    cover_image_url: str | None = None
    preview_link: str | None = None
    info_link: str | None = None
    canonical_volume_link: str | None = None
    sale_info: dict[str, Any] | None = None
    access_info: dict[str, Any] | None = None
    raw_provider_payload: dict[str, Any] | None = None


@dataclass
class BookEnrichment:
    canonical_title: str | None = None
    canonical_author: str | None = None
    google_books_url: str | None = None
    cover_image_url: str | None = None
    confidence_boost: float = 0.0
