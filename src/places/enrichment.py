from __future__ import annotations

from collections.abc import Callable

from sqlmodel import Session

from src.extraction.schemas import ExtractedMention
from src.places.schemas import GooglePlace
from src.places.service import upsert_google_place
from src.sources.models import SourceItem

PlaceFinder = Callable[[str, str | None], GooglePlace | None]


def find_google_place_sync(_name: str, _location_hint: str | None) -> GooglePlace | None:
    # No real Google Places provider exists yet; callers inject a place_finder in tests.
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
