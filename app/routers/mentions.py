from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app.deps import CallerDep, SessionDep
from app.schemas.mentions import SavedMentionListResponse, SavedMentionResponse, UpdateSavedMentionRequest
from app.services.job_coordinator import CoordinatorError, JobCoordinator


router = APIRouter(prefix="/v1/mentions", tags=["mentions"])

MentionId = Annotated[str, Path(min_length=1, description="The saved mention ID")]


def _raise_http(exc: CoordinatorError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"error_code": exc.error_code, "message": str(exc)},
    ) from exc


@router.get("", response_model=SavedMentionListResponse)
def list_mentions_endpoint(
    session: SessionDep,
    caller: CallerDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    review_status: Annotated[str | None, Query()] = None,
    save_state: Annotated[str, Query()] = "active",
    source_creator: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    sort: Annotated[str, Query()] = "created_desc",
) -> SavedMentionListResponse:
    return JobCoordinator(session).list_mentions(
        caller,
        limit=limit,
        cursor=cursor,
        category=category,
        review_status=review_status,
        save_state=save_state,
        source_creator=source_creator,
        q=q,
        sort=sort,
    )


@router.get("/{mention_id}", response_model=SavedMentionResponse)
def get_mention_endpoint(mention_id: MentionId, session: SessionDep, caller: CallerDep) -> SavedMentionResponse:
    try:
        return JobCoordinator(session).get_mention(caller, mention_id)
    except CoordinatorError as exc:
        _raise_http(exc)


@router.patch("/{mention_id}", response_model=SavedMentionResponse)
def update_mention_endpoint(
    mention_id: MentionId,
    payload: UpdateSavedMentionRequest,
    session: SessionDep,
    caller: CallerDep,
) -> SavedMentionResponse:
    try:
        return JobCoordinator(session).update_mention(
            caller,
            mention_id,
            display_label=payload.display_label,
            display_author_or_creator=payload.display_author_or_creator,
            display_description=payload.display_description,
            category=payload.category,
        )
    except CoordinatorError as exc:
        _raise_http(exc)


@router.post("/{mention_id}/confirm", response_model=SavedMentionResponse)
def confirm_mention_endpoint(mention_id: MentionId, session: SessionDep, caller: CallerDep) -> SavedMentionResponse:
    try:
        return JobCoordinator(session).confirm_mention(caller, mention_id)
    except CoordinatorError as exc:
        _raise_http(exc)


@router.delete("/{mention_id}", response_model=SavedMentionResponse)
def delete_mention_endpoint(mention_id: MentionId, session: SessionDep, caller: CallerDep) -> SavedMentionResponse:
    try:
        return JobCoordinator(session).delete_mention(caller, mention_id)
    except CoordinatorError as exc:
        _raise_http(exc)
