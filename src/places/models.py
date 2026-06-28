from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Index
from sqlmodel import Field, SQLModel


class Place(SQLModel, table=True):
    __tablename__ = "places"
    __table_args__ = (
        Index(
            "places_provider_place_unique_idx",
            "provider",
            "provider_place_id",
            unique=True,
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    provider: str = Field(default="google_places", nullable=False, index=True)
    provider_place_id: str = Field(nullable=False, index=True)

    name: str = Field(nullable=False)
    formatted_address: str | None = Field(default=None)
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)
    maps_url: str | None = Field(default=None)

    raw_provider_payload: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
