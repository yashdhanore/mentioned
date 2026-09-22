from __future__ import annotations

import signal
from uuid import uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.config import Settings
from src.sources.models import Source, SourceStatus
from src.worker import (
    ShutdownFlag,
    _run_polling_worker,
    _run_polling_worker_iteration,
    _run_queue_worker,
    _run_queue_worker_iteration,
    install_signal_handlers,
)


@pytest.fixture
def engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


def test_run_queue_worker_iteration_processes_sources_and_drains_push(monkeypatch, engine):
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

    _run_queue_worker_iteration(Settings(worker_id="worker-queue"), engine)

    assert calls == ["read_sources", f"process_source:{source_id}", "drain_push"]


def test_run_polling_worker_iteration_claims_and_processes_pending_source(monkeypatch, engine):
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

    did_process = _run_polling_worker_iteration(Settings(worker_id="worker-poll"), engine)

    assert did_process is True
    assert processed == [str(source.id)]


def test_run_polling_worker_iteration_returns_false_when_no_pending_source(engine):
    did_process = _run_polling_worker_iteration(Settings(worker_id="worker-poll"), engine)

    assert did_process is False


def test_shutdown_flag_request_stop_sets_flag():
    flag = ShutdownFlag()

    flag.request_stop(signal.SIGTERM, None)

    assert flag.should_stop is True


def test_install_signal_handlers_registers_sigterm_and_sigint(monkeypatch):
    registered: list[int] = []
    monkeypatch.setattr(signal, "signal", lambda sig, _handler: registered.append(sig))

    install_signal_handlers(ShutdownFlag())

    assert signal.SIGTERM in registered
    assert signal.SIGINT in registered


def test_run_polling_worker_stops_between_iterations_on_shutdown_flag(monkeypatch):

    calls: list[int] = []
    flag = ShutdownFlag()

    def fake_iteration(_settings, _engine) -> bool:
        calls.append(1)
        if len(calls) >= 2:
            flag.should_stop = True
        return False

    monkeypatch.setattr("src.worker._run_polling_worker_iteration", fake_iteration)
    monkeypatch.setattr("src.worker.time.sleep", lambda _seconds: None)

    _run_polling_worker(Settings(worker_id="worker-poll"), object(), flag)

    assert len(calls) == 2


def test_run_polling_worker_recovers_from_iteration_exception_and_backs_off(monkeypatch):

    calls: list[int] = []
    slept: list[float] = []
    flag = ShutdownFlag()

    def fake_iteration(_settings, _engine) -> bool:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        flag.should_stop = True
        return False

    monkeypatch.setattr("src.worker._run_polling_worker_iteration", fake_iteration)
    monkeypatch.setattr("src.worker.time.sleep", lambda seconds: slept.append(seconds))

    _run_polling_worker(Settings(worker_id="worker-poll"), object(), flag)

    assert len(calls) == 2
    assert slept


def test_run_polling_worker_reraises_keyboard_interrupt(monkeypatch):

    def fake_iteration(_settings, _engine) -> bool:
        raise KeyboardInterrupt

    monkeypatch.setattr("src.worker._run_polling_worker_iteration", fake_iteration)

    with pytest.raises(KeyboardInterrupt):
        _run_polling_worker(Settings(worker_id="worker-poll"), object(), ShutdownFlag())


def test_run_queue_worker_stops_between_iterations_on_shutdown_flag(monkeypatch):

    calls: list[int] = []
    flag = ShutdownFlag()

    def fake_iteration(_settings, _engine) -> None:
        calls.append(1)
        if len(calls) >= 2:
            flag.should_stop = True

    monkeypatch.setattr("src.worker._run_queue_worker_iteration", fake_iteration)

    _run_queue_worker(Settings(worker_id="worker-queue"), object(), flag)

    assert len(calls) == 2


def test_run_queue_worker_recovers_from_iteration_exception_and_backs_off(monkeypatch):

    calls: list[int] = []
    slept: list[float] = []
    flag = ShutdownFlag()

    def fake_iteration(_settings, _engine) -> None:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        flag.should_stop = True

    monkeypatch.setattr("src.worker._run_queue_worker_iteration", fake_iteration)
    monkeypatch.setattr("src.worker.time.sleep", lambda seconds: slept.append(seconds))

    _run_queue_worker(Settings(worker_id="worker-queue"), object(), flag)

    assert len(calls) == 2
    assert slept


def test_run_queue_worker_reraises_system_exit(monkeypatch):

    def fake_iteration(_settings, _engine) -> None:
        raise SystemExit

    monkeypatch.setattr("src.worker._run_queue_worker_iteration", fake_iteration)

    with pytest.raises(SystemExit):
        _run_queue_worker(Settings(worker_id="worker-queue"), object(), ShutdownFlag())
