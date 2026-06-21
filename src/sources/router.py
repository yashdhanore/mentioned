from __future__ import annotations

from fastapi import APIRouter, Query, status

from src.auth.dependencies import CallerDep
from src.extraction.url import SourceUrlError
from src.ids import parse_uuid
from src.jobs.dependencies import SessionDep
from src.jobs.exceptions import JobNotFound
from src.sources import service as source_service
from src.sources.models import SavedSource
from src.sources.read_models import saved_source_list_response, saved_source_response
from src.sources.schemas import (
    CreateSavedSourceRequest,
    DeleteSavedSourceResponse,
    SavedSourceResponse,
)


router = APIRouter(tags=["saved-sources"])


@router.post("/v1/saved-sources", status_code=status.HTTP_202_ACCEPTED)
def create_saved_source(
    body: CreateSavedSourceRequest,
    caller: CallerDep,
    session: SessionDep,
) -> SavedSourceResponse:
    try:
        saved = source_service.save_source_for_user(session, caller.subject_id, body.url)
    except SourceUrlError as exc:
        raise JobNotFound() from exc
    return saved_source_response(session, saved)


@router.get("/v1/saved-sources")
def list_saved_sources(
    caller: CallerDep,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[SavedSourceResponse]:
    return saved_source_list_response(session, caller.subject_id, limit=limit)


@router.get("/v1/saved-sources/{saved_source_id}")
def get_saved_source(
    saved_source_id: str,
    caller: CallerDep,
    session: SessionDep,
) -> SavedSourceResponse:
    try:
        saved_uuid = parse_uuid(saved_source_id)
        caller_uuid = parse_uuid(caller.subject_id)
    except ValueError as exc:
        raise JobNotFound() from exc

    saved = session.get(SavedSource, saved_uuid)
    if saved is None or saved.owner_id != caller_uuid:
        raise JobNotFound()
    return saved_source_response(session, saved)


@router.delete("/v1/saved-sources/{saved_source_id}")
def delete_saved_source(
    saved_source_id: str,
    caller: CallerDep,
    session: SessionDep,
) -> DeleteSavedSourceResponse:
    try:
        saved_uuid = parse_uuid(saved_source_id)
        caller_uuid = parse_uuid(caller.subject_id)
    except ValueError as exc:
        raise JobNotFound() from exc

    saved = session.get(SavedSource, saved_uuid)
    if saved is None or saved.owner_id != caller_uuid:
        raise JobNotFound()

    source_service.delete_saved_source(session, saved)
    return DeleteSavedSourceResponse(id=saved_source_id)
