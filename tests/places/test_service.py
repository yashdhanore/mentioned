from __future__ import annotations

from sqlmodel import Session, select

from src.places.models import Place
from src.places.schemas import GooglePlace
from src.places.service import upsert_google_place


def _google_place() -> GooglePlace:
    return GooglePlace(
        provider_place_id="ChIJ-place-1",
        name="Cafe Nero",
        formatted_address="12 King St, London, UK",
        latitude=51.5072,
        longitude=-0.1276,
        maps_url="https://www.google.com/maps/place/?q=place_id:ChIJ-place-1",
        raw_provider_payload={"id": "ChIJ-place-1"},
    )


def test_upsert_google_place_dedups_on_provider_place_id(session: Session) -> None:
    first = upsert_google_place(session, _google_place())
    second = upsert_google_place(session, _google_place())

    places = list(session.exec(select(Place)).all())
    assert len(places) == 1
    assert first.id == second.id


def test_upsert_google_place_updates_existing_fields(session: Session) -> None:
    upsert_google_place(session, _google_place())

    moved = _google_place()
    moved.formatted_address = "99 New Rd, London, UK"
    place = upsert_google_place(session, moved)

    assert place.formatted_address == "99 New Rd, London, UK"
    assert len(list(session.exec(select(Place)).all())) == 1
