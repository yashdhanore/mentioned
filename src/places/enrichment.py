from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from sqlmodel import Session

from src.extraction.schemas import ExtractedMention
from src.places.schemas import GooglePlace
from src.places.service import upsert_google_place
from src.sources.models import SourceItem

logger = logging.getLogger(__name__)

PlaceFinder = Callable[[str, str | None], GooglePlace | None]


def find_google_place_sync(name: str, location_hint: str | None) -> GooglePlace | None:
    # Real Google Places provider lands in a later slice (issue #46); the seam
    # degrades to no enrichment until then, matching the book finder's fail-open style.
    try:
        from src.extraction.google_places import find_google_place

        return asyncio.run(find_google_place(name, location_hint))
    except Exception as exc:
        logger.warning("Google Places enrichment failed: %s", exc)
        return None


def enrich_extracted_place_item(
    session: Session,
    item: SourceItem,
    extracted: ExtractedMention,
    *,
    place_finder: PlaceFinder = find_google_place_sync,
) -> None:
    google_place = place_finder(extracted.title, extracted.location_hint)
    if not google_place:
        return

    place = upsert_google_place(session, google_place)
    item.place_id = place.id
    item.formatted_address = place.formatted_address
    item.latitude = place.latitude
    item.longitude = place.longitude
    item.maps_url = place.maps_url
