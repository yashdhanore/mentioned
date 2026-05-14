from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Session, SQLModel, create_engine

from src.config import Settings
from src.jobs.models import Job, JobStatus
from src.jobs.queue import ExtractJobMessage
from src.worker import process_extract_job_message


OWNER = UUID("00000000-0000-4000-8000-000000000001")


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def test_worker_archives_missing_queue_job(monkeypatch):
    engine = _engine()
    archived = []

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    monkeypatch.setattr("src.worker.archive_extract_job_message", fake_archive)

    try:
        process_extract_job_message(
            ExtractJobMessage(msg_id=10, job_id=uuid4(), read_count=1),
            engine,
            Settings(worker_id="worker-queue"),
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == [10]


def test_worker_leaves_locked_pending_queue_job_unarchived(monkeypatch):
    engine = _engine()
    archived = []
    processed = []

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    def fake_process(_job: Job, _session: Session) -> None:
        processed.append(_job.id)

    monkeypatch.setattr("src.worker.archive_extract_job_message", fake_archive)
    monkeypatch.setattr("src.worker.process_job", fake_process)

    try:
        with Session(engine) as session:
            job = Job(
                owner_id=OWNER,
                source_url="https://www.instagram.com/reel/LOCKED/",
                status=JobStatus.PENDING,
                locked_by="other-worker",
                locked_at=datetime.utcnow(),
                heartbeat_at=datetime.utcnow(),
            )
            session.add(job)
            session.commit()
            session.refresh(job)

        process_extract_job_message(
            ExtractJobMessage(msg_id=11, job_id=job.id, read_count=1),
            engine,
            Settings(worker_id="worker-queue"),
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == []
    assert processed == []


def test_worker_archives_queue_message_after_job_status_is_saved(monkeypatch):
    engine = _engine()
    archived = []
    order = []

    def fake_process(job: Job, session: Session) -> None:
        order.append(("process", job.locked_by))
        job.status = JobStatus.DONE
        job.finished_at = datetime.utcnow()
        job.locked_by = None
        job.locked_at = None
        session.add(job)
        session.commit()

    def fake_archive(session: Session, msg_id: int) -> None:
        refreshed = session.get(Job, job.id)
        order.append(("archive", refreshed.status if refreshed else None))
        archived.append(msg_id)

    monkeypatch.setattr("src.worker.process_job", fake_process)
    monkeypatch.setattr("src.worker.archive_extract_job_message", fake_archive)

    try:
        with Session(engine) as session:
            job = Job(
                owner_id=OWNER,
                source_url="https://www.instagram.com/reel/QUEUE/",
                status=JobStatus.PENDING,
            )
            session.add(job)
            session.commit()
            session.refresh(job)

        process_extract_job_message(
            ExtractJobMessage(msg_id=12, job_id=job.id, read_count=1),
            engine,
            Settings(worker_id="worker-queue"),
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == [12]
    assert order == [("process", "worker-queue"), ("archive", JobStatus.DONE)]
