from __future__ import annotations

from collections.abc import Callable

from sqlmodel import Session

from src.books.resolution import find_resolved_book
from src.books.schemas import GoogleBook
from src.books.service import upsert_google_book
from src.extraction.schemas import ExtractedMention
from src.sources.models import SourceItem

BookFinder = Callable[[str, str | None], GoogleBook | None]


def clamp_confidence(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def enrich_extracted_book_item(
    session: Session,
    item: SourceItem,
    extracted: ExtractedMention,
    *,
    book_finder: BookFinder = find_resolved_book,
) -> None:
    item.title = extracted.title
    item.author = extracted.author
    item.category = extracted.category
    item.confidence = extracted.confidence

    google_book = book_finder(extracted.title, extracted.author)
    if not google_book:
        return

    book = upsert_google_book(session, google_book)
    item.book_id = book.id
    item.title = book.title
    item.author = ", ".join(book.authors) or extracted.author
    item.google_books_url = book.info_link
    item.cover_image_url = book.cover_image_url
    item.confidence = clamp_confidence(extracted.confidence + 0.05)
