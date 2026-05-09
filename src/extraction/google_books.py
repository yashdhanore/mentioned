from __future__ import annotations

from typing import Any
import logging

import httpx

from src.config import get_settings
from src.extraction.schemas import BookEnrichment, GoogleBook

logger = logging.getLogger(__name__)

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"


def _search_query(title: str, author: str | None) -> str:
    query = f"intitle:{title}"
    if author:
        query += f"+inauthor:{author}"
    return query


async def _fetch_first_volume(title: str, author: str | None) -> tuple[dict[str, Any] | None, str]:
    query = _search_query(title, author)
    params: dict[str, str | int] = {"q": query, "maxResults": 1}
    api_key = get_settings().google_books.api_key
    if api_key:
        params["key"] = api_key

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(GOOGLE_BOOKS_API, params=params)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Google Books API error: %s", exc)
        return None, "error"

    data = resp.json()
    if not data.get("totalItems"):
        return None, "not_found"

    items = data.get("items") or []
    if not items:
        return None, "not_found"

    return items[0], "found"


def _image_links(volume_info: dict[str, Any]) -> dict[str, str]:
    links = volume_info.get("imageLinks") or {}
    return {str(key): str(value) for key, value in links.items() if value}


def _cover_image_url(image_links: dict[str, str]) -> str | None:
    for key in ("thumbnail", "smallThumbnail", "small", "medium", "large", "extraLarge"):
        if image_links.get(key):
            return image_links[key]
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


def _parse_google_book(volume: dict[str, Any]) -> GoogleBook | None:
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


async def find_google_book(title: str, author: str | None) -> GoogleBook | None:
    volume, _status = await _fetch_first_volume(title, author)
    if volume is None:
        return None
    return _parse_google_book(volume)


async def enrich_book(title: str, author: str | None) -> BookEnrichment:
    volume, status = await _fetch_first_volume(title, author)
    if status == "error":
        return BookEnrichment(confidence_boost=0.0)
    if volume is None:
        return BookEnrichment(confidence_boost=-0.1)

    google_book = _parse_google_book(volume)
    if google_book is None:
        return BookEnrichment(confidence_boost=0.0)

    return BookEnrichment(
        canonical_title=google_book.title,
        canonical_author=", ".join(google_book.authors) or None,
        google_books_url=google_book.info_link,
        cover_image_url=google_book.cover_image_url,
        confidence_boost=0.05,
    )
