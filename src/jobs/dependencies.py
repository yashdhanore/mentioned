from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from src.auth.dependencies import AuthenticatedSessionDep, CallerDep
from src.jobs.exceptions import JobNotFound
from src.jobs.models import Job

SessionDep = AuthenticatedSessionDep


async def valid_job_id(job_id: str, caller: CallerDep, session: SessionDep) -> Job:
    job = session.get(Job, job_id)
    if not job or job.owner_id != caller.subject_id:
        raise JobNotFound()
    return job


ValidJobDep = Annotated[Job, Depends(valid_job_id)]
