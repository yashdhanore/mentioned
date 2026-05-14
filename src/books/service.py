from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from src.books.models import Book
from src.extraction.schemas import GoogleBook


def _identifier_value(
    identifiers: list[dict[str, Any]],
    identifier_type: str,
) -> str | None:
    for item in identifiers:
        if item.get("type") == identifier_type and item.get("identifier"):
            return str(item["identifier"])
    return None


def upsert_google_book(session: Session, google_book: GoogleBook) -> Book:
    stmt = select(Book).where(
        Book.provider == "google_books",
        Book.provider_volume_id == google_book.provider_volume_id,
    )
    book = session.exec(stmt).first()
    now = datetime.utcnow()

    fields = {
        "provider": "google_books",
        "provider_volume_id": google_book.provider_volume_id,
        "provider_etag": google_book.provider_etag,
        "provider_self_link": google_book.provider_self_link,
        "title": google_book.title,
        "subtitle": google_book.subtitle,
        "authors": google_book.authors,
        "publisher": google_book.publisher,
        "published_date": google_book.published_date,
        "description": google_book.description,
        "industry_identifiers": google_book.industry_identifiers,
        "isbn_10": _identifier_value(google_book.industry_identifiers, "ISBN_10"),
        "isbn_13": _identifier_value(google_book.industry_identifiers, "ISBN_13"),
        "page_count": google_book.page_count,
        "print_type": google_book.print_type,
        "language": google_book.language,
        "main_category": google_book.main_category,
        "categories": google_book.categories,
        "image_links": google_book.image_links,
        "cover_image_url": google_book.cover_image_url,
        "preview_link": google_book.preview_link,
        "info_link": google_book.info_link,
        "canonical_volume_link": google_book.canonical_volume_link,
        "sale_info": google_book.sale_info,
        "access_info": google_book.access_info,
        "raw_provider_payload": google_book.raw_provider_payload,
        "updated_at": now,
    }

    if book is None:
        book = Book(**fields)
    else:
        for key, value in fields.items():
            setattr(book, key, value)

    session.add(book)
    session.flush()
    return book
