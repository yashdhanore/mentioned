from __future__ import annotations

from sqlmodel import Session, select

from src.books.enrichment import enrich_extracted_book_item
from src.books.models import Book
from src.books.schemas import GoogleBook
from src.extraction.schemas import ExtractedMention
from src.sources.models import SourceItem


def _google_book() -> GoogleBook:
    return GoogleBook(
        provider_volume_id="google-volume-1",
        title="Atomic Habits",
        authors=["James Clear"],
        industry_identifiers=[{"type": "ISBN_13", "identifier": "9780735211292"}],
        cover_image_url="https://books.google.com/thumb.jpg",
        info_link="https://books.google.com/books?id=google-volume-1",
        raw_provider_payload={"id": "google-volume-1"},
    )


def _item() -> SourceItem:
    return SourceItem(
        title="Atomic Habits",
        author="James Clear",
        category="book",
        confidence=0.98,
        position=0,
    )


def test_enrich_extracted_book_item_links_book_and_clamps_confidence(
    session: Session,
) -> None:
    item = _item()
    extracted = ExtractedMention(
        title="Atomic Habits",
        author="James Clear",
        category="book",
        confidence=0.98,
    )

    enrich_extracted_book_item(
        session,
        item,
        extracted,
        book_finder=lambda _title, _author: _google_book(),
    )

    books = list(session.exec(select(Book)).all())
    assert len(books) == 1
    assert item.book_id == books[0].id
    assert item.title == "Atomic Habits"
    assert item.author == "James Clear"
    assert item.google_books_url == "https://books.google.com/books?id=google-volume-1"
    assert item.cover_image_url == "https://books.google.com/thumb.jpg"
    assert item.confidence == 1.0


def test_enrich_extracted_book_item_leaves_item_when_provider_misses(
    session: Session,
) -> None:
    item = _item()
    extracted = ExtractedMention(
        title="Atomic Habits",
        author="James Clear",
        category="book",
        confidence=0.72,
    )

    enrich_extracted_book_item(
        session,
        item,
        extracted,
        book_finder=lambda _title, _author: None,
    )

    assert list(session.exec(select(Book)).all()) == []
    assert item.book_id is None
    assert item.title == "Atomic Habits"
    assert item.confidence == 0.72
