from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from app.deps import SessionDep
from app.schemas.jobs import CreateJobRequest, JobResponse
from app.services.job_service import create_job, get_job, rerun_job, to_job_response


router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


JobId = Annotated[str, Path(min_length=1, description="The job ID")]


@router.post("/", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job_endpoint(payload: CreateJobRequest, session: SessionDep) -> JobResponse:
    job = create_job(session, str(payload.url))
    return to_job_response(job)


@router.get("/{job_id}", response_model=JobResponse)
def get_job_endpoint(job_id: JobId, session: SessionDep) -> JobResponse:
    job = get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return to_job_response(job)


@router.post("/{job_id}/rerun", response_model=JobResponse)
def rerun_job_endpoint(job_id: JobId, session: SessionDep) -> JobResponse:
    job = get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Running jobs cannot be reset",
        )
    rerun_job(session, job)
    return to_job_response(job)

