from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from extractor.types import ArtifactRecord, StageOutcome


SCHEMA_VERSION = "visual_reconstruction.v1"

SourceSurface = Literal["frame", "post_image"]
VisualRole = Literal["full", "overlay", "object"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VisibleTextBlock(StrictModel):
    text: str
    kind: Literal["overlay", "title", "author", "subtitle", "object_text", "ui", "background", "unknown"]
    source_surface: SourceSurface
    source_image_ids: list[str]
    source_crop_ids: list[str]
    confidence: float = Field(..., ge=0.0, le=1.0)
    include_in_merged_text: bool
    ignored_reason: str | None


class CandidateMention(StrictModel):
    label: str
    author_or_creator: str | None
    category: Literal["book", "product", "newsletter", "person", "unknown"]
    evidence_basis: Literal["direct_visible_text", "partial_cover_inference", "caption_context", "mixed"]
    creator_supplied_context: str | None
    visible_evidence: str
    normalization_notes: str | None
    source_image_ids: list[str]
    source_crop_ids: list[str]
    confidence: float = Field(..., ge=0.0, le=1.0)


class VisualReconstruction(StrictModel):
    schema_version: Literal["visual_reconstruction.v1"]
    cleaned_frame_text: str
    cleaned_post_image_text: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    visible_text_blocks: list[VisibleTextBlock]
    candidate_mentions: list[CandidateMention]
    ignored_text_summary: str | None
    uncertainty_notes: list[str]


@dataclass(slots=True)
class VisualImage:
    id: str
    role: VisualRole
    path: Path
    source_surface: SourceSurface
    source_image_id: str
    frame_index: int | None
    timestamp_seconds: float | None
    bbox_normalized: tuple[float, float, float, float]
    width: int
    height: int
    sha256: str

    def manifest_record(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "path": str(self.path),
            "source_surface": self.source_surface,
            "source_image_id": self.source_image_id,
            "frame_index": self.frame_index,
            "timestamp_seconds": self.timestamp_seconds,
            "bbox_normalized": list(self.bbox_normalized),
            "width": self.width,
            "height": self.height,
            "sha256": self.sha256,
        }


@dataclass(slots=True)
class VisualInputBundle:
    selected_images: list[VisualImage]
    crops: list[VisualImage]
    llm_images: list[VisualImage]
    image_selection_manifest: dict[str, Any]


@dataclass(slots=True)
class OpenAIVisualResponse:
    reconstruction: VisualReconstruction
    raw_response: dict[str, Any]
    usage: dict[str, Any] | None


@dataclass(slots=True)
class VisualExtractionResult:
    visual_text: str | None
    image_text: str | None
    warnings: list[str] = field(default_factory=list)
    nonfatal_errors: list[str] = field(default_factory=list)
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    stage_runs: list[StageOutcome] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)
