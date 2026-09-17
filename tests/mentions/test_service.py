from __future__ import annotations

from uuid import UUID

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.jobs.service import create_job
from src.mentions.models import Mention
from src.mentions.service import delete_mention, list_mentions, update_mention


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
OWNER_UUID = UUID(OWNER)


def _create_mention(session, job_id: str, title: str = "Test Book") -> Mention:
    m = Mention(
        owner_id=OWNER_UUID,
        job_id=job_id,
        title=title,
        category="book",
        source_url="https://instagram.com/reel/X/",
    )
    session.add(m)
    session.commit()
    session.refresh(m)
    return m


def test_list_mentions(session):
    job = create_job(session, OWNER, "https://instagram.com/reel/X/")
    _create_mention(session, job.id, "Book A")
    _create_mention(session, job.id, "Book B")
    mentions = list_mentions(session, OWNER)
    assert len(mentions) == 2


def test_list_excludes_deleted(session):
    job = create_job(session, OWNER, "https://instagram.com/reel/X/")
    m = _create_mention(session, job.id)
    delete_mention(session, m)
    mentions = list_mentions(session, OWNER)
    assert len(mentions) == 0


def test_update_mention(session):
    job = create_job(session, OWNER, "https://instagram.com/reel/X/")
    m = _create_mention(session, job.id, "Old Title")
    updated = update_mention(session, m, title="New Title", author="Author X")
    assert updated.title == "New Title"
    assert updated.author == "Author X"


def test_delete_mention(session):
    job = create_job(session, OWNER, "https://instagram.com/reel/X/")
    m = _create_mention(session, job.id)
    delete_mention(session, m)
    refreshed = session.get(Mention, m.id)
    assert refreshed.is_deleted is True
