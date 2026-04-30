from datetime import datetime

from pydantic import BaseModel


class ArtifactResponse(BaseModel):
    kind: str
    path: str
    metadata: dict | list | str | int | float | bool | None = None
    created_at: datetime


class StageRunResponse(BaseModel):
    stage: str
    success: bool
    duration_ms: int
    payload: dict | list | str | int | float | bool | None = None
    error_text: str | None
    created_at: datetime


class TextResultResponse(BaseModel):
    caption_text: str | None
    spoken_text: str | None
    visual_text: str | None
    image_text: str | None
    merged_text: str
    warnings: list[str]
    debug: dict | list | str | int | float | bool | None = None


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
