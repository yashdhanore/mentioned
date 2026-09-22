from __future__ import annotations

from uuid import UUID

import pytest
from sqlmodel import Session

from src.books.schemas import GoogleBook
from src.extraction.schemas import ExtractedMention, PipelineResult
from src.ingestion.source_processor import SourceIngestion
from src.places.schemas import GooglePlace
from src.sources.models import SavedSource, Source, SourceStatus
from src.timeutils import utc_now

pytestmark = pytest.mark.asyncio
TEST_USER_UUID = UUID("00000000-0000-4000-8000-000000000001")


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


def _saved_pending_source(session: Session, external_id: str) -> SavedSource:
    source = Source(
        source_key=f"instagram:reel:{external_id}",
        platform="instagram",
        source_type="reel",
        external_id=external_id,
        canonical_url=f"https://www.instagram.com/reel/{external_id}/",
        status=SourceStatus.PROCESSING,
    )
    session.add(source)
    session.commit()
    session.refresh(source)

    saved = SavedSource(
        owner_id=TEST_USER_UUID,
        source_id=source.id,
        created_at=utc_now(),
    )
    session.add(saved)
    session.commit()
    session.refresh(saved)
    return saved


async def test_place_enrichment_flows_from_worker_to_http(client, session: Session) -> None:
    saved = _saved_pending_source(session, "TRACER1")
    source = session.get(Source, saved.source_id)

    SourceIngestion(
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
    ).process_source(session, source)

    resp = await client.get(f"/v1/saved-sources/{saved.id}")

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["category"] == "place"
    assert item["title"] == "Cafe Nero"
    assert item["formatted_address"] == "12 King St, London, UK"
    assert item["latitude"] == 51.5072
    assert item["longitude"] == -0.1276
    assert item["place_id"] is not None
    assert item["maps_url"] == "https://www.google.com/maps/place/?q=place_id:ChIJ-place-1"


async def test_mixed_source_tracer_book_place_product_over_http(client, session: Session) -> None:
    saved = _saved_pending_source(session, "TRACER2")
    source = session.get(Source, saved.source_id)

    SourceIngestion(
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
    ).process_source(session, source)

    resp = await client.get(f"/v1/saved-sources/{saved.id}")

    assert resp.status_code == 200
    items = {item["category"]: item for item in resp.json()["items"]}

    # Book enriched its book fields; place fields null.
    assert items["book"]["google_books_url"] == "https://books.google.com/books?id=google-volume-1"
    assert items["book"]["cover_image_url"] == "https://books.google.com/thumb.jpg"
    assert items["book"]["formatted_address"] is None

    # Place enriched its place fields; book fields null.
    assert items["place"]["formatted_address"] == "12 King St, London, UK"
    assert items["place"]["latitude"] == 51.5072
    assert items["place"]["google_books_url"] is None

    # Product untouched by either enrichment.
    assert items["product"]["place_id"] is None
    assert items["product"]["formatted_address"] is None
    assert items["product"]["google_books_url"] is None
