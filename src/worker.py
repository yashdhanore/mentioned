from __future__ import annotations

import asyncio
import logging
import time

from sqlmodel import Session
from sqlalchemy.engine import Engine

from src.books.service import upsert_google_book
from src.config import Settings, get_settings
from src.database import check_worker_database_role, create_sql_engine, engine
from src.extraction.google_books import find_google_book
from src.extraction.pipeline import run_pipeline
from src.extraction.schemas import GoogleBook
from src.jobs.models import Job, JobStatus
from src.jobs.queue import (
    ExtractJobMessage,
    archive_extract_job_message,
    read_extract_job_messages,
)
from src.jobs.service import (
    claim_job_by_id,
    claim_next_job,
    complete_job,
    fail_job,
    get_job,
    recover_stale_jobs,
)
from src.mentions.models import Mention
from src.push.expo import PushDeliveryRetryableError, send_job_push_notifications
from src.push.queue import (
    PushNotificationMessage,
    archive_push_notification_message,
    read_push_notification_messages,
)
from src.push.service import (
    disable_push_token_value,
    list_active_push_tokens,
)
from src.storage.thumbnails import store_job_thumbnail

logger = logging.getLogger(__name__)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _find_google_book_sync(title: str, author: str | None) -> GoogleBook | None:
    """Run async Google Books enrichment synchronously."""
    try:
        return asyncio.run(find_google_book(title, author))
    except Exception as exc:
        logger.warning("Google Books enrichment failed: %s", exc)
        return None


def process_job(job: Job, session: Session) -> None:
    logger.info("Starting pipeline for job %s → %s", job.id, job.source_url)
    result = run_pipeline(job.source_url)
    job.thumbnail_url = store_job_thumbnail(
        result.thumbnail_url,
        owner_id=job.owner_id,
        job_id=job.id,
    )
    if result.error:
        logger.warning("Job %s failed: %s", job.id, result.error)
        fail_job(session, job, result.error)
        return
    logger.info("Job %s extracted %d mentions", job.id, len(result.mentions))

    mentions = []
    for m in result.mentions:
        mention = Mention(
            owner_id=job.owner_id,
            job_id=job.id,
            title=m.title,
            author=m.author,
            category=m.category,
            confidence=m.confidence,
            source_url=job.source_url,
        )

        if m.category == "book":
            google_book = _find_google_book_sync(m.title, m.author)
            if google_book:
                book = upsert_google_book(session, google_book)
                mention.book_id = book.id
                mention.title = book.title
                mention.author = ", ".join(book.authors) or m.author
                mention.google_books_url = book.info_link
                mention.cover_image_url = book.cover_image_url
                mention.confidence = _clamp(m.confidence + 0.05)

        mentions.append(mention)

    complete_job(session, job, mentions)


def resolve_worker_engine(settings: Settings) -> Engine:
    if settings.worker_database_url:
        return create_sql_engine(settings.worker_database_url)
    if settings.is_production:
        raise RuntimeError("Production worker requires WORKER_DATABASE_URL")
    return engine


def process_extract_job_message(
    message: ExtractJobMessage,
    worker_engine: Engine,
    settings: Settings,
) -> None:
    logger.info(
        "Processing extract queue message %s for job %s (read_count=%s)",
        message.msg_id,
        message.job_id,
        message.read_count,
    )
    with Session(worker_engine) as session:
        job = get_job(session, message.job_id)
        if not job:
            logger.warning(
                "Archiving queue message %s for missing job %s (read_count=%s)",
                message.msg_id,
                message.job_id,
                message.read_count,
            )
            archive_extract_job_message(session, message.msg_id)
            session.commit()
            return
        if job.status != JobStatus.PENDING:
            logger.info(
                "Archiving queue message %s for terminal job %s (%s, read_count=%s)",
                message.msg_id,
                job.id,
                job.status,
                message.read_count,
            )
            archive_extract_job_message(session, message.msg_id)
            session.commit()
            return
        if job.locked_by is not None:
            logger.info(
                "Leaving queue message %s unarchived for locked job %s (read_count=%s); "
                "retry waits for queue visibility timeout and stale lock recovery",
                message.msg_id,
                job.id,
                message.read_count,
            )
            return

        job = claim_job_by_id(session, message.job_id, settings.worker_id)
        if not job:
            logger.info(
                "Leaving queue message %s unarchived because job %s was claimed by another worker (read_count=%s)",
                message.msg_id,
                message.job_id,
                message.read_count,
            )
            return

    logger.info(
        "Claimed queued job %s from queue message %s (%s, read_count=%s)",
        job.id,
        message.msg_id,
        job.source_url,
        message.read_count,
    )
    with Session(worker_engine) as session:
        job = session.get(Job, job.id)
        if not job:
            logger.warning(
                "Archiving queue message %s for missing claimed job %s (read_count=%s)",
                message.msg_id,
                message.job_id,
                message.read_count,
            )
            archive_extract_job_message(session, message.msg_id)
            session.commit()
            return
        process_job(job, session)
        archive_extract_job_message(session, message.msg_id)
        session.commit()
        logger.info(
            "Archived queue message %s for job %s (read_count=%s)",
            message.msg_id,
            job.id,
            message.read_count,
        )


def process_push_notification_message(
    message: PushNotificationMessage,
    worker_engine: Engine,
) -> None:
    with Session(worker_engine) as session:
        job = get_job(session, message.job_id)
        if not job:
            logger.warning(
                "Archiving push message %s for missing job %s",
                message.msg_id,
                message.job_id,
            )
            archive_push_notification_message(session, message.msg_id)
            session.commit()
            return
        if job.status == JobStatus.PENDING:
            logger.info(
                "Leaving push message %s unarchived for pending job %s",
                message.msg_id,
                job.id,
            )
            return
        tokens = list_active_push_tokens(session, job.owner_id)

    try:
        result = send_job_push_notifications(job, tokens)
    except PushDeliveryRetryableError as exc:
        logger.warning(
            "Leaving push message %s unarchived after retryable delivery failure: %s",
            message.msg_id,
            exc,
        )
        return

    with Session(worker_engine) as session:
        for expo_push_token in result.disabled_tokens:
            disable_push_token_value(session, expo_push_token)
        archive_push_notification_message(session, message.msg_id)
        session.commit()
        logger.info("Archived push message %s for job %s", message.msg_id, job.id)


def _drain_push_notifications(settings: Settings, worker_engine: Engine) -> None:
    with Session(worker_engine) as session:
        messages = read_push_notification_messages(
            session,
            visibility_timeout_seconds=settings.worker_queue_visibility_timeout_seconds,
        )
        session.commit()

    for message in messages:
        process_push_notification_message(message, worker_engine)


def _run_polling_worker(settings: Settings, worker_engine: Engine) -> None:
    worker_id = settings.worker_id
    poll_interval = settings.worker_poll_interval_seconds
    stale_timeout = settings.worker_stale_timeout_seconds

    logger.info("Worker %s starting in polling mode (poll=%.1fs)", worker_id, poll_interval)
    while True:
        with Session(worker_engine) as session:
            recovered = recover_stale_jobs(session, stale_timeout)
            if recovered:
                logger.info("Recovered %d stale jobs", recovered)
            job = claim_next_job(session, worker_id)

        if not job:
            logger.debug("No pending jobs, sleeping %.1fs", poll_interval)
            time.sleep(poll_interval)
            continue

        logger.info("Claimed job %s (%s)", job.id, job.source_url)
        with Session(worker_engine) as session:
            job = session.get(Job, job.id)
            if job:
                process_job(job, session)
                logger.info("Job %s finished with status: %s", job.id, job.status)


def _run_queue_worker(settings: Settings, worker_engine: Engine) -> None:
    logger.info(
        "Worker %s starting in queue mode (visibility_timeout=%ss)",
        settings.worker_id,
        settings.worker_queue_visibility_timeout_seconds,
    )
    while True:
        with Session(worker_engine) as session:
            recovered = recover_stale_jobs(session, settings.worker_stale_timeout_seconds)
            if recovered:
                logger.info("Recovered %d stale jobs", recovered)
            messages = read_extract_job_messages(
                session,
                visibility_timeout_seconds=settings.worker_queue_visibility_timeout_seconds,
                max_poll_seconds=settings.worker_queue_max_poll_seconds,
                poll_interval_ms=settings.worker_queue_poll_interval_ms,
            )
            session.commit()

        for message in messages:
            process_extract_job_message(message, worker_engine, settings)
        _drain_push_notifications(settings, worker_engine)


def run_worker() -> None:
    settings = get_settings()
    worker_engine = resolve_worker_engine(settings)
    check_worker_database_role(worker_engine, require_postgres=settings.is_production)

    if worker_engine.dialect.name == "postgresql":
        _run_queue_worker(settings, worker_engine)
        return
    _run_polling_worker(settings, worker_engine)


def main() -> None:
    settings = get_settings()
    level = logging.DEBUG if not settings.is_production else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_worker()


if __name__ == "__main__":
    main()
