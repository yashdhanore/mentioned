from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from src.sources.models import SavedSource, Source, SourceItem, SourceStatus
from src.sources.service import (
    claim_source_for_processing,
    complete_source_processing,
    count_active_saved_sources,
    count_saved_sources_created_since,
    delete_saved_source,
    fail_source_processing,
    recover_stale_sources,
    save_source_for_user,
)


OWNER = "00000000-0000-4000-8000-000000000001"
OWNER_UUID = UUID(OWNER)
OTHER_OWNER = "00000000-0000-4000-8000-000000000002"


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


def test_save_source_for_user_rolls_back_when_enqueue_fails(
    session: Session, monkeypatch
) -> None:
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

    complete_source_processing(session, source, [item])

    updated_source = session.get(Source, source.id)
    assert updated_source is not None
    assert updated_source.status == SourceStatus.DONE
    assert updated_source.error_message is None
    assert updated_source.processed_at is not None
    persisted_item = session.exec(
        select(SourceItem).where(SourceItem.source_id == source.id)
    ).one()
    assert persisted_item.title == "Atomic Habits"


def test_fail_source_processing_marks_failed_and_sets_error(session: Session) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/ABC123/")
    source = claim_source_for_processing(session, saved.source_id)
    assert source is not None

    fail_source_processing(session, source, "network timeout")

    updated_source = session.get(Source, source.id)
    assert updated_source is not None
    assert updated_source.status == SourceStatus.FAILED
    assert updated_source.error_message == "network timeout"
    assert updated_source.processed_at is not None


def test_recover_stale_sources_resets_old_processing_sources(session: Session) -> None:
    old_source = Source(
        source_key="instagram:reel:OLD",
        platform="instagram",
        source_type="reel",
        external_id="OLD",
        canonical_url="https://www.instagram.com/reel/OLD/",
        status=SourceStatus.PROCESSING,
        processing_started_at=datetime.utcnow() - timedelta(minutes=30),
    )
    fresh_source = Source(
        source_key="instagram:reel:FRESH",
        platform="instagram",
        source_type="reel",
        external_id="FRESH",
        canonical_url="https://www.instagram.com/reel/FRESH/",
        status=SourceStatus.PROCESSING,
        processing_started_at=datetime.utcnow(),
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
    now = datetime.utcnow()
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
