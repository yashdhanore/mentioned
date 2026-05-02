from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.deps import CallerDep, SessionDep
from app.schemas.jobs import CreateJobRequest, JobListResponse, JobResponse
from app.services.job_coordinator import CoordinatorError, JobCoordinator


router = APIRouter(prefix="/v1/jobs", tags=["jobs"])

JobId = Annotated[str, Path(min_length=1, description="The job ID")]


def _raise_http(exc: CoordinatorError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"error_code": exc.error_code, "message": str(exc)},
    ) from exc


@router.post("", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job_endpoint(payload: CreateJobRequest, session: SessionDep, caller: CallerDep) -> JobResponse:
    try:
        return JobCoordinator(session).create_job(caller, payload.url, payload.idempotency_key)
    except CoordinatorError as exc:
        _raise_http(exc)


@router.get("", response_model=JobListResponse)
def list_jobs_endpoint(
    session: SessionDep,
    caller: CallerDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> JobListResponse:
    return JobCoordinator(session).list_jobs(caller, limit=limit, cursor=cursor)


@router.get("/{job_id}", response_model=JobResponse)
def get_job_endpoint(job_id: JobId, session: SessionDep, caller: CallerDep) -> JobResponse:
    try:
        return JobCoordinator(session).get_job(caller, job_id)
    except CoordinatorError as exc:
        _raise_http(exc)


@router.post("/{job_id}/rerun", response_model=JobResponse)
def rerun_job_endpoint(job_id: JobId, session: SessionDep, caller: CallerDep) -> JobResponse:
    try:
        return JobCoordinator(session).rerun_job(caller, job_id)
    except CoordinatorError as exc:
        _raise_http(exc)


@router.post("/{job_id}/cancel", response_model=JobResponse)
def cancel_job_endpoint(job_id: JobId, session: SessionDep, caller: CallerDep) -> JobResponse:
    try:
        return JobCoordinator(session).cancel_job(caller, job_id)
    except CoordinatorError as exc:
        _raise_http(exc)
