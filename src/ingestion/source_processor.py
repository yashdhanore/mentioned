from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from sqlmodel import Session

from src.books.enrichment import BookFinder, enrich_extracted_book_mention, find_google_book_sync
from src.extraction.pipeline import run_pipeline
from src.extraction.schemas import PipelineResult
from src.mentions.models import Mention
from src.sources.models import Source, SourceItem
from src.sources.service import complete_source_processing, fail_source_processing
from src.storage.thumbnails import store_job_thumbnail


logger = logging.getLogger(__name__)


class ThumbnailStore(Protocol):
    def __call__(self, thumbnail_url: str | None, *, owner_id: UUID, job_id: UUID) -> str | None:
        ...


ExtractionRunner = Callable[[str], PipelineResult]


class SourceIngestion:
    def __init__(
        self,
        *,
        extraction_runner: ExtractionRunner = run_pipeline,
        thumbnail_store: ThumbnailStore = store_job_thumbnail,
        book_finder: BookFinder = find_google_book_sync,
    ) -> None:
        self._extraction_runner = extraction_runner
        self._thumbnail_store = thumbnail_store
        self._book_finder = book_finder

    def process_source(self, session: Session, source: Source) -> bool:
        logger.info("Starting pipeline for source %s -> %s", source.id, source.canonical_url)
        result = self._extraction_runner(source.canonical_url)
        source.creator_handle = result.source_creator_handle
        source.thumbnail_url = self._thumbnail_store(
            result.thumbnail_url,
            owner_id=source.id,
            job_id=source.id,
        )
        if result.error:
            return fail_source_processing(session, source, result.error)

        items: list[SourceItem] = []
        for position, extracted in enumerate(result.mentions):
            item = SourceItem(
                source_id=source.id,
                title=extracted.title,
                author=extracted.author,
                category=extracted.category,
                confidence=extracted.confidence,
                position=position,
            )
            if extracted.category == "book":
                mention = Mention(
                    owner_id=source.id,
                    job_id=source.id,
                    title=extracted.title,
                    author=extracted.author,
                    category=extracted.category,
                    confidence=extracted.confidence,
                    source_url=source.canonical_url,
                )
                enrich_extracted_book_mention(
                    session,
                    mention,
                    extracted,
                    book_finder=self._book_finder,
                )
                item.book_id = mention.book_id
                item.title = mention.title
                item.author = mention.author
                item.google_books_url = mention.google_books_url
                item.cover_image_url = mention.cover_image_url
                item.confidence = mention.confidence
            items.append(item)

        return complete_source_processing(session, source, items, skip_reason=result.skip_reason)


default_source_ingestion = SourceIngestion()
