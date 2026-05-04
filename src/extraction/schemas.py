from __future__ import annotations

from dataclasses import dataclass, field


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
class BookEnrichment:
    canonical_title: str | None = None
    canonical_author: str | None = None
    google_books_url: str | None = None
    cover_image_url: str | None = None
    confidence_boost: float = 0.0
