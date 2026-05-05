from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.jobs.models import Job, JobStatus
from src.jobs.service import (
    claim_next_job,
    complete_job,
    count_active_jobs,
    count_jobs_created_since,
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


OWNER = "owner-1"


def test_create_job(session):
    job = create_job(session, OWNER, "https://instagram.com/reel/ABC123/")
    assert job.id
    assert job.owner_id == OWNER
    assert job.status == JobStatus.PENDING
    assert job.source_url == "https://instagram.com/reel/ABC123/"


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
        owner_id=OWNER,
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


def test_fail_job(session):
    job = create_job(session, OWNER, "https://instagram.com/reel/ABC123/")
    job = claim_next_job(session, "worker-1")
    fail_job(session, job, "Download failed")
    refreshed = session.get(Job, job.id)
    assert refreshed.status == JobStatus.FAILED
    assert refreshed.error_message == "Download failed"


def test_count_active_jobs(session):
    create_job(session, OWNER, "https://instagram.com/reel/A/")
    create_job(session, OWNER, "https://instagram.com/reel/B/")
    assert count_active_jobs(session, OWNER) == 2
    assert count_active_jobs(session, "other-owner") == 0


def test_count_jobs_created_since(session):
    now = datetime.utcnow()
    create_job(session, OWNER, "https://instagram.com/reel/A/")
    old = create_job(session, OWNER, "https://instagram.com/reel/B/")
    old.created_at = now - timedelta(days=2)
    session.add(old)
    session.commit()

    assert count_jobs_created_since(session, OWNER, now - timedelta(days=1)) == 1
    assert count_jobs_created_since(session, "other-owner", now - timedelta(days=1)) == 0
