from __future__ import annotations

import logging
import signal
import time
from types import FrameType

from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.config import Settings, get_settings
from src.database import check_worker_database_role, create_sql_engine, engine
from src.ingestion.queue_worker import process_source_extraction_message
from src.ingestion.source_processor import default_source_ingestion
from src.observability import configure_tracing, shutdown_tracing
from src.push.queue import read_push_notification_messages
from src.push.worker import process_push_notification_message
from src.sources.models import Source
from src.sources.queue import read_source_extraction_messages
from src.sources.service import claim_next_pending_source, recover_stale_sources

logger = logging.getLogger(__name__)


class ShutdownFlag:
    """A plain flag checked between loop iterations, set by a signal handler.

    No threads: SIGTERM/SIGINT just flip a bool, so the current iteration (an
    in-flight source) always finishes before the worker loop notices and exits.
    """

    def __init__(self) -> None:
        self.should_stop = False

    def request_stop(self, signum: int, _frame: FrameType | None) -> None:
        logger.info("Received signal %s, will exit after the current iteration finishes", signum)
        self.should_stop = True


def install_signal_handlers(flag: ShutdownFlag) -> None:
    signal.signal(signal.SIGTERM, flag.request_stop)
    signal.signal(signal.SIGINT, flag.request_stop)


def resolve_worker_engine(settings: Settings) -> Engine:
    if settings.worker_database_url:
        return create_sql_engine(settings.worker_database_url)
    if settings.is_production:
        raise RuntimeError("Production worker requires WORKER_DATABASE_URL")
    return engine


def _drain_push_notifications(settings: Settings, worker_engine: Engine) -> None:
    with Session(worker_engine) as session:
        messages = read_push_notification_messages(
            session,
            visibility_timeout_seconds=settings.worker_queue_visibility_timeout_seconds,
        )
        session.commit()

    for message in messages:
        process_push_notification_message(message, worker_engine, settings)


def _run_polling_worker_iteration(settings: Settings, worker_engine: Engine) -> bool:
    with Session(worker_engine) as session:
        recovered = recover_stale_sources(session, settings.worker_stale_timeout_seconds)
        if recovered:
            logger.info("Recovered %d stale sources", recovered)
        source = claim_next_pending_source(session)

    if not source:
        return False

    logger.info("Claimed source %s (%s)", source.id, source.canonical_url)
    with Session(worker_engine) as session:
        source = session.get(Source, source.id)
        if source:
            default_source_ingestion.process_source(session, source)
            logger.info("Source %s finished with status: %s", source.id, source.status)
    return True


def _run_polling_worker(settings: Settings, worker_engine: Engine, shutdown: ShutdownFlag) -> None:
    poll_interval = settings.worker_poll_interval_seconds
    logger.info(
        "Worker %s starting in polling mode (poll=%.1fs)", settings.worker_id, poll_interval
    )
    while not shutdown.should_stop:
        try:
            processed = _run_polling_worker_iteration(settings, worker_engine)
        except Exception:
            logger.exception("Unhandled error in polling worker iteration, backing off")
            time.sleep(poll_interval)
            continue
        if not processed:
            logger.debug("No pending sources, sleeping %.1fs", poll_interval)
            time.sleep(poll_interval)
    logger.info("Worker %s stopped", settings.worker_id)


def _run_queue_worker(settings: Settings, worker_engine: Engine, shutdown: ShutdownFlag) -> None:
    logger.info(
        "Worker %s starting in queue mode (visibility_timeout=%ss)",
        settings.worker_id,
        settings.worker_queue_visibility_timeout_seconds,
    )
    while not shutdown.should_stop:
        try:
            _run_queue_worker_iteration(settings, worker_engine)
        except Exception:
            logger.exception("Unhandled error in queue worker iteration, backing off")
            time.sleep(settings.worker_poll_interval_seconds)
    logger.info("Worker %s stopped", settings.worker_id)


def _run_queue_worker_iteration(settings: Settings, worker_engine: Engine) -> None:
    with Session(worker_engine) as session:
        recovered_sources = recover_stale_sources(session, settings.worker_stale_timeout_seconds)
        if recovered_sources:
            logger.info("Recovered %d stale sources", recovered_sources)
        source_messages = read_source_extraction_messages(
            session,
            visibility_timeout_seconds=settings.worker_queue_visibility_timeout_seconds,
            max_poll_seconds=settings.worker_queue_max_poll_seconds,
            poll_interval_ms=settings.worker_queue_poll_interval_ms,
        )
        session.commit()

    for message in source_messages:
        process_source_extraction_message(message, worker_engine, settings)

    _drain_push_notifications(settings, worker_engine)


def run_worker() -> None:
    settings = get_settings()
    worker_engine = resolve_worker_engine(settings)
    check_worker_database_role(worker_engine, require_postgres=settings.is_production)

    shutdown = ShutdownFlag()
    install_signal_handlers(shutdown)

    if worker_engine.dialect.name == "postgresql":
        _run_queue_worker(settings, worker_engine, shutdown)
        return
    _run_polling_worker(settings, worker_engine, shutdown)


def main() -> None:
    settings = get_settings()
    level = logging.INFO if settings.is_production else logging.DEBUG
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    configure_tracing(settings)
    try:
        run_worker()
    finally:
        # Send queued traces before exit; SIGTERM ends run_worker() normally, SIGKILL skips it.
        shutdown_tracing()


if __name__ == "__main__":
    main()
