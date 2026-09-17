from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from src.books.enrichment import enrich_extracted_book_mention
from src.books.models import Book
from src.books.schemas import GoogleBook
from src.extraction.schemas import ExtractedMention
from src.mentions.models import Mention

OWNER = UUID("00000000-0000-4000-8000-000000000001")
JOB_ID = UUID("00000000-0000-4000-8000-000000000099")


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


def _mention() -> Mention:
    return Mention(
        owner_id=OWNER,
        job_id=JOB_ID,
        title="Atomic Habits",
        author="James Clear",
        category="book",
        confidence=0.98,
        source_url="https://www.instagram.com/reel/BOOK/",
    )


def test_enrich_extracted_book_mention_links_book_and_clamps_confidence(
    session: Session,
) -> None:
    mention = _mention()
    extracted = ExtractedMention(
        title="Atomic Habits",
        author="James Clear",
        category="book",
        confidence=0.98,
    )

    enrich_extracted_book_mention(
        session,
        mention,
        extracted,
        book_finder=lambda _title, _author: _google_book(),
    )

    books = list(session.exec(select(Book)).all())
    assert len(books) == 1
    assert mention.book_id == books[0].id
    assert mention.title == "Atomic Habits"
    assert mention.author == "James Clear"
    assert mention.google_books_url == "https://books.google.com/books?id=google-volume-1"
    assert mention.cover_image_url == "https://books.google.com/thumb.jpg"
    assert mention.confidence == 1.0


def test_enrich_extracted_book_mention_leaves_mention_when_provider_misses(
    session: Session,
) -> None:
    mention = _mention()
    extracted = ExtractedMention(
        title="Atomic Habits",
        author="James Clear",
        category="book",
        confidence=0.72,
    )

    enrich_extracted_book_mention(
        session,
        mention,
        extracted,
        book_finder=lambda _title, _author: None,
    )

    assert list(session.exec(select(Book)).all()) == []
    assert mention.book_id is None
    assert mention.title == "Atomic Habits"
    assert mention.confidence == 0.72
