from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class PushPlatform(StrEnum):
    IOS = "ios"
    ANDROID = "android"


class PushToken(SQLModel, table=True):
    __tablename__ = "push_tokens"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(nullable=False, index=True)
    expo_push_token: str = Field(nullable=False, index=True)
    platform: str = Field(nullable=False)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    disabled_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
