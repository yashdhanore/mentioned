from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from src.ids import parse_uuid
from src.sources.identity import identify_source
from src.sources.models import SavedSource, Source, SourceItem, SourceStatus
from src.sources.queue import enqueue_source_extraction


def save_source_for_user(session: Session, owner_id: str, raw_url: str) -> SavedSource:
    for attempt in range(2):
        try:
            return _save_source_for_user_once(session, owner_id, raw_url)
        except IntegrityError:
            session.rollback()
            if attempt == 1:
                raise
        except Exception:
            session.rollback()
            raise
    raise RuntimeError("Could not save source after retry")


def _save_source_for_user_once(session: Session, owner_id: str, raw_url: str) -> SavedSource:
    owner_uuid = parse_uuid(owner_id)
    identity = identify_source(raw_url, require_https=False)
    should_enqueue = False

    source = session.exec(select(Source).where(Source.source_key == identity.source_key)).first()
    if source is None:
        source = Source(
            source_key=identity.source_key,
            platform=identity.platform,
            source_type=identity.source_type,
            external_id=identity.external_id,
            canonical_url=identity.canonical_url,
            status=SourceStatus.PENDING,
        )
        session.add(source)
        session.flush()
        should_enqueue = True

    saved = session.exec(
        select(SavedSource).where(
            SavedSource.owner_id == owner_uuid,
            SavedSource.source_id == source.id,
        )
    ).first()
    if saved is None:
        saved = SavedSource(owner_id=owner_uuid, source_id=source.id)
        session.add(saved)
        session.flush()

    if should_enqueue:
        enqueue_source_extraction(session, source.id)

    session.commit()
    session.refresh(saved)
    return saved


def claim_source_for_processing(session: Session, source_id: str | UUID) -> Source | None:
    parsed_source_id = parse_uuid(source_id)
    now = datetime.utcnow()
    stmt = (
        update(Source)
        .where(Source.id == parsed_source_id, Source.status == SourceStatus.PENDING)
        .values(status=SourceStatus.PROCESSING, processing_started_at=now, updated_at=now)
        .returning(Source.id)
    )
    claimed_id = session.execute(stmt).scalar_one_or_none()
    if claimed_id is None:
        session.rollback()
        return None
    session.commit()
    return session.get(Source, claimed_id)


def complete_source_processing(session: Session, source: Source, items: list[SourceItem]) -> None:
    now = datetime.utcnow()
    source.status = SourceStatus.DONE
    source.error_message = None
    source.processed_at = now
    source.updated_at = now
    session.add(source)
    for item in items:
        session.add(item)
    session.commit()


def fail_source_processing(session: Session, source: Source, error: str) -> None:
    now = datetime.utcnow()
    source.status = SourceStatus.FAILED
    source.error_message = error
    source.processed_at = now
    source.updated_at = now
    session.add(source)
    session.commit()


def recover_stale_sources(session: Session, stale_timeout_seconds: int = 900) -> int:
    cutoff = datetime.utcnow() - timedelta(seconds=stale_timeout_seconds)
    stmt = select(Source).where(
        Source.status == SourceStatus.PROCESSING,
        Source.processing_started_at < cutoff,
    )
    stale_sources = list(session.exec(stmt).all())
    for source in stale_sources:
        source.status = SourceStatus.PENDING
        source.processing_started_at = None
        source.updated_at = datetime.utcnow()
        session.add(source)
    if stale_sources:
        session.commit()
    return len(stale_sources)


def delete_saved_source(session: Session, saved_source: SavedSource) -> None:
    session.delete(saved_source)
    session.commit()
