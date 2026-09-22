from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import pytest
from sqlmodel import Session

from src.config import Settings
from src.sources.models import SavedSource, Source, SourceItem, SourceStatus
from src.timeutils import utc_now

TEST_USER_ID = "00000000-0000-4000-8000-000000000001"
TEST_USER_UUID = UUID(TEST_USER_ID)
OTHER_USER_UUID = UUID("00000000-0000-4000-8000-000000000002")


def _quota_settings() -> Settings:
    return Settings(
        max_job_create_burst_per_minute=3,
        max_jobs_created_per_day=25,
        max_active_jobs_per_user=5,
    )


def _https_required_settings() -> Settings:
    return Settings(source_require_https=True)


@pytest.fixture
def enqueued(monkeypatch) -> list[str]:
    enqueued: list[str] = []
    monkeypatch.setattr(
        "src.sources.service.enqueue_source_extraction",
        lambda _session, source_id: enqueued.append(str(source_id)),
    )
    return enqueued


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
        created_at=created_at or utc_now(),
    )
    session.add(saved)
    session.commit()
    session.refresh(saved)
    return saved


def _set_saved_source_retry_attempts(
    session: Session,
    saved: SavedSource,
    attempted_at: datetime,
    *,
    burst_count: int = 1,
    daily_count: int = 1,
) -> None:
    saved.last_retry_at = attempted_at
    saved.retry_burst_started_at = attempted_at
    saved.retry_burst_count = burst_count
    saved.retry_daily_started_at = attempted_at
    saved.retry_daily_count = daily_count
    session.add(saved)
    session.commit()


async def test_create_saved_source(client) -> None:
    resp = await client.post(
        "/v1/saved-sources", json={"url": "https://www.instagram.com/reel/ABC123/"}
    )

    assert resp.status_code == 202
    data = resp.json()
    assert data["source_key"] == "instagram:reel:ABC123"
    assert data["status"] == "processing"
    # The mobile app parses this with Date.parse, which reads a timestamp without an
    # offset as local time, so the API must send an explicit "Z".
    assert data["created_at"].endswith("Z")


async def test_create_saved_source_allows_http_when_https_not_required(client) -> None:
    resp = await client.post(
        "/v1/saved-sources", json={"url": "http://www.instagram.com/reel/ABC123/"}
    )

    assert resp.status_code == 202
    data = resp.json()
    assert data["source_key"] == "instagram:reel:ABC123"


async def test_create_saved_source_rejects_http_when_https_required(client, monkeypatch) -> None:
    monkeypatch.setattr("src.sources.router.get_settings", _https_required_settings)

    resp = await client.post(
        "/v1/saved-sources", json={"url": "http://www.instagram.com/reel/ABC123/"}
    )

    assert resp.status_code == 400
    assert resp.json()["error_code"] == "invalid_source_url"


async def test_create_saved_source_allows_https_when_https_required(client, monkeypatch) -> None:
    monkeypatch.setattr("src.sources.router.get_settings", _https_required_settings)

    resp = await client.post(
        "/v1/saved-sources", json={"url": "https://www.instagram.com/reel/ABC123/"}
    )

    assert resp.status_code == 202
    data = resp.json()
    assert data["source_key"] == "instagram:reel:ABC123"


async def test_list_saved_sources_returns_items(client, session: Session) -> None:
    source = Source(
        source_key="instagram:reel:BOOK123",
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
    now = utc_now()
    for index in range(3):
        _save_source(
            session,
            f"BURST{index}",
            status=SourceStatus.DONE,
            created_at=now - timedelta(seconds=index),
        )

    resp = await client.post(
        "/v1/saved-sources", json={"url": "https://www.instagram.com/reel/ABC123/"}
    )

    assert resp.status_code == 429
    assert resp.json()["error_code"] == "rate_limited"


async def test_create_saved_source_daily_quota(client, session: Session, monkeypatch) -> None:
    monkeypatch.setattr("src.sources.router.get_settings", _quota_settings)
    now = utc_now()
    for index in range(25):
        _save_source(
            session,
            f"DAILY{index}",
            status=SourceStatus.DONE,
            created_at=now - timedelta(hours=2, minutes=index),
        )

    resp = await client.post(
        "/v1/saved-sources", json={"url": "https://www.instagram.com/reel/ABC123/"}
    )

    assert resp.status_code == 429
    assert resp.json()["error_code"] == "quota_exceeded"


async def test_create_saved_source_active_quota(client, session: Session, monkeypatch) -> None:
    monkeypatch.setattr("src.sources.router.get_settings", _quota_settings)
    for index in range(5):
        _save_source(session, f"ACTIVE{index}", status=SourceStatus.PENDING)

    resp = await client.post(
        "/v1/saved-sources", json={"url": "https://www.instagram.com/reel/ABC123/"}
    )

    assert resp.status_code == 429
    assert resp.json()["error_code"] == "quota_exceeded"


async def test_create_saved_source_reuses_existing_at_active_quota(
    client,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr("src.sources.router.get_settings", _quota_settings)
    existing = _save_source(session, "EXISTINGACTIVE", status=SourceStatus.PENDING)
    for index in range(4):
        _save_source(session, f"ACTIVE{index}", status=SourceStatus.PENDING)

    resp = await client.post(
        "/v1/saved-sources",
        json={"url": "https://www.instagram.com/reel/EXISTINGACTIVE/"},
    )

    assert resp.status_code == 202
    data = resp.json()
    assert data["id"] == str(existing.id)
    assert data["source_key"] == "instagram:reel:EXISTINGACTIVE"


async def test_create_saved_source_reuses_existing_at_burst_limit(
    client,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr("src.sources.router.get_settings", _quota_settings)
    now = utc_now()
    existing = _save_source(
        session,
        "EXISTINGBURST",
        status=SourceStatus.DONE,
        created_at=now,
    )
    for index in range(2):
        _save_source(
            session,
            f"BURST{index}",
            status=SourceStatus.DONE,
            created_at=now - timedelta(seconds=index),
        )

    resp = await client.post(
        "/v1/saved-sources",
        json={"url": "https://www.instagram.com/reel/EXISTINGBURST/"},
    )

    assert resp.status_code == 202
    assert resp.json()["id"] == str(existing.id)


async def test_create_saved_source_requeues_existing_failed_source(
    client,
    session: Session,
    enqueued: list[str],
) -> None:
    saved = _save_source(session, "FAILEDRETRY", status=SourceStatus.FAILED)
    source = session.get(Source, saved.source_id)
    assert source is not None
    source.error_message = "network timeout"
    source.processing_started_at = utc_now() - timedelta(minutes=5)
    source.processed_at = utc_now()
    session.add(source)
    session.commit()

    resp = await client.post(
        "/v1/saved-sources",
        json={"url": "https://www.instagram.com/reel/FAILEDRETRY/"},
    )

    session.expire_all()
    refreshed = session.get(Source, saved.source_id)
    assert refreshed is not None
    assert resp.status_code == 202
    data = resp.json()
    assert data["id"] == str(saved.id)
    assert data["status"] == "processing"
    assert data["error_message"] is None
    assert refreshed.status == SourceStatus.PENDING
    assert refreshed.error_message is None
    assert refreshed.processing_started_at is None
    assert refreshed.processed_at is None
    assert enqueued == [str(saved.source_id)]


async def test_create_saved_source_failed_retry_blocks_at_active_quota(
    client,
    session: Session,
    monkeypatch,
    enqueued: list[str],
) -> None:
    monkeypatch.setattr("src.sources.router.get_settings", _quota_settings)
    saved = _save_source(session, "FAILEDQUOTA", status=SourceStatus.FAILED)
    for index in range(5):
        _save_source(session, f"ACTIVEFAILEDRETRY{index}", status=SourceStatus.PENDING)

    resp = await client.post(
        "/v1/saved-sources",
        json={"url": "https://www.instagram.com/reel/FAILEDQUOTA/"},
    )

    session.expire_all()
    refreshed = session.get(Source, saved.source_id)
    assert refreshed is not None
    assert resp.status_code == 429
    assert resp.json()["error_code"] == "quota_exceeded"
    assert refreshed.status == SourceStatus.FAILED
    assert enqueued == []


async def test_create_saved_source_failed_retry_uses_burst_throttle(
    client,
    session: Session,
    monkeypatch,
    enqueued: list[str],
) -> None:
    monkeypatch.setattr("src.sources.router.get_settings", _quota_settings)
    now = utc_now()
    target = _save_source(
        session,
        "FAILEDBURSTRETRY",
        status=SourceStatus.FAILED,
        created_at=now - timedelta(days=2),
    )
    _set_saved_source_retry_attempts(session, target, now - timedelta(hours=2))
    saved = _save_source(
        session,
        "RECENTFAILEDRETRIES",
        status=SourceStatus.FAILED,
        created_at=now - timedelta(days=2),
    )
    _set_saved_source_retry_attempts(
        session,
        saved,
        now - timedelta(seconds=10),
        burst_count=3,
    )

    resp = await client.post(
        "/v1/saved-sources",
        json={"url": "https://www.instagram.com/reel/FAILEDBURSTRETRY/"},
    )

    session.expire_all()
    refreshed = session.get(Source, target.source_id)
    assert refreshed is not None
    assert resp.status_code == 429
    assert resp.json()["error_code"] == "rate_limited"
    assert refreshed.status == SourceStatus.FAILED
    assert enqueued == []


async def test_create_saved_source_failed_retry_combines_create_and_retry_burst_counts(
    client,
    session: Session,
    monkeypatch,
    enqueued: list[str],
) -> None:
    monkeypatch.setattr("src.sources.router.get_settings", _quota_settings)
    now = utc_now()
    target = _save_source(
        session,
        "FAILEDMIXEDBURST",
        status=SourceStatus.FAILED,
        created_at=now - timedelta(days=2),
    )
    _set_saved_source_retry_attempts(session, target, now - timedelta(hours=2))
    for index in range(2):
        _save_source(
            session,
            f"MIXEDBURSTCREATE{index}",
            status=SourceStatus.DONE,
            created_at=now - timedelta(seconds=index),
        )
    saved = _save_source(
        session,
        "MIXEDBURSTRETRY",
        status=SourceStatus.FAILED,
        created_at=now - timedelta(days=2),
    )
    _set_saved_source_retry_attempts(session, saved, now - timedelta(seconds=10))

    resp = await client.post(
        "/v1/saved-sources",
        json={"url": "https://www.instagram.com/reel/FAILEDMIXEDBURST/"},
    )

    session.expire_all()
    refreshed = session.get(Source, target.source_id)
    assert refreshed is not None
    assert resp.status_code == 429
    assert resp.json()["error_code"] == "rate_limited"
    assert refreshed.status == SourceStatus.FAILED
    assert enqueued == []


async def test_create_saved_source_failed_retry_uses_daily_throttle(
    client,
    session: Session,
    monkeypatch,
    enqueued: list[str],
) -> None:
    monkeypatch.setattr("src.sources.router.get_settings", _quota_settings)
    now = utc_now()
    target = _save_source(
        session,
        "FAILEDAILYRETRY",
        status=SourceStatus.FAILED,
        created_at=now - timedelta(days=2),
    )
    _set_saved_source_retry_attempts(session, target, now - timedelta(days=2))
    saved = _save_source(
        session,
        "DAILYFAILEDRETRIES",
        status=SourceStatus.FAILED,
        created_at=now - timedelta(days=2),
    )
    _set_saved_source_retry_attempts(
        session,
        saved,
        now - timedelta(hours=2),
        daily_count=25,
    )

    resp = await client.post(
        "/v1/saved-sources",
        json={"url": "https://www.instagram.com/reel/FAILEDAILYRETRY/"},
    )

    session.expire_all()
    refreshed = session.get(Source, target.source_id)
    assert refreshed is not None
    assert resp.status_code == 429
    assert resp.json()["error_code"] == "quota_exceeded"
    assert refreshed.status == SourceStatus.FAILED
    assert enqueued == []


async def test_create_saved_source_failed_retry_combines_create_and_retry_daily_counts(
    client,
    session: Session,
    monkeypatch,
    enqueued: list[str],
) -> None:
    monkeypatch.setattr("src.sources.router.get_settings", _quota_settings)
    now = utc_now()
    target = _save_source(
        session,
        "FAILEDMIXEDDAILY",
        status=SourceStatus.FAILED,
        created_at=now - timedelta(days=2),
    )
    _set_saved_source_retry_attempts(session, target, now - timedelta(days=2))
    for index in range(24):
        _save_source(
            session,
            f"MIXEDDAILYCREATE{index}",
            status=SourceStatus.DONE,
            created_at=now - timedelta(hours=2, minutes=index),
        )
    saved = _save_source(
        session,
        "MIXEDDAILYRETRY",
        status=SourceStatus.FAILED,
        created_at=now - timedelta(days=2),
    )
    _set_saved_source_retry_attempts(
        session,
        saved,
        now - timedelta(hours=2),
        daily_count=1,
    )

    resp = await client.post(
        "/v1/saved-sources",
        json={"url": "https://www.instagram.com/reel/FAILEDMIXEDDAILY/"},
    )

    session.expire_all()
    refreshed = session.get(Source, target.source_id)
    assert refreshed is not None
    assert resp.status_code == 429
    assert resp.json()["error_code"] == "quota_exceeded"
    assert refreshed.status == SourceStatus.FAILED
    assert enqueued == []


async def test_create_saved_source_does_not_requeue_existing_non_failed_source(
    client,
    session: Session,
    enqueued: list[str],
) -> None:
    saved = _save_source(session, "DONERETRY", status=SourceStatus.DONE)

    resp = await client.post(
        "/v1/saved-sources",
        json={"url": "https://www.instagram.com/reel/DONERETRY/"},
    )

    session.expire_all()
    refreshed = session.get(Source, saved.source_id)
    assert refreshed is not None
    assert resp.status_code == 202
    data = resp.json()
    assert data["id"] == str(saved.id)
    assert data["status"] == "done"
    assert refreshed.status == SourceStatus.DONE
    assert enqueued == []


async def test_delete_saved_source_unlinks_only_user_save(client) -> None:
    create_resp = await client.post(
        "/v1/saved-sources", json={"url": "https://www.instagram.com/reel/ABC123/"}
    )
    saved_source_id = create_resp.json()["id"]

    resp = await client.delete(f"/v1/saved-sources/{saved_source_id}")

    assert resp.status_code == 200
    assert resp.json() == {"id": saved_source_id, "deleted": True}
    list_resp = await client.get("/v1/saved-sources")
    assert list_resp.json() == []
