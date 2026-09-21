from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Query, status
from sqlmodel import Session

from src.auth.dependencies import AuthenticatedSessionDep as SessionDep
from src.auth.dependencies import CallerDep
from src.config import Settings, get_settings
from src.extraction.url import SourceUrlError
from src.ids import parse_uuid
from src.sources import service as source_service
from src.sources.exceptions import InvalidSourceUrl, QuotaExceeded, RateLimited, SavedSourceNotFound
from src.sources.identity import identify_source
from src.sources.models import SavedSource, Source, SourceStatus
from src.sources.read_models import saved_source_list_response, saved_source_response
from src.sources.schemas import (
    CreateSavedSourceRequest,
    DeleteSavedSourceResponse,
    SavedSourceResponse,
)
from src.timeutils import utc_now

router = APIRouter(tags=["saved-sources"])


def _enforce_source_quota(
    session: Session,
    settings: Settings,
    owner_id: str,
    *,
    include_retries: bool,
) -> None:
    active = source_service.count_active_saved_sources(session, owner_id)
    if active >= settings.max_active_jobs_per_user:
        raise QuotaExceeded()

    now = utc_now()
    burst_count = source_service.count_saved_sources_created_since(
        session, owner_id, now - timedelta(minutes=1)
    )
    daily_count = source_service.count_saved_sources_created_since(
        session, owner_id, now - timedelta(days=1)
    )
    if include_retries:
        burst_count += source_service.count_saved_source_retry_attempts_since(
            session, owner_id, now - timedelta(minutes=1), window="burst"
        )
        daily_count += source_service.count_saved_source_retry_attempts_since(
            session, owner_id, now - timedelta(days=1), window="daily"
        )

    if burst_count >= settings.max_job_create_burst_per_minute:
        raise RateLimited()
    if daily_count >= settings.max_jobs_created_per_day:
        raise QuotaExceeded()


@router.post("/v1/saved-sources", status_code=status.HTTP_202_ACCEPTED)
def create_saved_source(
    body: CreateSavedSourceRequest,
    caller: CallerDep,
    session: SessionDep,
) -> SavedSourceResponse:
    settings = get_settings()
    try:
        identity = identify_source(body.url, require_https=settings.source_require_https)
    except SourceUrlError as exc:
        raise InvalidSourceUrl() from exc

    existing = source_service.get_saved_source_by_key(
        session, caller.subject_id, identity.source_key
    )
    if existing is not None:
        source = session.get(Source, existing.source_id)
        if source is not None and source.status == SourceStatus.FAILED:
            _enforce_source_quota(session, settings, caller.subject_id, include_retries=True)
            source_service.retry_failed_saved_source(session, existing)
        return saved_source_response(session, existing)

    _enforce_source_quota(session, settings, caller.subject_id, include_retries=False)

    try:
        saved = source_service.save_source_for_user(
            session, caller.subject_id, body.url, require_https=settings.source_require_https
        )
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
