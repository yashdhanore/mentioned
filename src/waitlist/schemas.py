from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class WaitlistSignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(..., max_length=320)
    source: str | None = Field(default=None, max_length=120)


class WaitlistSignupResponse(BaseModel):
    id: str
    email: str
    created: bool
    created_at: datetime
