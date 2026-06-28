from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from sqlmodel import Session

from src.books.schemas import GoogleBook
from src.books.service import upsert_google_book
from src.extraction.google_books import find_google_book
from src.extraction.schemas import ExtractedMention
from src.mentions.models import Mention


logger = logging.getLogger(__name__)

BookFinder = Callable[[str, str | None], GoogleBook | None]


def clamp_confidence(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def find_google_book_sync(title: str, author: str | None) -> GoogleBook | None:
    try:
        return asyncio.run(find_google_book(title, author))
    except Exception as exc:
        logger.warning("Google Books enrichment failed: %s", exc)
        return None


def enrich_extracted_book_mention(
    session: Session,
    mention: Mention,
    extracted: ExtractedMention,
    *,
    book_finder: BookFinder = find_google_book_sync,
) -> None:
    mention.title = extracted.title
    mention.author = extracted.author
    mention.category = extracted.category
    mention.confidence = extracted.confidence

    google_book = book_finder(extracted.title, extracted.author)
    if not google_book:
        return

    book = upsert_google_book(session, google_book)
    mention.book_id = book.id
    mention.title = book.title
    mention.author = ", ".join(book.authors) or extracted.author
    mention.google_books_url = book.info_link
    mention.cover_image_url = book.cover_image_url
    mention.confidence = clamp_confidence(extracted.confidence + 0.05)
