from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GooglePlace:
    provider_place_id: str
    name: str
    formatted_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    maps_url: str | None = None
    raw_provider_payload: dict[str, Any] | None = field(default=None)
