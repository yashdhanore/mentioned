from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app.deps import CallerDep, SessionDep
from app.schemas.results import JobResultResponse
from app.services.job_coordinator import CoordinatorError, JobCoordinator


router = APIRouter(prefix="/v1/jobs", tags=["results"])

JobId = Annotated[str, Path(min_length=1, description="The job ID")]


def _raise_http(exc: CoordinatorError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"error_code": exc.error_code, "message": str(exc)},
    ) from exc


@router.get("/{job_id}/result", response_model=JobResultResponse)
def get_job_result_endpoint(
    job_id: JobId,
    session: SessionDep,
    caller: CallerDep,
    debug: Annotated[bool, Query()] = False,
) -> JobResultResponse:
    try:
        return JobCoordinator(session).get_result(caller, job_id, include_debug=debug and caller.role == "admin")
    except CoordinatorError as exc:
        _raise_http(exc)
