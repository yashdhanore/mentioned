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
    thumbnail_url: str | None = None
    source_creator_handle: str | None = None
    error: str | None = None
    skip_reason: str | None = None
