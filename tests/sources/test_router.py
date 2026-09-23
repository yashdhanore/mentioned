from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import pytest
from sqlmodel import Session

from src.config import Settings
from src.sources.models import SavedSource, Source, SourceStatus
from src.timeutils import utc_now

TEST_USER_ID = "00000000-0000-4000-8000-000000000001"
TEST_USER_UUID = UUID(TEST_USER_ID)


def _quota_settings() -> Settings:
    return Settings(
        max_job_create_burst_per_minute=3,
        max_jobs_created_per_day=25,
        max_active_jobs_per_user=5,
    )


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
