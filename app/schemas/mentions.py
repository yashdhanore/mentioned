from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SavedMentionResponse(BaseModel):
    mention_id: str
    category: str
    label: str
    author_or_creator: str | None
    description: str | None
    source_job_id: str
    source_url: str
    source_platform: str
    source_creator: str | None
    source_context_snippet: str | None
    confidence: float | None
    created_at: datetime
    updated_at: datetime


class SavedMentionListResponse(BaseModel):
    items: list[SavedMentionResponse]
    next_cursor: str | None


class UpdateSavedMentionRequest(StrictModel):
    label: str | None = Field(default=None, min_length=1, max_length=300)
    author_or_creator: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = None
