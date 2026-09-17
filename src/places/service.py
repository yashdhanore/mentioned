from __future__ import annotations

from sqlmodel import Session, select

from src.places.models import Place
from src.places.schemas import GooglePlace
from src.timeutils import utc_now


def upsert_google_place(session: Session, google_place: GooglePlace) -> Place:
    stmt = select(Place).where(
        Place.provider == "google_places",
        Place.provider_place_id == google_place.provider_place_id,
    )
    place = session.exec(stmt).first()
    now = utc_now()

    fields = {
        "provider": "google_places",
        "provider_place_id": google_place.provider_place_id,
        "name": google_place.name,
        "formatted_address": google_place.formatted_address,
        "latitude": google_place.latitude,
        "longitude": google_place.longitude,
        "maps_url": google_place.maps_url,
        "raw_provider_payload": google_place.raw_provider_payload,
        "updated_at": now,
    }

    if place is None:
        place = Place(**fields)
    else:
        for key, value in fields.items():
            setattr(place, key, value)

    session.add(place)
    session.flush()
    return place
