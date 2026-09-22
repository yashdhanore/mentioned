from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GoogleBook:
    provider_volume_id: str
    title: str
    provider_etag: str | None = None
    provider_self_link: str | None = None
    subtitle: str | None = None
    authors: list[str] = field(default_factory=list)
    publisher: str | None = None
    published_date: str | None = None
    description: str | None = None
    industry_identifiers: list[dict[str, Any]] = field(default_factory=list)
    page_count: int | None = None
    print_type: str | None = None
    language: str | None = None
    main_category: str | None = None
    categories: list[str] = field(default_factory=list)
    image_links: dict[str, str] = field(default_factory=dict)
    cover_image_url: str | None = None
    preview_link: str | None = None
    info_link: str | None = None
    canonical_volume_link: str | None = None
    sale_info: dict[str, Any] | None = None
    access_info: dict[str, Any] | None = None
    raw_provider_payload: dict[str, Any] | None = None
