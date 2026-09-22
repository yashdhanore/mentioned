from __future__ import annotations

import logging
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.config import Settings
from src.ingestion.queue_worker import process_source_extraction_message
from src.sources.models import Source, SourceStatus
from src.sources.queue import SourceExtractionMessage
from src.timeutils import utc_now

ARCHIVE_TARGET = "src.ingestion.queue_worker.archive_source_extraction_message"


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


@pytest.fixture
def engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def archived(monkeypatch) -> list[int]:
    archived: list[int] = []
    monkeypatch.setattr(ARCHIVE_TARGET, lambda _session, msg_id: archived.append(msg_id))
    return archived


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


def test_queue_worker_archives_missing_source(engine, archived):
    ingestion = FakeSourceIngestion()

    process_source_extraction_message(
        SourceExtractionMessage(msg_id=20, source_id=uuid4(), read_count=1),
        engine,
        Settings(worker_id="worker-queue"),
        ingestion=ingestion,
    )

    assert archived == [20]
    assert ingestion.processed == []


def test_queue_worker_archives_non_pending_source(engine, archived):
    ingestion = FakeSourceIngestion()
    source = _source(engine, status=SourceStatus.DONE)

    process_source_extraction_message(
        SourceExtractionMessage(msg_id=21, source_id=source.id, read_count=1),
        engine,
        Settings(worker_id="worker-queue"),
        ingestion=ingestion,
    )

    assert archived == [21]
    assert ingestion.processed == []


def test_queue_worker_leaves_processing_source_unarchived(engine, archived, caplog):
    ingestion = FakeSourceIngestion()
    caplog.set_level(logging.INFO, logger="src.ingestion.queue_worker")
    source = _source(engine, status=SourceStatus.PROCESSING)

    process_source_extraction_message(
        SourceExtractionMessage(msg_id=24, source_id=source.id, read_count=2),
        engine,
        Settings(worker_id="worker-queue"),
        ingestion=ingestion,
    )

    assert archived == []
    assert ingestion.processed == []
    assert "source queue message 24" in caplog.text
    assert str(source.id) in caplog.text
    assert "stale source recovery" in caplog.text


def test_queue_worker_leaves_failed_source_claim_race_unarchived(engine, archived, monkeypatch):
    ingestion = FakeSourceIngestion()
    monkeypatch.setattr(
        "src.ingestion.queue_worker.claim_source_for_processing", lambda *args: None
    )
    source = _source(engine)

    process_source_extraction_message(
        SourceExtractionMessage(msg_id=22, source_id=source.id, read_count=3),
        engine,
        Settings(worker_id="worker-queue"),
        ingestion=ingestion,
    )

    assert archived == []
    assert ingestion.processed == []


def test_queue_worker_marks_source_failed_and_archives_when_processor_raises(
    engine, monkeypatch, caplog
):
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

    monkeypatch.setattr(ARCHIVE_TARGET, fake_archive)
    source = _source(engine)

    with caplog.at_level("ERROR", logger="src.ingestion.queue_worker"):
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
    # The raw exception text must never reach the user-facing error_message.
    assert refreshed.error_message == "Something went wrong while processing this post."
    assert archived == [25]
    assert order == [("process", SourceStatus.PROCESSING), ("archive", SourceStatus.FAILED)]
    # The raw exception detail is preserved server-side in logs instead.
    assert "thumbnail store unavailable" in caplog.text


def test_queue_worker_leaves_source_message_unarchived_when_attempt_not_finalized(engine, archived):
    class StaleSourceIngestion:
        def process_source(self, _session: Session, source: Source) -> bool:
            source.status = SourceStatus.PROCESSING
            return False

    source = _source(engine)

    process_source_extraction_message(
        SourceExtractionMessage(msg_id=26, source_id=source.id, read_count=1),
        engine,
        Settings(worker_id="worker-queue"),
        ingestion=StaleSourceIngestion(),
    )

    assert archived == []


def test_queue_worker_archives_message_after_source_status_is_saved(engine, monkeypatch, caplog):
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
    monkeypatch.setattr(ARCHIVE_TARGET, fake_archive)
    source = _source(engine)

    process_source_extraction_message(
        SourceExtractionMessage(msg_id=23, source_id=source.id, read_count=1),
        engine,
        Settings(worker_id="worker-queue"),
        ingestion=ingestion,
    )

    assert archived == [23]
    assert order == [("process", SourceStatus.PROCESSING), ("archive", SourceStatus.DONE)]
    assert "Archived source queue message 23" in caplog.text
    assert str(source.id) in caplog.text


def test_queue_worker_fails_and_archives_poison_message_past_max_deliveries(
    engine, archived, caplog
):
    ingestion = FakeSourceIngestion()
    caplog.set_level(logging.ERROR, logger="src.ingestion.queue_worker")
    source = _source(engine, status=SourceStatus.PENDING)

    process_source_extraction_message(
        SourceExtractionMessage(msg_id=99, source_id=source.id, read_count=6),
        engine,
        Settings(worker_id="worker-queue", worker_queue_max_deliveries=5),
        ingestion=ingestion,
    )

    with Session(engine) as session:
        refreshed = session.get(Source, source.id)
    assert refreshed is not None
    assert refreshed.status == SourceStatus.FAILED
    assert refreshed.error_message == "This post could not be processed after repeated attempts."
    assert archived == [99]
    assert ingestion.processed == []
    assert "exceeded max deliveries" in caplog.text


def test_queue_worker_processes_message_at_max_deliveries(engine, archived):
    ingestion = FakeSourceIngestion()
    source = _source(engine, status=SourceStatus.PENDING)

    process_source_extraction_message(
        SourceExtractionMessage(msg_id=100, source_id=source.id, read_count=5),
        engine,
        Settings(worker_id="worker-queue", worker_queue_max_deliveries=5),
        ingestion=ingestion,
    )

    assert archived == [100]
    assert ingestion.processed == [source.id]
