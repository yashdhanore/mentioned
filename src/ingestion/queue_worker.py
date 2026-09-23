from __future__ import annotations

import logging
from typing import Protocol

from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.config import Settings
from src.ingestion.source_processor import default_source_ingestion
from src.sources.failure import SourceFailureReason, safe_source_error_message
from src.sources.models import Source, SourceStatus
from src.sources.queue import SourceExtractionMessage, archive_source_extraction_message
from src.sources.service import (
    claim_source_for_processing,
    fail_source_processing,
    fail_source_processing_forcibly,
)

logger = logging.getLogger(__name__)


class SourceIngestionProcessor(Protocol):
    def process_source(self, session: Session, source: Source) -> bool: ...


def _archive_poison_message(
    message: SourceExtractionMessage, worker_engine: Engine, settings: Settings
) -> None:
    logger.error(
        "Source queue message %s exceeded max deliveries (read_count=%s > %s) for source %s; "
        "failing source and archiving message",
        message.msg_id,
        message.read_count,
        settings.worker_queue_max_deliveries,
        message.source_id,
    )
    with Session(worker_engine) as session:
        fail_source_processing_forcibly(
            session,
            message.source_id,
            safe_source_error_message(SourceFailureReason.TOO_MANY_ATTEMPTS),
        )
        archive_source_extraction_message(session, message.msg_id)
        session.commit()


def process_source_extraction_message(
    message: SourceExtractionMessage,
    worker_engine: Engine,
    settings: Settings,
    ingestion: SourceIngestionProcessor = default_source_ingestion,
) -> None:
    logger.info(
        "Processing source queue message %s for source %s (read_count=%s)",
        message.msg_id,
        message.source_id,
        message.read_count,
    )
    if message.read_count > settings.worker_queue_max_deliveries:
        _archive_poison_message(message, worker_engine, settings)
        return
    with Session(worker_engine) as session:
        source = session.get(Source, message.source_id)
        if not source:
            logger.warning(
                "Archiving source queue message %s for missing source %s (read_count=%s)",
                message.msg_id,
                message.source_id,
                message.read_count,
            )
            archive_source_extraction_message(session, message.msg_id)
            session.commit()
            return
        if source.status in (SourceStatus.DONE, SourceStatus.FAILED):
            logger.info(
                "Archiving source queue message %s for terminal source %s (%s, read_count=%s)",
                message.msg_id,
                source.id,
                source.status,
                message.read_count,
            )
            archive_source_extraction_message(session, message.msg_id)
            session.commit()
            return
        if source.status == SourceStatus.PROCESSING:
            logger.info(
                "Leaving source queue message %s unarchived for processing source %s "
                "(read_count=%s); retry waits for queue visibility timeout and stale source "
                "recovery",
                message.msg_id,
                source.id,
                message.read_count,
            )
            return

        source = claim_source_for_processing(session, message.source_id)
        if not source:
            logger.info(
                "Leaving source queue message %s unarchived because source %s was claimed by "
                "another worker (read_count=%s)",
                message.msg_id,
                message.source_id,
                message.read_count,
            )
            return

    logger.info(
        "Claimed queued source %s from source queue message %s (%s, read_count=%s)",
        source.id,
        message.msg_id,
        source.canonical_url,
        message.read_count,
    )
    with Session(worker_engine) as session:
        source = session.get(Source, source.id)
        if not source:
            logger.warning(
                "Archiving source queue message %s for missing claimed source %s (read_count=%s)",
                message.msg_id,
                message.source_id,
                message.read_count,
            )
            archive_source_extraction_message(session, message.msg_id)
            session.commit()
            return
        source_id = source.id
        should_archive = False
        try:
            should_archive = ingestion.process_source(session, source)
        except Exception:
            # Roll back first: after a failed flush the session refuses every query, even
            # reading an attribute of `source`, which would crash this handler and leave the
            # source processing.
            session.rollback()
            logger.exception(
                "Source %s failed while processing queue message %s", source_id, message.msg_id
            )
            failed_source = session.get(Source, source_id)
            if failed_source:
                should_archive = fail_source_processing(
                    session,
                    failed_source,
                    safe_source_error_message(SourceFailureReason.UNEXPECTED_ERROR),
                )
            else:
                logger.warning(
                    "Archiving source queue message %s for missing failed source %s "
                    "(read_count=%s)",
                    message.msg_id,
                    message.source_id,
                    message.read_count,
                )
                should_archive = True
        if not should_archive:
            logger.info(
                "Leaving source queue message %s unarchived because source %s attempt was not "
                "finalized (read_count=%s)",
                message.msg_id,
                message.source_id,
                message.read_count,
            )
            return

        archive_source_extraction_message(session, message.msg_id)
        session.commit()
        logger.info(
            "Archived source queue message %s for source %s (read_count=%s)",
            message.msg_id,
            source_id,
            message.read_count,
        )
