from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from langfuse import propagate_attributes
from sqlmodel import Session

from src.books.enrichment import BookFinder, enrich_extracted_book_item
from src.books.resolution import find_resolved_book
from src.extraction.pipeline import run_pipeline
from src.extraction.schemas import PipelineResult
from src.observability import langfuse, observe_step
from src.places.enrichment import PlaceFinder, enrich_extracted_place_item, find_google_place_sync
from src.sources.models import Source, SourceItem
from src.sources.service import complete_source_processing, fail_source_processing
from src.storage.thumbnails import store_source_thumbnail

logger = logging.getLogger(__name__)


class ThumbnailStore(Protocol):
    def __call__(self, thumbnail_url: str | None, *, source_id: UUID) -> str | None: ...


ExtractionRunner = Callable[[str], PipelineResult]


class SourceIngestion:
    def __init__(
        self,
        *,
        extraction_runner: ExtractionRunner = run_pipeline,
        thumbnail_store: ThumbnailStore = store_source_thumbnail,
        book_finder: BookFinder = find_resolved_book,
        place_finder: PlaceFinder = find_google_place_sync,
    ) -> None:
        self._extraction_runner = extraction_runner
        self._thumbnail_store = thumbnail_store
        self._book_finder = book_finder
        self._place_finder = place_finder

    def process_source(self, session: Session, source: Source) -> bool:
        """Extract one claimed source and store the outcome.

        One attempt is one `extract-source` trace. Its session is the source id, so every
        attempt at the same Reel groups together; it carries no user id, because a source is
        shared by everyone who saved it."""
        logger.info("Starting pipeline for source %s -> %s", source.id, source.canonical_url)
        with (
            observe_step(
                "extract-source",
                input={"source_url": source.canonical_url},
                metadata={"source_id": str(source.id), "source_key": source.source_key},
            ) as trace_root,
            propagate_attributes(
                session_id=str(source.id),
                trace_name="extract-source",
                tags=[source.platform, source.source_type],
            ),
        ):
            attempt = self._process(session, source)
            if attempt.outcome == "failed":
                trace_root.update(
                    output=attempt.view(), level="ERROR", status_message=attempt.error
                )
            else:
                trace_root.update(output=attempt.view())
            langfuse().score_current_trace(
                name="extraction-outcome", value=attempt.outcome, data_type="CATEGORICAL"
            )
            return attempt.stored

    def _process(self, session: Session, source: Source) -> _Attempt:
        result = self._extraction_runner(source.canonical_url)
        source.creator_handle = result.source_creator_handle
        source.thumbnail_url = self._thumbnail_store(result.thumbnail_url, source_id=source.id)
        if result.error:
            stored = fail_source_processing(session, source, result.error)
            return _Attempt(stored=stored, outcome="failed", error=result.error)

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
                enrich_extracted_book_item(
                    session,
                    item,
                    extracted,
                    book_finder=self._book_finder,
                )
            elif extracted.category == "place":
                enrich_extracted_place_item(
                    session,
                    item,
                    extracted,
                    place_finder=self._place_finder,
                )
            items.append(item)

        # Read before the commit below expires the items.
        item_views = [_item_view(item) for item in items]
        stored = complete_source_processing(session, source, items, skip_reason=result.skip_reason)
        return _Attempt(
            stored=stored,
            outcome="skipped" if result.skip_reason else "done",
            skip_reason=result.skip_reason,
            items=item_views,
        )


@dataclass(frozen=True)
class _Attempt:
    """What one attempt produced. `stored` is False when another attempt had taken over the
    source, so this attempt's outcome was discarded."""

    stored: bool
    outcome: str
    error: str | None = None
    skip_reason: str | None = None
    items: list[dict[str, object]] = field(default_factory=list)

    def view(self) -> dict[str, object]:
        return {
            "outcome": self.outcome,
            "stored": self.stored,
            "error": self.error,
            "skip_reason": self.skip_reason,
            "items": self.items,
        }


def _item_view(item: SourceItem) -> dict[str, object]:
    return {
        "title": item.title,
        "author": item.author,
        "category": item.category,
        "confidence": item.confidence,
        "catalog_match": item.book_id is not None,
    }


default_source_ingestion = SourceIngestion()
