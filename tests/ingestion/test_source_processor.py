from __future__ import annotations

from sqlmodel import Session, select

from src.extraction.schemas import ExtractedMention, PipelineResult
from src.ingestion.source_processor import SourceIngestion
from src.sources.models import Source, SourceItem, SourceStatus


def test_source_processor_writes_canonical_source_items(session: Session) -> None:
    source = Source(
        source_key="instagram:reel:ABC123",
        platform="instagram",
        source_type="reel",
        external_id="ABC123",
        canonical_url="https://www.instagram.com/reel/ABC123/",
        status=SourceStatus.PROCESSING,
    )
    session.add(source)
    session.commit()
    session.refresh(source)

    processor = SourceIngestion(
        extraction_runner=lambda _url: PipelineResult(
            thumbnail_url="https://instagram.example/thumb.jpg",
            source_creator_handle="jamesclear",
            mentions=[
                ExtractedMention(
                    title="Atomic Habits",
                    author="James Clear",
                    category="book",
                    confidence=0.91,
                )
            ],
        ),
        thumbnail_store=lambda _url, *, source_id: "https://cdn.example/thumb.jpg",
        book_finder=lambda _title, _author: None,
    )

    processed = processor.process_source(session, source)

    refreshed = session.get(Source, source.id)
    items = list(session.exec(select(SourceItem).where(SourceItem.source_id == source.id)).all())

    assert refreshed is not None
    assert processed is True
    assert refreshed.status == SourceStatus.DONE
    assert refreshed.thumbnail_url == "https://cdn.example/thumb.jpg"
    assert refreshed.creator_handle == "jamesclear"
    assert len(items) == 1
    assert items[0].title == "Atomic Habits"
    assert items[0].position == 0
