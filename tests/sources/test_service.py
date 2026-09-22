from __future__ import annotations

from datetime import UTC, timedelta
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from src.sources.models import SavedSource, Source, SourceItem, SourceStatus
from src.sources.service import (
    _increment_retry_window,
    claim_source_for_processing,
    complete_source_processing,
    count_active_saved_sources,
    count_saved_source_retry_attempts_since,
    count_saved_sources_created_since,
    delete_saved_source,
    fail_source_processing,
    get_saved_source_by_key,
    recover_stale_sources,
    retry_failed_saved_source,
    save_source_for_user,
)
from src.timeutils import utc_now

OWNER = "00000000-0000-4000-8000-000000000001"
OWNER_UUID = UUID(OWNER)
OTHER_OWNER = "00000000-0000-4000-8000-000000000002"


def test_increment_retry_window_handles_timezone_aware_started_at() -> None:
    # Postgres returns timezone-aware datetimes for DateTime(timezone=True)
    # columns, while utc_now() is naive. The window comparison must not
    # raise "can't compare offset-naive and offset-aware datetimes".
    now = utc_now()
    aware_started_at = (now - timedelta(seconds=10)).replace(tzinfo=UTC)

    started_at, count = _increment_retry_window(
        aware_started_at,
        2,
        now,
        timedelta(minutes=1),
    )

    # Within the window: same instant (normalized to naive UTC), incremented count.
    assert count == 3
    assert started_at == aware_started_at.replace(tzinfo=None)
    assert started_at.tzinfo is None


def test_increment_retry_window_resets_when_aware_started_at_is_stale() -> None:
    now = utc_now()
    aware_started_at = (now - timedelta(minutes=5)).replace(tzinfo=UTC)

    started_at, count = _increment_retry_window(
        aware_started_at,
        9,
        now,
        timedelta(minutes=1),
    )

    # Outside the window: reset to now / count 1.
    assert count == 1
    assert started_at == now


def test_save_source_for_user_creates_source_and_saved_source(
    session: Session, monkeypatch
) -> None:
    enqueued: list[str] = []
    monkeypatch.setattr(
        "src.sources.service.enqueue_source_extraction",
        lambda _session, source_id: enqueued.append(str(source_id)),
    )

    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/ABC123/")

    source = session.get(Source, saved.source_id)
    assert source is not None
    assert source.source_key == "instagram:reel:ABC123"
    assert source.status == SourceStatus.PENDING
    assert saved.owner_id == OWNER_UUID
    assert enqueued == [str(source.id)]


def test_save_source_for_user_reuses_existing_source_and_saved_source(
    session: Session, monkeypatch
) -> None:
    enqueued: list[str] = []
    monkeypatch.setattr(
        "src.sources.service.enqueue_source_extraction",
        lambda _session, source_id: enqueued.append(str(source_id)),
    )

    first = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/ABC123/?igsh=x")
    second = save_source_for_user(session, OWNER, "https://instagram.com/reel/ABC123")

    assert second.id == first.id
    assert len(list(session.exec(select(Source)).all())) == 1
    assert len(list(session.exec(select(SavedSource)).all())) == 1
    assert len(enqueued) == 1


def test_save_source_for_user_rolls_back_when_enqueue_fails(session: Session, monkeypatch) -> None:
    def fail_enqueue(_session: Session, _source_id: UUID) -> None:
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr("src.sources.service.enqueue_source_extraction", fail_enqueue)

    with pytest.raises(RuntimeError, match="queue unavailable"):
        save_source_for_user(session, OWNER, "https://www.instagram.com/reel/ABC123/")

    assert len(list(session.exec(select(Source)).all())) == 0
    assert len(list(session.exec(select(SavedSource)).all())) == 0


def test_save_source_for_user_retries_once_after_integrity_error(
    session: Session, monkeypatch
) -> None:
    enqueued: list[str] = []
    monkeypatch.setattr(
        "src.sources.service.enqueue_source_extraction",
        lambda _session, source_id: enqueued.append(str(source_id)),
    )
    original_flush = session.flush
    calls = 0

    def flaky_flush() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise IntegrityError("insert source", {}, Exception("duplicate source"))
        original_flush()

    monkeypatch.setattr(session, "flush", flaky_flush)

    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/ABC123/")

    assert saved.source_id is not None
    assert calls >= 2
    assert len(list(session.exec(select(Source)).all())) == 1
    assert len(list(session.exec(select(SavedSource)).all())) == 1
    assert len(enqueued) == 1


def test_claim_source_for_processing_claims_only_pending_source(session: Session) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/ABC123/")

    claimed = claim_source_for_processing(session, saved.source_id)
    second_claim = claim_source_for_processing(session, saved.source_id)

    assert claimed is not None
    assert claimed.status == SourceStatus.PROCESSING
    assert claimed.processing_started_at is not None
    assert second_claim is None


def test_complete_source_processing_marks_done_and_persists_items(session: Session) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/ABC123/")
    source = claim_source_for_processing(session, saved.source_id)
    assert source is not None
    source.error_message = "previous error"
    item = SourceItem(
        source_id=source.id,
        category="book",
        title="Atomic Habits",
        author="James Clear",
        confidence=0.91,
        position=0,
    )

    completed = complete_source_processing(session, source, [item])

    updated_source = session.get(Source, source.id)
    assert updated_source is not None
    assert completed is True
    assert updated_source.status == SourceStatus.DONE
    assert updated_source.error_message is None
    assert updated_source.processed_at is not None
    persisted_item = session.exec(select(SourceItem).where(SourceItem.source_id == source.id)).one()
    assert persisted_item.title == "Atomic Habits"


def test_complete_source_processing_enqueues_push_notification_before_commit(
    session: Session, monkeypatch
) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/PUSHDONE/")
    source = claim_source_for_processing(session, saved.source_id)
    assert source is not None
    enqueued: list[tuple[UUID, bool]] = []

    def fake_enqueue(inner_session: Session, source_id) -> None:
        enqueued.append((source_id, inner_session.in_transaction()))

    monkeypatch.setattr("src.sources.service.enqueue_push_notification", fake_enqueue)

    completed = complete_source_processing(session, source, [])

    assert completed is True
    assert enqueued == [(source.id, True)]


def test_fail_source_processing_enqueues_push_notification_before_commit(
    session: Session, monkeypatch
) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/PUSHFAIL/")
    source = claim_source_for_processing(session, saved.source_id)
    assert source is not None
    enqueued: list[tuple[UUID, bool]] = []

    def fake_enqueue(inner_session: Session, source_id) -> None:
        enqueued.append((source_id, inner_session.in_transaction()))

    monkeypatch.setattr("src.sources.service.enqueue_push_notification", fake_enqueue)

    failed = fail_source_processing(session, source, "network timeout")

    assert failed is True
    assert enqueued == [(source.id, True)]


def test_complete_source_processing_persists_skip_reason(session: Session) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/SKIPME/")
    source = claim_source_for_processing(session, saved.source_id)
    assert source is not None

    completed = complete_source_processing(session, source, [], skip_reason="dance clip")

    updated_source = session.get(Source, source.id)
    assert completed is True
    assert updated_source is not None
    assert updated_source.status == SourceStatus.DONE
    assert updated_source.skip_reason == "dance clip"


def test_complete_source_processing_clears_skip_reason_on_normal_completion(
    session: Session,
) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/CLEARSKIP/")
    source = claim_source_for_processing(session, saved.source_id)
    assert source is not None
    source.skip_reason = "stale skip"
    item = SourceItem(source_id=source.id, category="book", title="Real Book", position=0)

    completed = complete_source_processing(session, source, [item])

    updated_source = session.get(Source, source.id)
    assert completed is True
    assert updated_source is not None
    assert updated_source.skip_reason is None


def test_complete_source_processing_rejects_stale_attempt(session: Session) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/STALECOMPLETE/")
    source = claim_source_for_processing(session, saved.source_id)
    assert source is not None
    source_id = source.id
    bind = session.get_bind()

    with Session(bind) as current_session:
        current_source = current_session.get(Source, source_id)
        assert current_source is not None
        current_source.status = SourceStatus.PROCESSING
        current_source.processing_started_at = utc_now() + timedelta(seconds=1)
        current_source.thumbnail_url = "https://cdn.example/current.jpg"
        current_session.add(current_source)
        current_session.commit()

    source.thumbnail_url = "https://cdn.example/stale.jpg"
    item = SourceItem(
        source_id=source_id,
        category="book",
        title="Stale Result",
        author="Old Worker",
        confidence=0.5,
        position=0,
    )

    completed = complete_source_processing(session, source, [item])

    with Session(bind) as check_session:
        refreshed = check_session.get(Source, source_id)
        items = list(
            check_session.exec(select(SourceItem).where(SourceItem.source_id == source_id)).all()
        )
    assert completed is False
    assert refreshed is not None
    assert refreshed.status == SourceStatus.PROCESSING
    assert refreshed.processed_at is None
    assert refreshed.thumbnail_url == "https://cdn.example/current.jpg"
    assert items == []


def test_fail_source_processing_marks_failed_and_sets_error(session: Session) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/ABC123/")
    source = claim_source_for_processing(session, saved.source_id)
    assert source is not None

    failed = fail_source_processing(session, source, "network timeout")

    updated_source = session.get(Source, source.id)
    assert updated_source is not None
    assert failed is True
    assert updated_source.status == SourceStatus.FAILED
    assert updated_source.error_message == "network timeout"
    assert updated_source.processed_at is not None


def test_fail_source_processing_rejects_stale_attempt(session: Session) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/STALEFAIL/")
    source = claim_source_for_processing(session, saved.source_id)
    assert source is not None
    source_id = source.id
    bind = session.get_bind()

    with Session(bind) as current_session:
        current_source = current_session.get(Source, source_id)
        assert current_source is not None
        current_source.status = SourceStatus.DONE
        current_source.processed_at = utc_now()
        current_source.error_message = None
        current_session.add(current_source)
        current_session.commit()

    failed = fail_source_processing(session, source, "old timeout")

    with Session(bind) as check_session:
        refreshed = check_session.get(Source, source_id)
    assert failed is False
    assert refreshed is not None
    assert refreshed.status == SourceStatus.DONE
    assert refreshed.error_message is None


def test_recover_stale_sources_resets_old_processing_sources(session: Session) -> None:
    old_source = Source(
        source_key="instagram:reel:OLD",
        platform="instagram",
        source_type="reel",
        external_id="OLD",
        canonical_url="https://www.instagram.com/reel/OLD/",
        status=SourceStatus.PROCESSING,
        processing_started_at=utc_now() - timedelta(minutes=30),
    )
    fresh_source = Source(
        source_key="instagram:reel:FRESH",
        platform="instagram",
        source_type="reel",
        external_id="FRESH",
        canonical_url="https://www.instagram.com/reel/FRESH/",
        status=SourceStatus.PROCESSING,
        processing_started_at=utc_now(),
    )
    session.add(old_source)
    session.add(fresh_source)
    session.commit()

    recovered = recover_stale_sources(session, stale_timeout_seconds=15 * 60)

    refreshed_old = session.get(Source, old_source.id)
    refreshed_fresh = session.get(Source, fresh_source.id)
    assert recovered == 1
    assert refreshed_old is not None
    assert refreshed_old.status == SourceStatus.PENDING
    assert refreshed_old.processing_started_at is None
    assert refreshed_fresh is not None
    assert refreshed_fresh.status == SourceStatus.PROCESSING
    assert refreshed_fresh.processing_started_at is not None


def test_delete_saved_source_removes_only_saved_source(session: Session) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/ABC123/")
    source_id = saved.source_id

    delete_saved_source(session, saved)

    assert session.get(Source, source_id) is not None
    assert len(list(session.exec(select(SavedSource)).all())) == 0


def test_get_saved_source_by_key_returns_owner_save(session: Session) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/ABC123/")
    save_source_for_user(session, OTHER_OWNER, "https://www.instagram.com/reel/ABC123/")

    found = get_saved_source_by_key(session, OWNER, "instagram:reel:ABC123")

    assert found is not None
    assert found.id == saved.id
    assert get_saved_source_by_key(session, OWNER, "instagram:reel:MISSING") is None


def test_retry_failed_saved_source_requeues_and_clears_failure(
    session: Session, monkeypatch
) -> None:
    enqueued: list[str] = []
    monkeypatch.setattr(
        "src.sources.service.enqueue_source_extraction",
        lambda _session, source_id: enqueued.append(str(source_id)),
    )
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/FAILED/")
    source = session.get(Source, saved.source_id)
    assert source is not None
    source.status = SourceStatus.FAILED
    source.error_message = "network timeout"
    source.processing_started_at = utc_now() - timedelta(minutes=5)
    source.processed_at = utc_now()
    session.add(source)
    session.commit()
    enqueued.clear()

    did_retry = retry_failed_saved_source(session, saved)

    refreshed = session.get(Source, source.id)
    assert refreshed is not None
    assert did_retry is True
    assert refreshed.status == SourceStatus.PENDING
    assert refreshed.error_message is None
    assert refreshed.processing_started_at is None
    assert refreshed.processed_at is None
    refreshed_saved = session.get(SavedSource, saved.id)
    assert refreshed_saved is not None
    assert refreshed_saved.last_retry_at is not None
    assert refreshed_saved.retry_burst_count == 1
    assert refreshed_saved.retry_daily_count == 1
    assert enqueued == [str(source.id)]


def test_retry_failed_saved_source_is_atomic_for_stale_concurrent_callers(
    session: Session, monkeypatch
) -> None:
    enqueued: list[str] = []
    monkeypatch.setattr(
        "src.sources.service.enqueue_source_extraction",
        lambda _session, source_id: enqueued.append(str(source_id)),
    )
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/RACE/")
    source = session.get(Source, saved.source_id)
    assert source is not None
    source.status = SourceStatus.FAILED
    source.error_message = "network timeout"
    session.add(source)
    session.commit()
    saved_id = saved.id
    source_id = source.id
    enqueued.clear()

    bind = session.get_bind()
    with Session(bind) as first_session, Session(bind) as second_session:
        first_saved = first_session.get(SavedSource, saved_id)
        second_saved = second_session.get(SavedSource, saved_id)
        assert first_saved is not None
        assert second_saved is not None
        first_source = first_session.get(Source, source_id)
        second_source = second_session.get(Source, source_id)
        assert first_source is not None
        assert second_source is not None
        assert first_source.status == SourceStatus.FAILED
        assert second_source.status == SourceStatus.FAILED

        first_retry = retry_failed_saved_source(first_session, first_saved)
        second_retry = retry_failed_saved_source(second_session, second_saved)

    assert first_retry is True
    assert second_retry is False
    assert enqueued == [str(source_id)]
    with Session(bind) as check_session:
        checked_saved = check_session.get(SavedSource, saved_id)
        assert checked_saved is not None
        assert checked_saved.retry_burst_count == 1
        assert checked_saved.retry_daily_count == 1


@pytest.mark.parametrize(
    "source_status",
    [SourceStatus.PENDING, SourceStatus.PROCESSING, SourceStatus.DONE],
)
def test_retry_failed_saved_source_does_not_requeue_non_failed_source(
    session: Session,
    monkeypatch,
    source_status: SourceStatus,
) -> None:
    enqueued: list[str] = []
    monkeypatch.setattr(
        "src.sources.service.enqueue_source_extraction",
        lambda _session, source_id: enqueued.append(str(source_id)),
    )
    saved = save_source_for_user(
        session,
        OWNER,
        f"https://www.instagram.com/reel/{source_status.value.upper()}/",
    )
    source = session.get(Source, saved.source_id)
    assert source is not None
    source.status = source_status
    session.add(source)
    session.commit()
    enqueued.clear()

    did_retry = retry_failed_saved_source(session, saved)

    refreshed = session.get(Source, source.id)
    assert refreshed is not None
    assert did_retry is False
    assert refreshed.status == source_status
    assert enqueued == []


def test_count_active_saved_sources(session: Session) -> None:
    pending = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/PENDING/")
    processing = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/PROCESSING/")
    done = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/DONE/")
    other = save_source_for_user(session, OTHER_OWNER, "https://www.instagram.com/reel/OTHER/")

    processing_source = session.get(Source, processing.source_id)
    done_source = session.get(Source, done.source_id)
    other_source = session.get(Source, other.source_id)
    assert processing_source is not None
    assert done_source is not None
    assert other_source is not None
    processing_source.status = SourceStatus.PROCESSING
    done_source.status = SourceStatus.DONE
    other_source.status = SourceStatus.PENDING
    session.add(processing_source)
    session.add(done_source)
    session.add(other_source)
    session.commit()

    assert count_active_saved_sources(session, OWNER) == 2
    assert count_active_saved_sources(session, OTHER_OWNER) == 1
    assert session.get(SavedSource, pending.id) is not None


def test_count_saved_sources_created_since(session: Session) -> None:
    now = utc_now()
    recent = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/RECENT/")
    old = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/OLD/")
    other = save_source_for_user(session, OTHER_OWNER, "https://www.instagram.com/reel/OTHER/")
    old.created_at = now - timedelta(days=2)
    other.created_at = now
    session.add(old)
    session.add(other)
    session.commit()

    assert count_saved_sources_created_since(session, OWNER, now - timedelta(days=1)) == 1
    assert count_saved_sources_created_since(session, OTHER_OWNER, now - timedelta(days=1)) == 1
    assert session.get(SavedSource, recent.id) is not None


def test_count_saved_source_retry_attempts_since_counts_attempt_windows(session: Session) -> None:
    now = utc_now()
    first = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/RETRYCOUNT1/")
    second = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/RETRYCOUNT2/")
    old = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/OLDRETRYCOUNT/")
    other = save_source_for_user(
        session, OTHER_OWNER, "https://www.instagram.com/reel/OTHERRETRYCOUNT/"
    )

    first.retry_burst_started_at = now - timedelta(seconds=20)
    first.retry_burst_count = 2
    first.retry_daily_started_at = now - timedelta(hours=2)
    first.retry_daily_count = 4
    second.retry_burst_started_at = now - timedelta(seconds=10)
    second.retry_burst_count = 1
    second.retry_daily_started_at = now - timedelta(hours=3)
    second.retry_daily_count = 3
    old.retry_burst_started_at = now - timedelta(minutes=2)
    old.retry_burst_count = 5
    old.retry_daily_started_at = now - timedelta(days=2)
    old.retry_daily_count = 10
    other.retry_burst_started_at = now
    other.retry_burst_count = 7
    other.retry_daily_started_at = now
    other.retry_daily_count = 8
    session.add(first)
    session.add(second)
    session.add(old)
    session.add(other)
    session.commit()

    assert (
        count_saved_source_retry_attempts_since(
            session,
            OWNER,
            now - timedelta(minutes=1),
            window="burst",
        )
        == 3
    )
    assert (
        count_saved_source_retry_attempts_since(
            session,
            OWNER,
            now - timedelta(days=1),
            window="daily",
        )
        == 7
    )
