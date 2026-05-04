from __future__ import annotations

import pytest
import respx
from httpx import Response

from src.extraction.google_books import GOOGLE_BOOKS_API, enrich_book


pytestmark = pytest.mark.asyncio


@respx.mock
async def test_enrich_book_found():
    respx.get(GOOGLE_BOOKS_API).mock(
        return_value=Response(
            200,
            json={
                "totalItems": 1,
                "items": [
                    {
                        "id": "abc123",
                        "volumeInfo": {
                            "title": "Atomic Habits",
                            "authors": ["James Clear"],
                            "imageLinks": {"thumbnail": "https://books.google.com/thumb.jpg"},
                        },
                    }
                ],
            },
        )
    )

    result = await enrich_book("Atomic Habits", "James Clear")
    assert result.canonical_title == "Atomic Habits"
    assert result.canonical_author == "James Clear"
    assert result.google_books_url == "https://books.google.com/books?id=abc123"
    assert result.cover_image_url == "https://books.google.com/thumb.jpg"
    assert result.confidence_boost == 0.05


@respx.mock
async def test_enrich_book_not_found():
    respx.get(GOOGLE_BOOKS_API).mock(
        return_value=Response(200, json={"totalItems": 0, "items": []})
    )

    result = await enrich_book("Nonexistent Book Title XYZ", None)
    assert result.canonical_title is None
    assert result.confidence_boost == -0.1


@respx.mock
async def test_enrich_book_api_error():
    respx.get(GOOGLE_BOOKS_API).mock(return_value=Response(500))

    result = await enrich_book("Some Book", None)
    assert result.canonical_title is None
    assert result.confidence_boost == 0.0
