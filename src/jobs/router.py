from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, status
from sqlmodel import select

from src.auth.dependencies import CallerDep
from src.config import get_settings
from src.extraction.url import SourceUrlError, validate_instagram_url
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
from src.jobs.service import count_active_jobs, count_jobs_created_since, create_job
from src.mentions.models import Mention

router = APIRouter(tags=["jobs"])


@router.post("/v1/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_job_endpoint(
    body: CreateJobRequest,
    caller: CallerDep,
    session: SessionDep,
) -> JobCreatedResponse:
    settings = get_settings()
    try:
        source_url = validate_instagram_url(body.url, require_https=settings.source_require_https)
    except SourceUrlError as exc:
        raise JobNotFound() from exc  # reuse 400-level error

    active = count_active_jobs(session, caller.subject_id)
    if active >= settings.max_active_jobs_per_user:
        raise QuotaExceeded()

    now = datetime.utcnow()
    burst_count = count_jobs_created_since(session, caller.subject_id, now - timedelta(minutes=1))
    if burst_count >= settings.max_job_create_burst_per_minute:
        raise RateLimited()

    daily_count = count_jobs_created_since(session, caller.subject_id, now - timedelta(days=1))
    if daily_count >= settings.max_jobs_created_per_day:
        raise QuotaExceeded()

    job = create_job(session, caller.subject_id, source_url)
    return JobCreatedResponse(job_id=job.id, status=job.status)


@router.get("/v1/jobs")
async def list_jobs_endpoint(
    caller: CallerDep,
    session: SessionDep,
) -> list[JobListItem]:
    stmt = (
        select(Job)
        .where(Job.owner_id == caller.subject_id)
        .order_by(Job.created_at.desc())
        .limit(50)
    )
    jobs = list(session.exec(stmt).all())
    return [
        JobListItem(
            job_id=j.id,
            status=j.status,
            source_url=j.source_url,
            created_at=j.created_at,
        )
        for j in jobs
    ]


@router.get("/v1/jobs/{job_id}")
async def get_job_endpoint(
    job: ValidJobDep,
    session: SessionDep,
) -> JobResponse:
    mentions = list(
        session.exec(
            select(Mention).where(Mention.job_id == job.id, Mention.is_deleted == False)
        ).all()
    )
    return JobResponse(
        job_id=job.id,
        status=job.status,
        source_url=job.source_url,
        error_message=job.error_message,
        created_at=job.created_at,
        finished_at=job.finished_at,
        mentions=[
            MentionInJob(
                id=m.id,
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
