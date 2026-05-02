from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class StageOutcome:
    stage: str
    success: bool
    duration_ms: int
    payload: dict[str, Any] | None = None
    error_text: str | None = None


@dataclass(slots=True)
class ArtifactRecord:
    kind: str
    path: str
    metadata: dict[str, Any] | None = None


@dataclass(slots=True)
class ExtractedBookCandidate:
    title: str
    author: str | None
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict)
    canonical_source: str | None = None
    canonical_id: str | None = None
    canonical_title: str | None = None
    canonical_author: str | None = None


@dataclass(slots=True)
class ExtractedMentionCandidate:
    label: str
    author_or_creator: str | None
    category: str
    confidence: float | None
    evidence: dict[str, Any] = field(default_factory=dict)
    description: str | None = None
    evidence_text: str | None = None


@dataclass(slots=True)
class TextExtractionResult:
    caption_text: str | None
    spoken_text: str | None
    visual_text: str | None
    image_text: str | None
    merged_text: str
    warnings: list[str] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PipelineResult:
    source_kind: str
    final_status: str
    error_code: str | None
    error_message: str | None
    stage_runs: list[StageOutcome]
    artifacts: list[ArtifactRecord]
    text_result: TextExtractionResult
    candidate_mentions: list[ExtractedMentionCandidate] = field(default_factory=list)
