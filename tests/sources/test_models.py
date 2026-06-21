from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from src.sources.models import SavedSource, Source, SourceItem, SourceStatus


OWNER = UUID("00000000-0000-4000-8000-000000000001")


def test_source_saved_source_and_items_round_trip(session: Session) -> None:
    source = Source(
        source_key="instagram:reel:ABC123",
        platform="instagram",
        source_type="reel",
        external_id="ABC123",
        canonical_url="https://www.instagram.com/reel/ABC123/",
        status=SourceStatus.DONE,
    )
    session.add(source)
    session.commit()
    session.refresh(source)

    item = SourceItem(
        source_id=source.id,
        category="book",
        title="Atomic Habits",
        author="James Clear",
        confidence=0.91,
        position=0,
    )
    saved = SavedSource(owner_id=OWNER, source_id=source.id)
    session.add(item)
    session.add(saved)
    session.commit()

    assert (
        session.exec(select(Source).where(Source.source_key == "instagram:reel:ABC123")).one().id
        == source.id
    )
    assert (
        session.exec(select(SourceItem).where(SourceItem.source_id == source.id)).one().title
        == "Atomic Habits"
    )
    assert (
        session.exec(select(SavedSource).where(SavedSource.owner_id == OWNER)).one().source_id
        == source.id
    )


def test_saved_source_rejects_duplicate_owner_source(session: Session) -> None:
    source = Source(
        source_key="instagram:reel:DUPLICATE",
        platform="instagram",
        source_type="reel",
        external_id="DUPLICATE",
        canonical_url="https://www.instagram.com/reel/DUPLICATE/",
        status=SourceStatus.DONE,
    )
    session.add(source)
    session.commit()
    session.refresh(source)

    session.add(SavedSource(owner_id=OWNER, source_id=source.id))
    session.add(SavedSource(owner_id=OWNER, source_id=source.id))

    with pytest.raises(IntegrityError):
        session.commit()
