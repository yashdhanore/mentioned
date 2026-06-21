from __future__ import annotations

from uuid import UUID

import pytest
from sqlmodel import Session

from src.sources.models import Source, SourceItem, SourceStatus


pytestmark = pytest.mark.asyncio
TEST_USER_UUID = UUID("00000000-0000-4000-8000-000000000001")


async def test_create_saved_source(client) -> None:
    resp = await client.post("/v1/saved-sources", json={"url": "https://www.instagram.com/reel/ABC123/"})

    assert resp.status_code == 202
    data = resp.json()
    assert data["source_key"] == "instagram:reel:ABC123"
    assert data["status"] == "processing"


async def test_list_saved_sources_returns_items(client, session: Session) -> None:
    source = Source(
        source_key="instagram:reel/BOOK123".replace("/", ":"),
        platform="instagram",
        source_type="reel",
        external_id="BOOK123",
        canonical_url="https://www.instagram.com/reel/BOOK123/",
        status=SourceStatus.DONE,
        thumbnail_url="https://instagram.example/thumb.jpg",
        creator_handle="jamesclear",
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    session.add(
        SourceItem(
            source_id=source.id,
            category="book",
            title="Atomic Habits",
            author="James Clear",
            confidence=0.91,
            position=0,
        )
    )
    session.commit()

    create_resp = await client.post("/v1/saved-sources", json={"url": source.canonical_url})
    assert create_resp.status_code == 202

    resp = await client.get("/v1/saved-sources")

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["source_key"] == "instagram:reel:BOOK123"
    assert data[0]["items"][0]["title"] == "Atomic Habits"


async def test_delete_saved_source_unlinks_only_user_save(client) -> None:
    create_resp = await client.post("/v1/saved-sources", json={"url": "https://www.instagram.com/reel/ABC123/"})
    saved_source_id = create_resp.json()["id"]

    resp = await client.delete(f"/v1/saved-sources/{saved_source_id}")

    assert resp.status_code == 200
    assert resp.json() == {"id": saved_source_id, "deleted": True}
    list_resp = await client.get("/v1/saved-sources")
    assert list_resp.json() == []
