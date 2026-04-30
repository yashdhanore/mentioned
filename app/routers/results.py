from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from app.deps import SessionDep
from app.schemas.results import JobResultResponse
from app.services.job_service import build_job_result, get_job


router = APIRouter(prefix="/v1/jobs", tags=["results"])


JobId = Annotated[str, Path(min_length=1, description="The job ID")]


@router.get("/{job_id}/result", response_model=JobResultResponse)
def get_job_result_endpoint(job_id: JobId, session: SessionDep) -> JobResultResponse:
    job = get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return build_job_result(session, job)

