from __future__ import annotations

from sqlmodel import Session, select

from src.extraction.schemas import ExtractedMention
from src.places.enrichment import enrich_extracted_place_item
from src.places.models import Place
from src.places.schemas import GooglePlace
from src.sources.models import Source, SourceItem, SourceStatus


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


def _source(session: Session) -> Source:
    source = Source(
        source_key="instagram:reel:PLACE1",
        platform="instagram",
        source_type="reel",
        external_id="PLACE1",
        canonical_url="https://www.instagram.com/reel/PLACE1/",
        status=SourceStatus.PROCESSING,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def _item(source: Source) -> SourceItem:
    return SourceItem(
        source_id=source.id,
        title="Cafe Nero",
        category="place",
        confidence=0.8,
        position=0,
    )


def test_enrich_place_item_upserts_place_and_denormalizes(session: Session) -> None:
    source = _source(session)
    item = _item(source)
    extracted = ExtractedMention(
        title="Cafe Nero",
        category="place",
        confidence=0.8,
        location_hint="London",
    )

    enrich_extracted_place_item(
        session,
        item,
        extracted,
        place_finder=lambda _name, _hint: _google_place(),
    )

    places = list(session.exec(select(Place)).all())
    assert len(places) == 1
    assert item.place_id == places[0].id
    assert item.formatted_address == "12 King St, London, UK"
    assert item.latitude == 51.5072
    assert item.longitude == -0.1276
    assert item.maps_url == "https://www.google.com/maps/place/?q=place_id:ChIJ-place-1"
