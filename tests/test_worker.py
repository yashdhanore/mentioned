from __future__ import annotations

from uuid import uuid4

from sqlmodel import Session, SQLModel, create_engine

from src.config import Settings
from src.sources.models import Source, SourceStatus


def test_worker_entrypoint_exports_main():
    import src.worker

    assert src.worker.main.__name__ == "main"


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def test_run_queue_worker_iteration_processes_sources_and_drains_push(monkeypatch):
    from src.worker import _run_queue_worker_iteration

    engine = _engine()
    calls: list[str] = []
    source_id = uuid4()

    def fake_read_sources(*_args, **_kwargs):
        calls.append("read_sources")
        return [("source_message", source_id)]

    def fake_process_source(message, _worker_engine, _settings) -> None:
        calls.append(f"process_source:{message[1]}")

    def fake_drain_push(_settings, _worker_engine) -> None:
        calls.append("drain_push")

    monkeypatch.setattr("src.worker.read_source_extraction_messages", fake_read_sources)
    monkeypatch.setattr("src.worker.process_source_extraction_message", fake_process_source)
    monkeypatch.setattr("src.worker._drain_push_notifications", fake_drain_push)

    try:
        _run_queue_worker_iteration(Settings(worker_id="worker-queue"), engine)
    finally:
        SQLModel.metadata.drop_all(engine)

    assert calls == ["read_sources", f"process_source:{source_id}", "drain_push"]


def test_run_polling_worker_iteration_claims_and_processes_pending_source(monkeypatch):
    from src.worker import _run_polling_worker_iteration

    engine = _engine()
    with Session(engine) as session:
        source = Source(
            source_key="instagram:reel:POLL1",
            platform="instagram",
            source_type="reel",
            external_id="POLL1",
            canonical_url="https://www.instagram.com/reel/POLL1/",
            status=SourceStatus.PENDING,
        )
        session.add(source)
        session.commit()
        session.refresh(source)

    processed: list[str] = []

    def fake_process_source(session: Session, source: Source) -> bool:
        processed.append(str(source.id))
        source.status = SourceStatus.DONE
        session.add(source)
        session.commit()
        return True

    monkeypatch.setattr("src.worker.default_source_ingestion.process_source", fake_process_source)

    try:
        did_process = _run_polling_worker_iteration(Settings(worker_id="worker-poll"), engine)
    finally:
        SQLModel.metadata.drop_all(engine)

    assert did_process is True
    assert processed == [str(source.id)]


def test_run_polling_worker_iteration_returns_false_when_no_pending_source():
    from src.worker import _run_polling_worker_iteration

    engine = _engine()

    try:
        did_process = _run_polling_worker_iteration(Settings(worker_id="worker-poll"), engine)
    finally:
        SQLModel.metadata.drop_all(engine)

    assert did_process is False
