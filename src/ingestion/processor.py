from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from sqlmodel import Session

from src.books.service import upsert_google_book
from src.extraction.google_books import find_google_book
from src.extraction.pipeline import run_pipeline
from src.extraction.schemas import GoogleBook, PipelineResult
from src.jobs.models import Job
from src.jobs.service import complete_job, fail_job
from src.mentions.models import Mention
from src.storage.thumbnails import store_job_thumbnail


logger = logging.getLogger(__name__)


class ThumbnailStore(Protocol):
    def __call__(self, thumbnail_url: str | None, *, owner_id: UUID, job_id: UUID) -> str | None:
        ...


ExtractionRunner = Callable[[str], PipelineResult]
BookFinder = Callable[[str, str | None], GoogleBook | None]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _find_google_book_sync(title: str, author: str | None) -> GoogleBook | None:
    """Run async Google Books enrichment synchronously."""
    try:
        return asyncio.run(find_google_book(title, author))
    except Exception as exc:
        logger.warning("Google Books enrichment failed: %s", exc)
        return None


class SavedSourceIngestion:
    def __init__(
        self,
        *,
        extraction_runner: ExtractionRunner = run_pipeline,
        thumbnail_store: ThumbnailStore = store_job_thumbnail,
        book_finder: BookFinder = _find_google_book_sync,
    ) -> None:
        self._extraction_runner = extraction_runner
        self._thumbnail_store = thumbnail_store
        self._book_finder = book_finder

    def process_job(self, session: Session, job: Job) -> None:
        logger.info("Starting pipeline for job %s -> %s", job.id, job.source_url)
        result = self._extraction_runner(job.source_url)
        job.source_creator_handle = result.source_creator_handle
        job.thumbnail_url = self._thumbnail_store(
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
        for extracted in result.mentions:
            mention = Mention(
                owner_id=job.owner_id,
                job_id=job.id,
                title=extracted.title,
                author=extracted.author,
                category=extracted.category,
                confidence=extracted.confidence,
                source_url=job.source_url,
            )

            if extracted.category == "book":
                google_book = self._book_finder(extracted.title, extracted.author)
                if google_book:
                    book = upsert_google_book(session, google_book)
                    mention.book_id = book.id
                    mention.title = book.title
                    mention.author = ", ".join(book.authors) or extracted.author
                    mention.google_books_url = book.info_link
                    mention.cover_image_url = book.cover_image_url
                    mention.confidence = _clamp(extracted.confidence + 0.05)

            mentions.append(mention)

        complete_job(session, job, mentions)


default_ingestion = SavedSourceIngestion()
