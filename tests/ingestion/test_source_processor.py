from __future__ import annotations

from sqlmodel import Session, select

from src.books.models import Book
from src.books.schemas import GoogleBook
from src.extraction.schemas import ExtractedMention, PipelineResult
from src.ingestion.source_processor import SourceIngestion
from src.sources.models import Source, SourceItem, SourceStatus


def _google_book() -> GoogleBook:
    return GoogleBook(
        provider_volume_id="google-volume-1",
        provider_etag="etag-1",
        provider_self_link="https://www.googleapis.com/books/v1/volumes/google-volume-1",
        title="Atomic Habits",
        authors=["James Clear"],
        industry_identifiers=[
            {"type": "ISBN_13", "identifier": "9780735211292"},
            {"type": "ISBN_10", "identifier": "0735211299"},
        ],
        image_links={"thumbnail": "https://books.google.com/thumb.jpg"},
        cover_image_url="https://books.google.com/thumb.jpg",
        info_link="https://books.google.com/books?id=google-volume-1",
        canonical_volume_link="https://books.google.com/books/about/Atomic_Habits.html?id=google-volume-1",
        raw_provider_payload={"id": "google-volume-1"},
    )


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
        thumbnail_store=lambda _url, *, owner_id, job_id: "https://cdn.example/thumb.jpg",
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


def test_source_processor_copies_google_books_enrichment_to_source_item(session: Session) -> None:
    source = Source(
        source_key="instagram:reel:BOOK123",
        platform="instagram",
        source_type="reel",
        external_id="BOOK123",
        canonical_url="https://www.instagram.com/reel/BOOK123/",
        status=SourceStatus.PROCESSING,
    )
    session.add(source)
    session.commit()
    session.refresh(source)

    processor = SourceIngestion(
        extraction_runner=lambda _url: PipelineResult(
            mentions=[
                ExtractedMention(
                    title="Atomic Habits",
                    author="James Clear",
                    category="book",
                    confidence=0.91,
                )
            ],
        ),
        thumbnail_store=lambda _url, *, owner_id, job_id: None,
        book_finder=lambda _title, _author: _google_book(),
    )

    processed = processor.process_source(session, source)

    books = list(session.exec(select(Book)).all())
    item = session.exec(select(SourceItem).where(SourceItem.source_id == source.id)).one()

    assert processed is True
    assert len(books) == 1
    assert item.book_id == books[0].id
    assert item.google_books_url == books[0].info_link
    assert item.cover_image_url == books[0].cover_image_url
