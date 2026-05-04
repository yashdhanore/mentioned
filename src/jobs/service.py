from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlmodel import Session, select

from src.jobs.models import Job, JobStatus
from src.mentions.models import Mention


def create_job(session: Session, owner_id: str, source_url: str) -> Job:
    job = Job(
        id=str(uuid4()),
        owner_id=owner_id,
        source_url=source_url,
        status=JobStatus.PENDING,
        created_at=datetime.utcnow(),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def get_job(session: Session, job_id: str) -> Job | None:
    return session.get(Job, job_id)


def list_jobs(session: Session, owner_id: str, limit: int = 50) -> list[Job]:
    stmt = (
        select(Job)
        .where(Job.owner_id == owner_id)
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    return list(session.exec(stmt).all())


def claim_next_job(session: Session, worker_id: str) -> Job | None:
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.PENDING, Job.locked_by == None)
        .order_by(Job.created_at)
        .limit(1)
    )
    job = session.exec(stmt).first()
    if not job:
        return None
    job.locked_by = worker_id
    job.locked_at = datetime.utcnow()
    job.heartbeat_at = datetime.utcnow()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def complete_job(session: Session, job: Job, mentions: list[Mention]) -> None:
    job.status = JobStatus.DONE
    job.finished_at = datetime.utcnow()
    job.locked_by = None
    job.locked_at = None
    session.add(job)
    for mention in mentions:
        session.add(mention)
    session.commit()


def fail_job(session: Session, job: Job, error: str) -> None:
    job.status = JobStatus.FAILED
    job.error_message = error
    job.finished_at = datetime.utcnow()
    job.locked_by = None
    job.locked_at = None
    session.add(job)
    session.commit()


def recover_stale_jobs(session: Session, stale_timeout_seconds: int = 900) -> int:
    cutoff = datetime.utcnow() - timedelta(seconds=stale_timeout_seconds)
    stmt = (
        select(Job)
        .where(
            Job.status == JobStatus.PENDING,
            Job.locked_by != None,
            Job.heartbeat_at < cutoff,
        )
    )
    stale_jobs = list(session.exec(stmt).all())
    for job in stale_jobs:
        job.locked_by = None
        job.locked_at = None
        job.heartbeat_at = None
        session.add(job)
    if stale_jobs:
        session.commit()
    return len(stale_jobs)


def count_active_jobs(session: Session, owner_id: str) -> int:
    stmt = select(Job).where(Job.owner_id == owner_id, Job.status == JobStatus.PENDING)
    return len(list(session.exec(stmt).all()))
