from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None


class ArtifactResponse(BaseModel):
    artifact_id: str
    kind: str
    storage_backend: str
    media_type: str | None
    byte_size: int | None
    metadata: JsonValue = None
    created_at: datetime


class StageRunResponse(BaseModel):
    stage: str
    success: bool
    duration_ms: int
    payload: JsonValue = None
    error_code: str | None = None
    error_text: str | None = None
    created_at: datetime


class TextResultResponse(BaseModel):
    caption_text: str | None
    spoken_text: str | None
    visual_text: str | None
    image_text: str | None
    merged_text: str
    warnings: list[str]
    debug: JsonValue = None


class JobResultResponse(BaseModel):
    job_id: str
    source_url: str
    source_kind: str
    status: str
    current_stage: str | None
    progress: float
    text: TextResultResponse
    stage_runs: list[StageRunResponse]
    artifacts: list[ArtifactResponse]
