from __future__ import annotations

from sqlmodel import Session, select

from src.books.schemas import GoogleBook
from src.extraction.schemas import ExtractedMention, PipelineResult
from src.ingestion.source_processor import SourceIngestion
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
    )


def _google_book() -> GoogleBook:
    return GoogleBook(
        provider_volume_id="google-volume-1",
        title="Atomic Habits",
        authors=["James Clear"],
        cover_image_url="https://books.google.com/thumb.jpg",
        info_link="https://books.google.com/books?id=google-volume-1",
    )


def _source(session: Session, key: str) -> Source:
    source = Source(
        source_key=key,
        platform="instagram",
        source_type="reel",
        external_id=key,
        canonical_url=f"https://www.instagram.com/reel/{key}/",
        status=SourceStatus.PROCESSING,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def test_place_mention_routes_through_place_enrichment(session: Session) -> None:
    source = _source(session, "PLACEONLY")
    processor = SourceIngestion(
        extraction_runner=lambda _url: PipelineResult(
            mentions=[
                ExtractedMention(
                    title="Cafe Nero",
                    category="place",
                    confidence=0.8,
                    location_hint="London",
                )
            ],
        ),
        thumbnail_store=lambda _url, *, source_id: None,
        place_finder=lambda _name, _hint: _google_place(),
    )

    processor.process_source(session, source)

    places = list(session.exec(select(Place)).all())
    item = session.exec(select(SourceItem).where(SourceItem.source_id == source.id)).one()

    assert len(places) == 1
    assert item.place_id == places[0].id
    assert item.formatted_address == "12 King St, London, UK"
    assert item.latitude == 51.5072
    assert item.longitude == -0.1276


def test_mixed_source_enriches_book_and_place_leaves_product(session: Session) -> None:
    source = _source(session, "MIXED")
    processor = SourceIngestion(
        extraction_runner=lambda _url: PipelineResult(
            mentions=[
                ExtractedMention(
                    title="Atomic Habits", author="James Clear", category="book", confidence=0.9
                ),
                ExtractedMention(
                    title="Cafe Nero", category="place", confidence=0.8, location_hint="London"
                ),
                ExtractedMention(title="Oura Ring", category="product", confidence=0.9),
            ],
        ),
        thumbnail_store=lambda _url, *, source_id: None,
        book_finder=lambda _title, _author: _google_book(),
        place_finder=lambda _name, _hint: _google_place(),
    )

    processor.process_source(session, source)

    items = {
        item.category: item
        for item in session.exec(select(SourceItem).where(SourceItem.source_id == source.id)).all()
    }

    assert items["book"].book_id is not None
    assert items["book"].cover_image_url == "https://books.google.com/thumb.jpg"
    assert items["book"].place_id is None

    assert items["place"].place_id is not None
    assert items["place"].formatted_address == "12 King St, London, UK"
    assert items["place"].book_id is None

    assert items["product"].book_id is None
    assert items["product"].place_id is None
    assert items["product"].formatted_address is None


def test_place_finder_miss_leaves_bare_title(session: Session) -> None:
    source = _source(session, "PLACEMISS")
    processor = SourceIngestion(
        extraction_runner=lambda _url: PipelineResult(
            mentions=[ExtractedMention(title="Some Cafe", category="place", confidence=0.8)],
        ),
        thumbnail_store=lambda _url, *, source_id: None,
        place_finder=lambda _name, _hint: None,
    )

    processor.process_source(session, source)

    places = list(session.exec(select(Place)).all())
    item = session.exec(select(SourceItem).where(SourceItem.source_id == source.id)).one()

    assert places == []
    assert item.place_id is None
    assert item.title == "Some Cafe"
