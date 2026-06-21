from __future__ import annotations

import logging
from typing import Protocol

from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.config import Settings
from src.ingestion.processor import default_ingestion
from src.jobs.models import Job, JobStatus
from src.jobs.queue import ExtractJobMessage, archive_extract_job_message
from src.jobs.service import claim_job_by_id, get_job


logger = logging.getLogger(__name__)


class IngestionProcessor(Protocol):
    def process_job(self, session: Session, job: Job) -> None:
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
