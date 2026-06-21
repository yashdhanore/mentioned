from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from src.sources.models import SavedSource, Source, SourceStatus
from src.sources.service import claim_source_for_processing, save_source_for_user


OWNER = "00000000-0000-4000-8000-000000000001"
OWNER_UUID = UUID(OWNER)


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


def test_claim_source_for_processing_claims_only_pending_source(session: Session) -> None:
    saved = save_source_for_user(session, OWNER, "https://www.instagram.com/reel/ABC123/")

    claimed = claim_source_for_processing(session, saved.source_id)
    second_claim = claim_source_for_processing(session, saved.source_id)

    assert claimed is not None
    assert claimed.status == SourceStatus.PROCESSING
    assert claimed.processing_started_at is not None
    assert second_claim is None
