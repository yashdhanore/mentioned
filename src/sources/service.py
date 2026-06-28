from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from src.ids import parse_uuid
from src.sources.identity import identify_source
from src.sources.models import SavedSource, Source, SourceItem, SourceStatus
from src.sources.queue import enqueue_source_extraction


def _increment_retry_window(
    window_started_at: datetime | None,
    count: int,
    now: datetime,
    window: timedelta,
) -> tuple[datetime, int]:
    if window_started_at is None or window_started_at < now - window:
        return now, 1
    return window_started_at, count + 1


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


def get_saved_source_by_key(session: Session, owner_id: str, source_key: str) -> SavedSource | None:
    owner_uuid = parse_uuid(owner_id)
    return session.exec(
        select(SavedSource)
        .join(Source, Source.id == SavedSource.source_id)
        .where(SavedSource.owner_id == owner_uuid, Source.source_key == source_key)
    ).first()


def retry_failed_saved_source(session: Session, saved_source: SavedSource) -> bool:
    now = datetime.utcnow()
    stmt = (
        update(Source)
        .where(Source.id == saved_source.source_id, Source.status == SourceStatus.FAILED)
        .values(
            status=SourceStatus.PENDING,
            error_message=None,
            processing_started_at=None,
            processed_at=None,
            updated_at=now,
        )
        .returning(Source.id)
    )
    source_id = session.execute(stmt).scalar_one_or_none()
    if source_id is None:
        session.rollback()
        return False

    saved = session.get(SavedSource, saved_source.id)
    if saved is None:
        session.rollback()
        raise RuntimeError(f"Missing saved source {saved_source.id}")

    retry_burst_started_at, retry_burst_count = _increment_retry_window(
        saved.retry_burst_started_at,
        saved.retry_burst_count,
        now,
        timedelta(minutes=1),
    )
    retry_daily_started_at, retry_daily_count = _increment_retry_window(
        saved.retry_daily_started_at,
        saved.retry_daily_count,
        now,
        timedelta(days=1),
    )
    saved.last_retry_at = now
    saved.retry_burst_started_at = retry_burst_started_at
    saved.retry_burst_count = retry_burst_count
    saved.retry_daily_started_at = retry_daily_started_at
    saved.retry_daily_count = retry_daily_count
    session.add(saved)

    try:
        enqueue_source_extraction(session, source_id)
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(saved_source)
    return True


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


def complete_source_processing(
    session: Session,
    source: Source,
    items: list[SourceItem],
    *,
    skip_reason: str | None = None,
) -> bool:
    now = datetime.utcnow()
    source_id = source.id
    processing_started_at = source.processing_started_at
    creator_handle = source.creator_handle
    thumbnail_url = source.thumbnail_url
    stmt = (
        update(Source)
        .where(
            Source.id == source_id,
            Source.status == SourceStatus.PROCESSING,
            Source.processing_started_at == processing_started_at,
        )
        .values(
            status=SourceStatus.DONE,
            creator_handle=creator_handle,
            thumbnail_url=thumbnail_url,
            error_message=None,
            skip_reason=skip_reason,
            processed_at=now,
            updated_at=now,
        )
        .returning(Source.id)
    )
    with session.no_autoflush:
        completed_id = session.execute(stmt).scalar_one_or_none()
    if completed_id is None:
        session.rollback()
        return False

    session.expire(source)
    session.execute(delete(SourceItem).where(SourceItem.source_id == source_id))
    for item in items:
        item.source_id = source_id
        session.add(item)
    session.commit()
    return True


def fail_source_processing(session: Session, source: Source, error: str) -> bool:
    now = datetime.utcnow()
    source_id = source.id
    processing_started_at = source.processing_started_at
    creator_handle = source.creator_handle
    thumbnail_url = source.thumbnail_url
    stmt = (
        update(Source)
        .where(
            Source.id == source_id,
            Source.status == SourceStatus.PROCESSING,
            Source.processing_started_at == processing_started_at,
        )
        .values(
            status=SourceStatus.FAILED,
            creator_handle=creator_handle,
            thumbnail_url=thumbnail_url,
            error_message=error,
            processed_at=now,
            updated_at=now,
        )
        .returning(Source.id)
    )
    with session.no_autoflush:
        failed_id = session.execute(stmt).scalar_one_or_none()
    if failed_id is None:
        session.rollback()
        return False

    session.expire(source)
    session.commit()
    return True


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


def count_active_saved_sources(session: Session, owner_id: str) -> int:
    owner_uuid = parse_uuid(owner_id)
    stmt = (
        select(func.count())
        .select_from(SavedSource)
        .join(Source, Source.id == SavedSource.source_id)
        .where(
            SavedSource.owner_id == owner_uuid,
            Source.status.in_([SourceStatus.PENDING, SourceStatus.PROCESSING]),
        )
    )
    return int(session.exec(stmt).one())


def count_saved_sources_created_since(session: Session, owner_id: str, since: datetime) -> int:
    owner_uuid = parse_uuid(owner_id)
    stmt = select(func.count()).select_from(SavedSource).where(
        SavedSource.owner_id == owner_uuid,
        SavedSource.created_at >= since,
    )
    return int(session.exec(stmt).one())


def count_saved_source_retry_attempts_since(
    session: Session,
    owner_id: str,
    since: datetime,
    *,
    window: str,
) -> int:
    owner_uuid = parse_uuid(owner_id)
    if window == "burst":
        started_at = SavedSource.retry_burst_started_at
        count = SavedSource.retry_burst_count
    elif window == "daily":
        started_at = SavedSource.retry_daily_started_at
        count = SavedSource.retry_daily_count
    else:
        raise ValueError("retry attempt window must be burst or daily")

    stmt = select(func.coalesce(func.sum(count), 0)).where(
        SavedSource.owner_id == owner_uuid,
        started_at >= since,
    )
    return int(session.exec(stmt).one())
