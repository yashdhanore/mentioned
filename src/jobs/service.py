from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlmodel import Session, select

from src.ids import parse_uuid
from src.jobs.models import Job, JobStatus
from src.jobs.queue import enqueue_extract_job
from src.mentions.models import Mention


def _new_job(owner_id: str, source_url: str) -> Job:
    return Job(
        id=uuid4(),
        owner_id=parse_uuid(owner_id),
        source_url=source_url,
        status=JobStatus.PENDING,
        created_at=datetime.utcnow(),
    )


def create_job(session: Session, owner_id: str, source_url: str) -> Job:
    job = _new_job(owner_id, source_url)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def create_queued_job(session: Session, owner_id: str, source_url: str) -> Job:
    job = _new_job(owner_id, source_url)
    try:
        session.add(job)
        session.flush()
        enqueue_extract_job(session, job.id)
        session.commit()
        session.refresh(job)
    except Exception:
        session.rollback()
        raise
    return job


def get_job(session: Session, job_id: str | UUID) -> Job | None:
    return session.get(Job, parse_uuid(job_id))


def list_jobs(session: Session, owner_id: str, limit: int = 50) -> list[Job]:
    owner_uuid = parse_uuid(owner_id)
    stmt = (
        select(Job)
        .where(Job.owner_id == owner_uuid)
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


def claim_job_by_id(session: Session, job_id: str | UUID, worker_id: str) -> Job | None:
    stmt = (
        select(Job)
        .where(
            Job.id == parse_uuid(job_id),
            Job.status == JobStatus.PENDING,
            Job.locked_by == None,
        )
        .limit(1)
    )
    job = session.exec(stmt).first()
    if not job:
        return None
    now = datetime.utcnow()
    job.locked_by = worker_id
    job.locked_at = now
    job.heartbeat_at = now
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
    owner_uuid = parse_uuid(owner_id)
    stmt = select(func.count()).select_from(Job).where(
        Job.owner_id == owner_uuid,
        Job.status == JobStatus.PENDING,
    )
    return int(session.exec(stmt).one())


def count_jobs_created_since(session: Session, owner_id: str, since: datetime) -> int:
    owner_uuid = parse_uuid(owner_id)
    stmt = select(func.count()).select_from(Job).where(
        Job.owner_id == owner_uuid,
        Job.created_at >= since,
    )
    return int(session.exec(stmt).one())
