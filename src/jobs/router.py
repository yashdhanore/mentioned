from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlmodel import select

from src.auth.dependencies import CallerDep
from src.config import get_settings
from src.extraction.url import SourceUrlError, validate_instagram_url
from src.ids import parse_uuid
from src.jobs.dependencies import SessionDep, ValidJobDep
from src.jobs.exceptions import JobNotFound, QuotaExceeded, RateLimited
from src.jobs.models import Job
from src.jobs.schemas import (
    CreateJobRequest,
    JobCreatedResponse,
    JobListItem,
    JobResponse,
    MentionInJob,
)
from src.jobs import service as job_service
from src.mentions.models import Mention

router = APIRouter(tags=["jobs"])
THUMBNAIL_PROXY_ALLOWED_HOST_SUFFIXES = (".fbcdn.net", ".cdninstagram.com")


def _is_allowed_thumbnail_url(url: str) -> bool:
    parsed = urlparse(url)
    hostname = parsed.hostname
    if parsed.scheme != "https" or not hostname:
        return False
    if parsed.port not in (None, 443):
        return False
    return any(
        hostname == suffix.removeprefix(".") or hostname.endswith(suffix)
        for suffix in THUMBNAIL_PROXY_ALLOWED_HOST_SUFFIXES
    )


@router.post("/v1/jobs", status_code=status.HTTP_202_ACCEPTED)
def create_job(
    body: CreateJobRequest,
    caller: CallerDep,
    session: SessionDep,
) -> JobCreatedResponse:
    settings = get_settings()
    try:
        source_url = validate_instagram_url(
            body.url, require_https=settings.source_require_https
        )
    except SourceUrlError as exc:
        raise JobNotFound() from exc  # reuse 400-level error

    active = job_service.count_active_jobs(session, caller.subject_id)
    if active >= settings.max_active_jobs_per_user:
        raise QuotaExceeded()

    now = datetime.now(timezone.utc)
    burst_count = job_service.count_jobs_created_since(
        session, caller.subject_id, now - timedelta(minutes=1)
    )
    if burst_count >= settings.max_job_create_burst_per_minute:
        raise RateLimited()

    daily_count = job_service.count_jobs_created_since(
        session, caller.subject_id, now - timedelta(days=1)
    )
    if daily_count >= settings.max_jobs_created_per_day:
        raise QuotaExceeded()

    job = job_service.create_queued_job(session, caller.subject_id, source_url)
    return JobCreatedResponse(job_id=str(job.id), status=job.status)


@router.get("/v1/jobs")
async def list_jobs(
    caller: CallerDep,
    session: SessionDep,
) -> list[JobListItem]:
    stmt = (
        select(Job)
        .where(Job.owner_id == parse_uuid(caller.subject_id))
        .order_by(Job.created_at.desc())
        .limit(50)
    )
    jobs = list(session.exec(stmt).all())
    return [
        JobListItem(
            job_id=str(j.id),
            status=j.status,
            source_url=j.source_url,
            thumbnail_url=j.thumbnail_url,
            created_at=j.created_at,
        )
        for j in jobs
    ]


@router.get("/v1/thumbnail-proxy", include_in_schema=False)
async def proxy_thumbnail(
    url: Annotated[str, Query(min_length=1, max_length=4096)],
) -> Response:
    if not _is_allowed_thumbnail_url(url):
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            upstream = await client.get(url)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=404, detail="Thumbnail not found") from exc

    content_type = upstream.headers.get("content-type", "").split(";", 1)[0].strip()
    if upstream.status_code != 200 or not content_type.startswith("image/"):
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    return Response(
        content=upstream.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/v1/jobs/{job_id}")
async def get_job(
    job: ValidJobDep,
    session: SessionDep,
) -> JobResponse:
    mentions = list(
        session.exec(
            select(Mention).where(Mention.job_id == job.id, Mention.is_deleted == False)
        ).all()
    )
    return JobResponse(
        job_id=str(job.id),
        status=job.status,
        source_url=job.source_url,
        thumbnail_url=job.thumbnail_url,
        error_message=job.error_message,
        created_at=job.created_at,
        finished_at=job.finished_at,
        mentions=[
            MentionInJob(
                id=str(m.id),
                book_id=str(m.book_id) if m.book_id else None,
                title=m.title,
                author=m.author,
                category=m.category,
                confidence=m.confidence,
                google_books_url=m.google_books_url,
                cover_image_url=m.cover_image_url,
            )
            for m in mentions
        ],
    )
