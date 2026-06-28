from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest
from sqlmodel import Session

from src.sources.models import SavedSource, Source, SourceItem, SourceStatus


pytestmark = pytest.mark.asyncio
TEST_USER_UUID = UUID("00000000-0000-4000-8000-000000000001")


def _save_source(session: Session, external_id: str) -> SavedSource:
    source = Source(
        source_key=f"instagram:reel:{external_id}",
        platform="instagram",
        source_type="reel",
        external_id=external_id,
        canonical_url=f"https://www.instagram.com/reel/{external_id}/",
        status=SourceStatus.DONE,
    )
    session.add(source)
    session.commit()
    session.refresh(source)

    saved = SavedSource(
        owner_id=TEST_USER_UUID,
        source_id=source.id,
        created_at=datetime.utcnow(),
    )
    session.add(saved)
    session.commit()
    session.refresh(saved)
    return saved


async def test_get_saved_source_serializes_place_fields(client, session: Session) -> None:
    saved = _save_source(session, "PLACEAPI")
    session.add(
        SourceItem(
            source_id=saved.source_id,
            category="place",
            title="Cafe Nero",
            confidence=0.8,
            formatted_address="12 King St, London, UK",
            latitude=51.5072,
            longitude=-0.1276,
            maps_url="https://www.google.com/maps/place/?q=place_id:ChIJ-x",
            position=0,
        )
    )
    session.commit()

    resp = await client.get(f"/v1/saved-sources/{saved.id}")

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["category"] == "place"
    assert item["formatted_address"] == "12 King St, London, UK"
    assert item["latitude"] == 51.5072
    assert item["longitude"] == -0.1276
    assert item["maps_url"] == "https://www.google.com/maps/place/?q=place_id:ChIJ-x"


async def test_get_saved_source_place_fields_null_for_book(client, session: Session) -> None:
    saved = _save_source(session, "BOOKAPI")
    session.add(
        SourceItem(
            source_id=saved.source_id,
            category="book",
            title="Atomic Habits",
            author="James Clear",
            confidence=0.91,
            google_books_url="https://books.google.com/books?id=x",
            position=0,
        )
    )
    session.commit()

    resp = await client.get(f"/v1/saved-sources/{saved.id}")

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    # v1 book fields intact.
    assert item["author"] == "James Clear"
    assert item["google_books_url"] == "https://books.google.com/books?id=x"
    # Additive place fields default to null for non-places.
    assert item["place_id"] is None
    assert item["formatted_address"] is None
    assert item["latitude"] is None
    assert item["longitude"] is None
    assert item["maps_url"] is None
