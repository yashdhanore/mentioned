from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import pytest
from sqlmodel import Session, select

from src.sources.models import SavedSource, Source, SourceItem, SourceStatus
from src.sources.service import (
    _increment_retry_window,
    claim_source_for_processing,
    complete_source_processing,
    count_saved_source_retry_attempts_since,
    fail_source_processing,
    fail_source_processing_forcibly,
    recover_stale_sources,
    retry_failed_saved_source,
    save_source_for_user,
)
from src.timeutils import utc_now

OWNER = "00000000-0000-4000-8000-000000000001"
OTHER_OWNER = "00000000-0000-4000-8000-000000000002"


@pytest.fixture
def enqueued(monkeypatch) -> list[str]:
    enqueued: list[str] = []
    monkeypatch.setattr(
        "src.sources.service.enqueue_source_extraction",
        lambda _session, source_id: enqueued.append(str(source_id)),
    )
    return enqueued


def test_increment_retry_window_keeps_window_when_recent() -> None:
    now = utc_now()
    started_at = now - timedelta(seconds=10)

    result_started_at, count = _increment_retry_window(
        started_at,
        2,
        now,
        timedelta(minutes=1),
    )

    assert count == 3
    assert result_started_at == started_at
    assert result_started_at.tzinfo is not None


def test_increment_retry_window_resets_when_stale() -> None:
    now = utc_now()
    started_at = now - timedelta(minutes=5)

    result_started_at, count = _increment_retry_window(
        started_at,
        9,
        now,
        timedelta(minutes=1),
    )

    assert count == 1
    assert result_started_at == now


def test_save_source_for_user_rolls_back_when_enqueue_fails(session: Session, monkeypatch) -> None:
    def fail_enqueue(_session: Session, _source_id: UUID) -> None:
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr("src.sources.service.enqueue_source_extraction", fail_enqueue)

    with pytest.raises(RuntimeError, match="queue unavailable"):
        save_source_for_user(session, OWNER, "https://www.instagram.com/reel/ABC123/")

    assert len(list(session.exec(select(Source)).all())) == 0
    assert len(list(session.exec(select(SavedSource)).all())) == 0


def test_claim_source_for_processing_claims_only_pending_source(session: Session) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/ABC123/")

    claimed = claim_source_for_processing(session, saved.source_id)
    second_claim = claim_source_for_processing(session, saved.source_id)

    assert claimed is not None
    assert claimed.status == SourceStatus.PROCESSING
    assert claimed.processing_started_at is not None
    assert second_claim is None


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


def test_fail_source_processing_forcibly_fails_pending_source(session: Session) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/FORCEPEND/")

    failed = fail_source_processing_forcibly(session, saved.source_id, "poison message")

    updated_source = session.get(Source, saved.source_id)
    assert failed is True
    assert updated_source is not None
    assert updated_source.status == SourceStatus.FAILED
    assert updated_source.error_message == "poison message"


def test_fail_source_processing_forcibly_fails_processing_source_without_matching_attempt(
    session: Session,
) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/FORCEPROC/")
    source = claim_source_for_processing(session, saved.source_id)
    assert source is not None

    failed = fail_source_processing_forcibly(session, saved.source_id, "poison message")

    updated_source = session.get(Source, saved.source_id)
    assert failed is True
    assert updated_source is not None
    assert updated_source.status == SourceStatus.FAILED
    assert updated_source.error_message == "poison message"


def test_fail_source_processing_forcibly_never_clobbers_a_done_source(session: Session) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/FORCEDONE/")
    source = claim_source_for_processing(session, saved.source_id)
    assert source is not None
    complete_source_processing(session, source, [])

    failed = fail_source_processing_forcibly(session, saved.source_id, "poison message")

    updated_source = session.get(Source, saved.source_id)
    assert failed is False
    assert updated_source is not None
    assert updated_source.status == SourceStatus.DONE
    assert updated_source.error_message is None


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


def test_retry_failed_saved_source_is_atomic_for_stale_concurrent_callers(
    session: Session, enqueued: list[str]
) -> None:
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
