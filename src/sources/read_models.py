from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from src.ids import parse_uuid
from src.sources.models import SavedSource, Source, SourceItem, SourceStatus
from src.sources.schemas import SavedSourceResponse, SourceItemResponse


def _app_status(source_status: str) -> str:
    if source_status in {SourceStatus.PENDING, SourceStatus.PROCESSING}:
        return "processing"
    if source_status == SourceStatus.DONE:
        return "done"
    return "failed"


def _source_items_response(session: Session, source_id: UUID) -> list[SourceItemResponse]:
    items = list(
        session.exec(
            select(SourceItem)
            .where(SourceItem.source_id == source_id)
            .order_by(SourceItem.position)
        ).all()
    )
    return [
        SourceItemResponse(
            id=str(item.id),
            book_id=str(item.book_id) if item.book_id else None,
            title=item.title,
            author=item.author,
            category=item.category,
            confidence=item.confidence,
            google_books_url=item.google_books_url,
            cover_image_url=item.cover_image_url,
            position=item.position,
        )
        for item in items
    ]


def saved_source_response(session: Session, saved_source: SavedSource) -> SavedSourceResponse:
    source = session.get(Source, saved_source.source_id)
    if source is None:
        raise RuntimeError(f"Saved source {saved_source.id} points to missing source {saved_source.source_id}")
    return SavedSourceResponse(
        id=str(saved_source.id),
        source_id=str(source.id),
        source_key=source.source_key,
        status=_app_status(source.status),
        source_url=source.canonical_url,
        thumbnail_url=source.thumbnail_url,
        source_creator_handle=source.creator_handle,
        error_message=source.error_message,
        skip_reason=source.skip_reason,
        created_at=saved_source.created_at,
        items=_source_items_response(session, source.id),
    )


def saved_source_list_response(session: Session, owner_id: str, limit: int = 50) -> list[SavedSourceResponse]:
    owner_uuid = parse_uuid(owner_id)
    saved_sources = list(
        session.exec(
            select(SavedSource)
            .where(SavedSource.owner_id == owner_uuid)
            .order_by(SavedSource.created_at.desc())
            .limit(limit)
        ).all()
    )
    return [saved_source_response(session, saved_source) for saved_source in saved_sources]
