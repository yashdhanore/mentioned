from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from src.jobs.models import Job, JobEvent, JobEventType, JobStatus
from src.jobs.service import (
    claim_next_job,
    complete_job,
    count_active_jobs,
    count_jobs_created_since,
    create_queued_job,
    create_job,
    fail_job,
    recover_stale_jobs,
)
from src.mentions.models import Mention


@pytest.fixture
def engine():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(e)
    yield e
    SQLModel.metadata.drop_all(e)


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


OWNER = "00000000-0000-4000-8000-000000000001"
OTHER_OWNER = "00000000-0000-4000-8000-000000000002"
OWNER_UUID = UUID(OWNER)


def test_create_job(session):
    job = create_job(session, OWNER, "https://instagram.com/reel/ABC123/")
    assert job.id
    assert str(job.owner_id) == OWNER
    assert job.status == JobStatus.PENDING
    assert job.source_url == "https://instagram.com/reel/ABC123/"


def test_create_queued_job_enqueues_extract_job(session, monkeypatch):
    enqueued = []

    def fake_enqueue(session_arg: Session, job_id) -> None:
        assert session_arg is session
        enqueued.append(str(job_id))

    monkeypatch.setattr("src.jobs.service.enqueue_extract_job", fake_enqueue)

    job = create_queued_job(session, OWNER, "https://instagram.com/reel/ABC123/")

    assert enqueued == [str(job.id)]
    assert session.get(Job, job.id) is not None


def test_create_queued_job_rolls_back_when_enqueue_fails(session, monkeypatch):
    def fail_enqueue(_session: Session, _job_id) -> None:
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr("src.jobs.service.enqueue_extract_job", fail_enqueue)

    with pytest.raises(RuntimeError, match="queue unavailable"):
        create_queued_job(session, OWNER, "https://instagram.com/reel/ABC123/")

    assert list(session.exec(select(Job)).all()) == []


def test_claim_next_job(session):
    create_job(session, OWNER, "https://instagram.com/reel/ABC123/")
    job = claim_next_job(session, "worker-1")
    assert job is not None
    assert job.locked_by == "worker-1"
    assert job.locked_at is not None


def test_claim_returns_none_when_empty(session):
    assert claim_next_job(session, "worker-1") is None


def test_complete_job(session):
    job = create_job(session, OWNER, "https://instagram.com/reel/ABC123/")
    job = claim_next_job(session, "worker-1")
    mention = Mention(
        owner_id=OWNER_UUID,
        job_id=job.id,
        title="Atomic Habits",
        category="book",
        source_url=job.source_url,
    )
    complete_job(session, job, [mention])
    refreshed = session.get(Job, job.id)
    assert refreshed.status == JobStatus.DONE
    assert refreshed.finished_at is not None
    assert refreshed.locked_by is None
    events = list(session.exec(select(JobEvent)).all())
    assert len(events) == 1
    assert events[0].owner_id == OWNER_UUID
    assert events[0].job_id == job.id
    assert events[0].event_type == JobEventType.JOB_DONE


def test_fail_job(session):
    job = create_job(session, OWNER, "https://instagram.com/reel/ABC123/")
    job = claim_next_job(session, "worker-1")
    fail_job(session, job, "Download failed")
    refreshed = session.get(Job, job.id)
    assert refreshed.status == JobStatus.FAILED
    assert refreshed.error_message == "Download failed"
    events = list(session.exec(select(JobEvent)).all())
    assert len(events) == 1
    assert events[0].owner_id == OWNER_UUID
    assert events[0].job_id == job.id
    assert events[0].event_type == JobEventType.JOB_FAILED


def test_count_active_jobs(session):
    create_job(session, OWNER, "https://instagram.com/reel/A/")
    create_job(session, OWNER, "https://instagram.com/reel/B/")
    assert count_active_jobs(session, OWNER) == 2
    assert count_active_jobs(session, OTHER_OWNER) == 0


def test_count_jobs_created_since(session):
    now = datetime.utcnow()
    create_job(session, OWNER, "https://instagram.com/reel/A/")
    old = create_job(session, OWNER, "https://instagram.com/reel/B/")
    old.created_at = now - timedelta(days=2)
    session.add(old)
    session.commit()

    assert count_jobs_created_since(session, OWNER, now - timedelta(days=1)) == 1
    assert count_jobs_created_since(session, OTHER_OWNER, now - timedelta(days=1)) == 0
