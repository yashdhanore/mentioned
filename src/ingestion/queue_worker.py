from __future__ import annotations

import logging
from typing import Protocol

from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.config import Settings
from src.ingestion.processor import default_ingestion
from src.ingestion.source_processor import default_source_ingestion
from src.jobs.models import Job, JobStatus
from src.jobs.queue import ExtractJobMessage, archive_extract_job_message
from src.jobs.service import claim_job_by_id, get_job
from src.sources.models import Source, SourceStatus
from src.sources.queue import SourceExtractionMessage, archive_source_extraction_message
from src.sources.service import claim_source_for_processing, fail_source_processing


logger = logging.getLogger(__name__)


class IngestionProcessor(Protocol):
    def process_job(self, session: Session, job: Job) -> None:
        ...


class SourceIngestionProcessor(Protocol):
    def process_source(self, session: Session, source: Source) -> bool:
        ...


def process_extract_job_message(
    message: ExtractJobMessage,
    worker_engine: Engine,
    settings: Settings,
    ingestion: IngestionProcessor = default_ingestion,
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
        ingestion.process_job(session, job)
        archive_extract_job_message(session, message.msg_id)
        session.commit()
        logger.info(
            "Archived queue message %s for job %s (read_count=%s)",
            message.msg_id,
            job.id,
            message.read_count,
        )


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
                "Leaving source queue message %s unarchived for processing source %s (read_count=%s); "
                "retry waits for queue visibility timeout and stale source recovery",
                message.msg_id,
                source.id,
                message.read_count,
            )
            return

        source = claim_source_for_processing(session, message.source_id)
        if not source:
            logger.info(
                "Leaving source queue message %s unarchived because source %s was claimed by another worker "
                "(read_count=%s)",
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
        should_archive = False
        try:
            should_archive = ingestion.process_source(session, source)
        except Exception as exc:
            logger.exception("Source %s failed while processing queue message %s", source.id, message.msg_id)
            session.rollback()
            failed_source = session.get(Source, source.id)
            if failed_source:
                should_archive = fail_source_processing(session, failed_source, str(exc))
            else:
                logger.warning(
                    "Archiving source queue message %s for missing failed source %s (read_count=%s)",
                    message.msg_id,
                    message.source_id,
                    message.read_count,
                )
                should_archive = True
        if not should_archive:
            logger.info(
                "Leaving source queue message %s unarchived because source %s attempt was not finalized "
                "(read_count=%s)",
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
            source.id,
            message.read_count,
        )
