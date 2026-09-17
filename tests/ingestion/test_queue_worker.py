from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlmodel import Session, SQLModel, create_engine

from src.config import Settings
from src.ingestion.queue_worker import (
    process_extract_job_message,
    process_source_extraction_message,
)
from src.jobs.models import Job, JobStatus
from src.jobs.queue import ExtractJobMessage
from src.sources.models import Source, SourceStatus
from src.sources.queue import SourceExtractionMessage
from src.timeutils import utc_now

OWNER = UUID("00000000-0000-4000-8000-000000000001")


class FakeIngestion:
    def __init__(self) -> None:
        self.processed: list[UUID] = []

    def process_job(self, session: Session, job: Job) -> None:
        self.processed.append(job.id)
        job.status = JobStatus.DONE
        job.finished_at = utc_now()
        job.locked_by = None
        job.locked_at = None
        session.add(job)
        session.commit()


class FakeSourceIngestion:
    def __init__(self) -> None:
        self.processed: list[UUID] = []

    def process_source(self, session: Session, source: Source) -> bool:
        self.processed.append(source.id)
        source.status = SourceStatus.DONE
        source.processed_at = utc_now()
        session.add(source)
        session.commit()
        return True


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
            locked_at=utc_now() if locked_by else None,
            heartbeat_at=utc_now() if locked_by else None,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job


def _source(engine, *, status: SourceStatus = SourceStatus.PENDING) -> Source:
    with Session(engine) as session:
        source = Source(
            source_key=f"instagram:reel:{uuid4()}",
            platform="instagram",
            source_type="reel",
            external_id="QUEUE",
            canonical_url="https://www.instagram.com/reel/QUEUE/",
            status=status,
        )
        session.add(source)
        session.commit()
        session.refresh(source)
        return source


def test_queue_worker_iteration_skips_legacy_poll_when_source_messages_exist(monkeypatch):
    from src.worker import _run_queue_worker_iteration

    engine = _engine()
    calls: list[str] = []
    source_message = SourceExtractionMessage(msg_id=30, source_id=uuid4(), read_count=1)

    def fake_read_sources(*_args, **_kwargs) -> list[SourceExtractionMessage]:
        calls.append("read_sources")
        return [source_message]

    def fake_process_source(message, _worker_engine, _settings) -> None:
        calls.append(f"process_source:{message.msg_id}")

    def fake_read_jobs(*_args, **_kwargs) -> list[ExtractJobMessage]:
        calls.append("read_jobs")
        return []

    def fake_drain_push(_settings, _worker_engine) -> None:
        calls.append("drain_push")

    monkeypatch.setattr("src.worker.read_source_extraction_messages", fake_read_sources)
    monkeypatch.setattr("src.worker.process_source_extraction_message", fake_process_source)
    monkeypatch.setattr("src.worker.read_extract_job_messages", fake_read_jobs)
    monkeypatch.setattr("src.worker._drain_push_notifications", fake_drain_push)

    try:
        _run_queue_worker_iteration(Settings(worker_id="worker-queue"), engine)
    finally:
        SQLModel.metadata.drop_all(engine)

    assert calls == ["read_sources", "process_source:30"]


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


def test_queue_worker_archives_missing_source(monkeypatch):
    engine = _engine()
    archived = []
    ingestion = FakeSourceIngestion()

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    monkeypatch.setattr(
        "src.ingestion.queue_worker.archive_source_extraction_message", fake_archive
    )

    try:
        process_source_extraction_message(
            SourceExtractionMessage(msg_id=20, source_id=uuid4(), read_count=1),
            engine,
            Settings(worker_id="worker-queue"),
            ingestion=ingestion,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == [20]
    assert ingestion.processed == []


def test_queue_worker_archives_non_pending_source(monkeypatch):
    engine = _engine()
    archived = []
    ingestion = FakeSourceIngestion()

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    monkeypatch.setattr(
        "src.ingestion.queue_worker.archive_source_extraction_message", fake_archive
    )

    try:
        source = _source(engine, status=SourceStatus.DONE)

        process_source_extraction_message(
            SourceExtractionMessage(msg_id=21, source_id=source.id, read_count=1),
            engine,
            Settings(worker_id="worker-queue"),
            ingestion=ingestion,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == [21]
    assert ingestion.processed == []


def test_queue_worker_leaves_processing_source_unarchived(monkeypatch, caplog):
    engine = _engine()
    archived = []
    ingestion = FakeSourceIngestion()
    caplog.set_level(logging.INFO, logger="src.ingestion.queue_worker")

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    monkeypatch.setattr(
        "src.ingestion.queue_worker.archive_source_extraction_message", fake_archive
    )

    try:
        source = _source(engine, status=SourceStatus.PROCESSING)

        process_source_extraction_message(
            SourceExtractionMessage(msg_id=24, source_id=source.id, read_count=2),
            engine,
            Settings(worker_id="worker-queue"),
            ingestion=ingestion,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == []
    assert ingestion.processed == []
    assert "source queue message 24" in caplog.text
    assert str(source.id) in caplog.text
    assert "stale source recovery" in caplog.text


def test_queue_worker_leaves_failed_source_claim_race_unarchived(monkeypatch):
    engine = _engine()
    archived = []
    ingestion = FakeSourceIngestion()

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    monkeypatch.setattr(
        "src.ingestion.queue_worker.archive_source_extraction_message", fake_archive
    )
    monkeypatch.setattr(
        "src.ingestion.queue_worker.claim_source_for_processing", lambda *args: None
    )

    try:
        source = _source(engine)

        process_source_extraction_message(
            SourceExtractionMessage(msg_id=22, source_id=source.id, read_count=3),
            engine,
            Settings(worker_id="worker-queue"),
            ingestion=ingestion,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == []
    assert ingestion.processed == []


def test_queue_worker_marks_source_failed_and_archives_when_processor_raises(monkeypatch):
    engine = _engine()
    archived = []
    order = []

    class FailingSourceIngestion:
        def process_source(self, session: Session, source: Source) -> None:
            order.append(("process", source.status))
            raise RuntimeError("thumbnail store unavailable")

    def fake_archive(session: Session, msg_id: int) -> None:
        refreshed = session.get(Source, source.id)
        order.append(("archive", refreshed.status if refreshed else None))
        archived.append(msg_id)

    monkeypatch.setattr(
        "src.ingestion.queue_worker.archive_source_extraction_message", fake_archive
    )

    try:
        source = _source(engine)

        process_source_extraction_message(
            SourceExtractionMessage(msg_id=25, source_id=source.id, read_count=1),
            engine,
            Settings(worker_id="worker-queue"),
            ingestion=FailingSourceIngestion(),
        )

        with Session(engine) as session:
            refreshed = session.get(Source, source.id)
            assert refreshed is not None
            assert refreshed.status == SourceStatus.FAILED
            assert refreshed.error_message == "thumbnail store unavailable"
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == [25]
    assert order == [("process", SourceStatus.PROCESSING), ("archive", SourceStatus.FAILED)]


def test_queue_worker_leaves_source_message_unarchived_when_attempt_not_finalized(monkeypatch):
    engine = _engine()
    archived = []

    class StaleSourceIngestion:
        def process_source(self, _session: Session, source: Source) -> bool:
            source.status = SourceStatus.PROCESSING
            return False

    def fake_archive(_session: Session, msg_id: int) -> None:
        archived.append(msg_id)

    monkeypatch.setattr(
        "src.ingestion.queue_worker.archive_source_extraction_message", fake_archive
    )

    try:
        source = _source(engine)

        process_source_extraction_message(
            SourceExtractionMessage(msg_id=26, source_id=source.id, read_count=1),
            engine,
            Settings(worker_id="worker-queue"),
            ingestion=StaleSourceIngestion(),
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == []


def test_queue_worker_archives_message_after_source_status_is_saved(monkeypatch, caplog):
    engine = _engine()
    archived = []
    order = []
    ingestion = FakeSourceIngestion()
    original_process_source = ingestion.process_source
    caplog.set_level(logging.INFO, logger="src.ingestion.queue_worker")

    def fake_process(session: Session, source: Source) -> bool:
        order.append(("process", source.status))
        return original_process_source(session, source)

    def fake_archive(session: Session, msg_id: int) -> None:
        refreshed = session.get(Source, source.id)
        order.append(("archive", refreshed.status if refreshed else None))
        archived.append(msg_id)

    ingestion.process_source = fake_process  # type: ignore[method-assign]
    monkeypatch.setattr(
        "src.ingestion.queue_worker.archive_source_extraction_message", fake_archive
    )

    try:
        source = _source(engine)

        process_source_extraction_message(
            SourceExtractionMessage(msg_id=23, source_id=source.id, read_count=1),
            engine,
            Settings(worker_id="worker-queue"),
            ingestion=ingestion,
        )
    finally:
        SQLModel.metadata.drop_all(engine)

    assert archived == [23]
    assert order == [("process", SourceStatus.PROCESSING), ("archive", SourceStatus.DONE)]
    assert "Archived source queue message 23" in caplog.text
    assert str(source.id) in caplog.text
