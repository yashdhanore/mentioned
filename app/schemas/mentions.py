from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SavedMentionResponse(BaseModel):
    mention_id: str
    category: str
    display_label: str
    display_author_or_creator: str | None
    display_description: str | None
    extracted_label: str
    extracted_author_or_creator: str | None
    extracted_description: str | None
    source_job_id: str
    source_url: str
    source_platform: str
    source_creator: str | None
    source_context_snippet: str | None
    evidence_text: str | None
    evidence: dict
    confidence: float | None
    save_state: str
    review_status: str
    created_at: datetime
    updated_at: datetime


class SavedMentionListResponse(BaseModel):
    items: list[SavedMentionResponse]
    next_cursor: str | None


class UpdateSavedMentionRequest(StrictModel):
    display_label: str | None = Field(default=None, min_length=1, max_length=300)
    display_author_or_creator: str | None = Field(default=None, max_length=300)
    display_description: str | None = Field(default=None, max_length=2000)
    category: str | None = None
