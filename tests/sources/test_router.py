from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import pytest
from sqlmodel import Session

from src.config import Settings
from src.sources.models import SavedSource, Source, SourceItem, SourceStatus


pytestmark = pytest.mark.asyncio
TEST_USER_ID = "00000000-0000-4000-8000-000000000001"
TEST_USER_UUID = UUID(TEST_USER_ID)
OTHER_USER_UUID = UUID("00000000-0000-4000-8000-000000000002")


def _quota_settings() -> Settings:
    return Settings(
        max_job_create_burst_per_minute=3,
        max_jobs_created_per_day=25,
        max_active_jobs_per_user=5,
    )


def _save_source(
    session: Session,
    external_id: str,
    *,
    owner_id: UUID = TEST_USER_UUID,
    status: SourceStatus = SourceStatus.DONE,
    created_at: datetime | None = None,
) -> SavedSource:
    source = Source(
        source_key=f"instagram:reel:{external_id}",
        platform="instagram",
        source_type="reel",
        external_id=external_id,
        canonical_url=f"https://www.instagram.com/reel/{external_id}/",
        status=status,
    )
    session.add(source)
    session.commit()
    session.refresh(source)

    saved = SavedSource(
        owner_id=owner_id,
        source_id=source.id,
        created_at=created_at or datetime.utcnow(),
    )
    session.add(saved)
    session.commit()
    session.refresh(saved)
    return saved


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


async def test_get_saved_source_returns_items(client, session: Session) -> None:
    saved = _save_source(session, "GET123")
    session.add(
        SourceItem(
            source_id=saved.source_id,
            category="book",
            title="The Creative Act",
            author="Rick Rubin",
            position=0,
        )
    )
    session.commit()

    resp = await client.get(f"/v1/saved-sources/{saved.id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(saved.id)
    assert data["source_key"] == "instagram:reel:GET123"
    assert data["status"] == "done"
    assert data["items"][0]["title"] == "The Creative Act"


async def test_get_saved_source_invalid_id_uses_source_error(client) -> None:
    resp = await client.get("/v1/saved-sources/not-a-uuid")

    assert resp.status_code == 404
    assert resp.json()["error_code"] == "saved_source_not_found"


async def test_get_saved_source_wrong_owner_not_found(client, session: Session) -> None:
    saved = _save_source(session, "OTHER123", owner_id=OTHER_USER_UUID)

    resp = await client.get(f"/v1/saved-sources/{saved.id}")

    assert resp.status_code == 404
    assert resp.json()["error_code"] == "saved_source_not_found"


async def test_delete_saved_source_wrong_owner_not_found(client, session: Session) -> None:
    saved = _save_source(session, "DELETEOTHER123", owner_id=OTHER_USER_UUID)

    resp = await client.delete(f"/v1/saved-sources/{saved.id}")

    assert resp.status_code == 404
    assert resp.json()["error_code"] == "saved_source_not_found"
    assert session.get(SavedSource, saved.id) is not None


@pytest.mark.parametrize(
    ("source_status", "app_status"),
    [
        (SourceStatus.PENDING, "processing"),
        (SourceStatus.PROCESSING, "processing"),
        (SourceStatus.DONE, "done"),
        (SourceStatus.FAILED, "failed"),
    ],
)
async def test_get_saved_source_maps_source_status(
    client,
    session: Session,
    source_status: SourceStatus,
    app_status: str,
) -> None:
    saved = _save_source(session, f"STATUS{source_status.value}", status=source_status)

    resp = await client.get(f"/v1/saved-sources/{saved.id}")

    assert resp.status_code == 200
    assert resp.json()["status"] == app_status


async def test_create_saved_source_invalid_url_uses_source_error(client) -> None:
    resp = await client.post("/v1/saved-sources", json={"url": "https://example.com/foo"})

    assert resp.status_code == 400
    assert resp.json()["error_code"] == "invalid_source_url"


async def test_create_saved_source_burst_limit(client, session: Session, monkeypatch) -> None:
    monkeypatch.setattr("src.sources.router.get_settings", _quota_settings)
    now = datetime.utcnow()
    for index in range(3):
        _save_source(
            session,
            f"BURST{index}",
            status=SourceStatus.DONE,
            created_at=now - timedelta(seconds=index),
        )

    resp = await client.post("/v1/saved-sources", json={"url": "https://www.instagram.com/reel/ABC123/"})

    assert resp.status_code == 429
    assert resp.json()["error_code"] == "rate_limited"


async def test_create_saved_source_daily_quota(client, session: Session, monkeypatch) -> None:
    monkeypatch.setattr("src.sources.router.get_settings", _quota_settings)
    now = datetime.utcnow()
    for index in range(25):
        _save_source(
            session,
            f"DAILY{index}",
            status=SourceStatus.DONE,
            created_at=now - timedelta(hours=2, minutes=index),
        )

    resp = await client.post("/v1/saved-sources", json={"url": "https://www.instagram.com/reel/ABC123/"})

    assert resp.status_code == 429
    assert resp.json()["error_code"] == "quota_exceeded"


async def test_create_saved_source_active_quota(client, session: Session, monkeypatch) -> None:
    monkeypatch.setattr("src.sources.router.get_settings", _quota_settings)
    for index in range(5):
        _save_source(session, f"ACTIVE{index}", status=SourceStatus.PENDING)

    resp = await client.post("/v1/saved-sources", json={"url": "https://www.instagram.com/reel/ABC123/"})

    assert resp.status_code == 429
    assert resp.json()["error_code"] == "quota_exceeded"


async def test_delete_saved_source_unlinks_only_user_save(client) -> None:
    create_resp = await client.post("/v1/saved-sources", json={"url": "https://www.instagram.com/reel/ABC123/"})
    saved_source_id = create_resp.json()["id"]

    resp = await client.delete(f"/v1/saved-sources/{saved_source_id}")

    assert resp.status_code == 200
    assert resp.json() == {"id": saved_source_id, "deleted": True}
    list_resp = await client.get("/v1/saved-sources")
    assert list_resp.json() == []
