from __future__ import annotations

import logging

import httpx

from src.config import get_settings
from src.extraction.schemas import BookEnrichment

logger = logging.getLogger(__name__)

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"


async def enrich_book(title: str, author: str | None) -> BookEnrichment:
    query = f"intitle:{title}"
    if author:
        query += f"+inauthor:{author}"
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
        return BookEnrichment(confidence_boost=0.0)

    data = resp.json()
    if not data.get("totalItems"):
        return BookEnrichment(confidence_boost=-0.1)

    volume = data["items"][0]["volumeInfo"]
    return BookEnrichment(
        canonical_title=volume.get("title"),
        canonical_author=", ".join(volume.get("authors", [])) or None,
        google_books_url=f"https://books.google.com/books?id={data['items'][0]['id']}",
        cover_image_url=volume.get("imageLinks", {}).get("thumbnail"),
        confidence_boost=0.05,
    )
