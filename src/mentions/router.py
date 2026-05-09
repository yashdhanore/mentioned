from __future__ import annotations

from fastapi import APIRouter, Query

from src.auth.dependencies import CallerDep
from src.mentions.dependencies import SessionDep, ValidMentionDep
from src.mentions.schemas import (
    DeleteMentionResponse,
    MentionListResponse,
    MentionResponse,
    UpdateMentionRequest,
)
from src.mentions.service import delete_mention, list_mentions, update_mention

router = APIRouter(tags=["mentions"])


@router.get("/v1/mentions")
async def list_mentions_endpoint(
    caller: CallerDep,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> MentionListResponse:
    mentions = list_mentions(session, caller.subject_id, limit=limit, cursor=cursor)
    items = [
        MentionResponse(
            id=str(m.id),
            title=m.title,
            author=m.author,
            category=m.category,
            confidence=m.confidence,
            google_books_url=m.google_books_url,
            cover_image_url=m.cover_image_url,
            source_url=m.source_url,
            created_at=m.created_at,
        )
        for m in mentions
    ]
    next_cursor = items[-1].id if len(items) == limit else None
    return MentionListResponse(items=items, next_cursor=next_cursor)


@router.patch("/v1/mentions/{mention_id}")
async def update_mention_endpoint(
    mention: ValidMentionDep,
    body: UpdateMentionRequest,
    session: SessionDep,
) -> MentionResponse:
    fields = body.model_dump(exclude_unset=True)
    updated = update_mention(session, mention, **fields)
    return MentionResponse(
        id=str(updated.id),
        title=updated.title,
        author=updated.author,
        category=updated.category,
        confidence=updated.confidence,
        google_books_url=updated.google_books_url,
        cover_image_url=updated.cover_image_url,
        source_url=updated.source_url,
        created_at=updated.created_at,
    )


@router.delete("/v1/mentions/{mention_id}")
async def delete_mention_endpoint(
    mention: ValidMentionDep,
    session: SessionDep,
) -> DeleteMentionResponse:
    delete_mention(session, mention)
    return DeleteMentionResponse(id=str(mention.id))
