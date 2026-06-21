from __future__ import annotations

from datetime import datetime
import logging
from uuid import UUID, uuid4

from sqlmodel import Session, SQLModel, create_engine

from src.config import Settings
from src.ingestion.queue_worker import process_extract_job_message
from src.jobs.models import Job, JobStatus
from src.jobs.queue import ExtractJobMessage


OWNER = UUID("00000000-0000-4000-8000-000000000001")


class FakeIngestion:
    def __init__(self) -> None:
        self.processed: list[UUID] = []

    def process_job(self, session: Session, job: Job) -> None:
        self.processed.append(job.id)
        job.status = JobStatus.DONE
        job.finished_at = datetime.utcnow()
        job.locked_by = None
        job.locked_at = None
        session.add(job)
        session.commit()


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def _job(engine, *, status: JobStatus = JobStatus.PENDING, locked_by: str | None = None) -> Job:
    with Session(engine) as session:
        job = Job(
            owner_id=OWNER,
            source_url="https://www.instagram.com/reel/QUEUE/",
            status=status,
            locked_by=locked_by,
            locked_at=datetime.utcnow() if locked_by else None,
            heartbeat_at=datetime.utcnow() if locked_by else None,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job


def test_queue_worker_archives_missing_job(monkeypatch):
    engine = _engine()
    archived = []
    ingestion = FakeIngestion()

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    monkeypatch.setattr("src.ingestion.queue_worker.archive_extract_job_message", fake_archive)

    try:
        process_extract_job_message(
            ExtractJobMessage(msg_id=10, job_id=uuid4(), read_count=1),
            engine,
            Settings(worker_id="worker-queue"),
            ingestion=ingestion,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == [10]
    assert ingestion.processed == []


def test_queue_worker_archives_terminal_job(monkeypatch):
    engine = _engine()
    archived = []
    ingestion = FakeIngestion()

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    monkeypatch.setattr("src.ingestion.queue_worker.archive_extract_job_message", fake_archive)

    try:
        job = _job(engine, status=JobStatus.DONE)

        process_extract_job_message(
            ExtractJobMessage(msg_id=11, job_id=job.id, read_count=1),
            engine,
            Settings(worker_id="worker-queue"),
            ingestion=ingestion,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == [11]
    assert ingestion.processed == []


def test_queue_worker_leaves_locked_pending_job_unarchived(monkeypatch, caplog):
    engine = _engine()
    archived = []
    ingestion = FakeIngestion()
    caplog.set_level(logging.INFO, logger="src.ingestion.queue_worker")

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    monkeypatch.setattr("src.ingestion.queue_worker.archive_extract_job_message", fake_archive)

    try:
        job = _job(engine, locked_by="other-worker")

        process_extract_job_message(
            ExtractJobMessage(msg_id=12, job_id=job.id, read_count=2),
            engine,
            Settings(worker_id="worker-queue"),
            ingestion=ingestion,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == []
    assert ingestion.processed == []
    assert "queue message 12" in caplog.text
    assert str(job.id) in caplog.text
    assert "read_count=2" in caplog.text


def test_queue_worker_leaves_failed_claim_race_unarchived(monkeypatch):
    engine = _engine()
    archived = []
    ingestion = FakeIngestion()

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    monkeypatch.setattr("src.ingestion.queue_worker.archive_extract_job_message", fake_archive)
    monkeypatch.setattr("src.ingestion.queue_worker.claim_job_by_id", lambda *args: None)

    try:
        job = _job(engine)

        process_extract_job_message(
            ExtractJobMessage(msg_id=13, job_id=job.id, read_count=3),
            engine,
            Settings(worker_id="worker-queue"),
            ingestion=ingestion,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == []
    assert ingestion.processed == []


def test_queue_worker_archives_message_after_job_status_is_saved(monkeypatch, caplog):
    engine = _engine()
    archived = []
    order = []
    ingestion = FakeIngestion()
    original_process_job = ingestion.process_job
    caplog.set_level(logging.INFO, logger="src.ingestion.queue_worker")

    def fake_process(session: Session, job: Job) -> None:
        order.append(("process", job.locked_by))
        original_process_job(session, job)

    def fake_archive(session: Session, msg_id: int) -> None:
        refreshed = session.get(Job, job.id)
        order.append(("archive", refreshed.status if refreshed else None))
        archived.append(msg_id)

    ingestion.process_job = fake_process  # type: ignore[method-assign]
    monkeypatch.setattr("src.ingestion.queue_worker.archive_extract_job_message", fake_archive)

    try:
        job = _job(engine)

        process_extract_job_message(
            ExtractJobMessage(msg_id=14, job_id=job.id, read_count=1),
            engine,
            Settings(worker_id="worker-queue"),
            ingestion=ingestion,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == [14]
    assert order == [("process", "worker-queue"), ("archive", JobStatus.DONE)]
    assert "Archived queue message 14" in caplog.text
    assert str(job.id) in caplog.text
