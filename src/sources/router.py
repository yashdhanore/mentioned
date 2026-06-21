from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, status

from src.auth.dependencies import CallerDep
from src.config import get_settings
from src.extraction.url import SourceUrlError
from src.ids import parse_uuid
from src.jobs.dependencies import SessionDep
from src.jobs.exceptions import QuotaExceeded, RateLimited
from src.sources import service as source_service
from src.sources.exceptions import InvalidSourceUrl, SavedSourceNotFound
from src.sources.identity import identify_source
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
        identity = identify_source(body.url, require_https=False)
    except SourceUrlError as exc:
        raise InvalidSourceUrl() from exc

    existing = source_service.get_saved_source_by_key(
        session, caller.subject_id, identity.source_key
    )
    if existing is not None:
        return saved_source_response(session, existing)

    settings = get_settings()
    active = source_service.count_active_saved_sources(session, caller.subject_id)
    if active >= settings.max_active_jobs_per_user:
        raise QuotaExceeded()

    now = datetime.now(timezone.utc)
    burst_count = source_service.count_saved_sources_created_since(
        session, caller.subject_id, now - timedelta(minutes=1)
    )
    if burst_count >= settings.max_job_create_burst_per_minute:
        raise RateLimited()

    daily_count = source_service.count_saved_sources_created_since(
        session, caller.subject_id, now - timedelta(days=1)
    )
    if daily_count >= settings.max_jobs_created_per_day:
        raise QuotaExceeded()

    try:
        saved = source_service.save_source_for_user(session, caller.subject_id, body.url)
    except SourceUrlError as exc:
        raise InvalidSourceUrl() from exc
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
        raise SavedSourceNotFound() from exc

    saved = session.get(SavedSource, saved_uuid)
    if saved is None or saved.owner_id != caller_uuid:
        raise SavedSourceNotFound()
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
        raise SavedSourceNotFound() from exc

    saved = session.get(SavedSource, saved_uuid)
    if saved is None or saved.owner_id != caller_uuid:
        raise SavedSourceNotFound()

    source_service.delete_saved_source(session, saved)
    return DeleteSavedSourceResponse(id=saved_source_id)
