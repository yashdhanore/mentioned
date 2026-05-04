from __future__ import annotations

import asyncio
import logging
import time

from sqlmodel import Session

from src.config import get_settings
from src.database import create_sql_engine, engine
from src.extraction.google_books import enrich_book
from src.extraction.pipeline import run_pipeline
from src.extraction.schemas import BookEnrichment
from src.jobs.models import Job
from src.jobs.service import claim_next_job, complete_job, fail_job, recover_stale_jobs
from src.mentions.models import Mention

logger = logging.getLogger(__name__)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _enrich_book_sync(title: str, author: str | None) -> BookEnrichment:
    """Run async Google Books enrichment synchronously."""
    try:
        return asyncio.run(enrich_book(title, author))
    except Exception as exc:
        logger.warning("Google Books enrichment failed: %s", exc)
        return BookEnrichment(confidence_boost=0.0)


def process_job(job: Job, session: Session) -> None:
    logger.info("Starting pipeline for job %s → %s", job.id, job.source_url)
    result = run_pipeline(job.source_url)
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
            enrichment = _enrich_book_sync(m.title, m.author)
            if enrichment.canonical_title:
                mention.title = enrichment.canonical_title
            if enrichment.canonical_author:
                mention.author = enrichment.canonical_author
            mention.google_books_url = enrichment.google_books_url
            mention.cover_image_url = enrichment.cover_image_url
            mention.confidence = _clamp(m.confidence + enrichment.confidence_boost)

        mentions.append(mention)

    complete_job(session, job, mentions)


def run_worker() -> None:
    settings = get_settings()
    worker_id = settings.worker_id
    poll_interval = settings.worker_poll_interval_seconds
    stale_timeout = settings.worker_stale_timeout_seconds

    # Use worker-specific DB URL if configured
    worker_engine = engine
    if settings.worker_database_url:
        worker_engine = create_sql_engine(settings.worker_database_url)

    logger.info("Worker %s starting (poll=%.1fs)", worker_id, poll_interval)

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


def main() -> None:
    settings = get_settings()
    level = logging.DEBUG if not settings.is_production else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_worker()


if __name__ == "__main__":
    main()
