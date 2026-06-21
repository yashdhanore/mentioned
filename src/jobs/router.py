from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, status

from src.auth.dependencies import CallerDep
from src.config import get_settings
from src.extraction.url import SourceUrlError, validate_instagram_url
from src.jobs.dependencies import SessionDep, ValidJobDep
from src.jobs.exceptions import JobNotFound, QuotaExceeded, RateLimited
from src.jobs.read_models import job_detail_response, job_list_response
from src.jobs.schemas import (
    CreateJobRequest,
    DeleteJobResponse,
    JobCreatedResponse,
    JobListItem,
    JobResponse,
)
from src.jobs import service as job_service

router = APIRouter(tags=["jobs"])


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
    return job_list_response(session, caller.subject_id)


@router.get("/v1/jobs/{job_id}")
async def get_job(
    job: ValidJobDep,
    session: SessionDep,
) -> JobResponse:
    return job_detail_response(session, job)


@router.delete("/v1/jobs/{job_id}")
async def delete_job(
    job: ValidJobDep,
    session: SessionDep,
) -> DeleteJobResponse:
    job_id = str(job.id)
    job_service.delete_job(session, job)
    return DeleteJobResponse(job_id=job_id)
