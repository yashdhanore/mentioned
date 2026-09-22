from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse, urlunparse

import httpx

from src.books.schemas import GoogleBook
from src.config import get_settings

logger = logging.getLogger(__name__)

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
DEFAULT_MAX_RESULTS = 5
REQUEST_TIMEOUT_SECONDS = 10.0

BooksSearchStatus = Literal["found", "not_found", "error"]


@dataclass(frozen=True)
class BooksSearchResult:
    """Outcome of one catalog query. `not_found` and `error` stay distinct: a
    not-found book is a signal about the mention, an error is not."""

    status: BooksSearchStatus
    books: list[GoogleBook] = field(default_factory=list)


def book_search_query(title: str, author: str | None) -> str:
    query = f"intitle:{title}"
    if author:
        query += f"+inauthor:{author}"
    return query


def search_volumes(query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> BooksSearchResult:
    params: dict[str, str | int] = {"q": query, "maxResults": max_results}
    api_key = get_settings().google_books.api_key
    if api_key:
        params["key"] = api_key

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            resp = client.get(GOOGLE_BOOKS_API, params=params)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # Never log the exception itself: its message includes the request URL and the key.
        logger.warning("Google Books API returned %s for query %r", exc.response.status_code, query)
        return BooksSearchResult(status="error")
    except httpx.HTTPError as exc:
        logger.warning(
            "Google Books API request failed for query %r: %s", query, type(exc).__name__
        )
        return BooksSearchResult(status="error")

    data = resp.json()
    books = [
        book
        for book in (parse_google_book(item) for item in data.get("items") or [])
        if book is not None
    ]
    if not books:
        return BooksSearchResult(status="not_found")
    return BooksSearchResult(status="found", books=books)


def _image_links(volume_info: dict[str, Any]) -> dict[str, str]:
    links = volume_info.get("imageLinks") or {}
    return {str(key): str(value) for key, value in links.items() if value}


def _normalize_cover_image_url(value: str) -> str | None:
    raw_url = value.strip()
    if not raw_url:
        return None

    try:
        parsed = urlparse(raw_url)
    except ValueError:
        return None

    scheme = parsed.scheme.casefold()
    hostname = (parsed.hostname or "").casefold()
    if scheme == "http" and hostname == "books.google.com":
        return urlunparse(parsed._replace(scheme="https"))
    if scheme == "https" and parsed.netloc:
        return raw_url
    return None


def _cover_image_url(image_links: dict[str, str]) -> str | None:
    for key in ("thumbnail", "smallThumbnail", "small", "medium", "large", "extraLarge"):
        if image_links.get(key):
            normalized_url = _normalize_cover_image_url(image_links[key])
            if normalized_url:
                return normalized_url
    return None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def _dict_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _dict_or_none(value: object) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def parse_google_book(volume: dict[str, Any]) -> GoogleBook | None:
    provider_volume_id = volume.get("id")
    volume_info = volume.get("volumeInfo") or {}
    title = volume_info.get("title")
    if not provider_volume_id or not title:
        return None

    image_links = _image_links(volume_info)
    fallback_info_link = f"https://books.google.com/books?id={provider_volume_id}"

    return GoogleBook(
        provider_volume_id=str(provider_volume_id),
        provider_etag=volume.get("etag"),
        provider_self_link=volume.get("selfLink"),
        title=str(title),
        subtitle=volume_info.get("subtitle"),
        authors=_string_list(volume_info.get("authors")),
        publisher=volume_info.get("publisher"),
        published_date=volume_info.get("publishedDate"),
        description=volume_info.get("description"),
        industry_identifiers=_dict_list(volume_info.get("industryIdentifiers")),
        page_count=volume_info.get("pageCount"),
        print_type=volume_info.get("printType"),
        language=volume_info.get("language"),
        main_category=volume_info.get("mainCategory"),
        categories=_string_list(volume_info.get("categories")),
        image_links=image_links,
        cover_image_url=_cover_image_url(image_links),
        preview_link=volume_info.get("previewLink"),
        info_link=volume_info.get("infoLink") or fallback_info_link,
        canonical_volume_link=volume_info.get("canonicalVolumeLink"),
        sale_info=_dict_or_none(volume.get("saleInfo")),
        access_info=_dict_or_none(volume.get("accessInfo")),
        raw_provider_payload=volume,
    )
