from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from src.auth.dependencies import AuthenticatedSessionDep, CallerDep
from src.jobs.exceptions import JobNotFound
from src.jobs.models import Job
from src.ids import parse_uuid

SessionDep = AuthenticatedSessionDep


async def valid_job_id(job_id: str, caller: CallerDep, session: SessionDep) -> Job:
    try:
        job_uuid = parse_uuid(job_id)
        caller_uuid = parse_uuid(caller.subject_id)
    except ValueError as exc:
        raise JobNotFound() from exc
    job = session.get(Job, job_uuid)
    if not job or job.owner_id != caller_uuid:
        raise JobNotFound()
    return job


ValidJobDep = Annotated[Job, Depends(valid_job_id)]
