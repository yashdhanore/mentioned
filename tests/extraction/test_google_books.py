from __future__ import annotations

import logging

import httpx
import pytest
import respx
from httpx import Response

from src.config import get_settings
from src.extraction.google_books import GOOGLE_BOOKS_API, book_search_query, search_volumes


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _volume(volume_id: str, title: str, authors: list[str], **info) -> dict:
    return {"id": volume_id, "volumeInfo": {"title": title, "authors": authors, **info}}


def test_book_search_query_adds_author_only_when_known():
    assert book_search_query("Dune", "Frank Herbert") == "intitle:Dune+inauthor:Frank Herbert"
    assert book_search_query("Dune", None) == "intitle:Dune"


@respx.mock
def test_search_volumes_returns_every_parsed_volume():
    route = respx.get(GOOGLE_BOOKS_API).mock(
        return_value=Response(
            200,
            json={
                "totalItems": 2,
                "items": [
                    _volume(
                        "abc123",
                        "Atomic Habits",
                        ["James Clear"],
                        imageLinks={"thumbnail": "http://books.google.com/thumb.jpg"},
                    ),
                    _volume("def456", "Atomic Habits Summary", ["Someone Else"]),
                    {"id": "no-title", "volumeInfo": {}},
                ],
            },
        )
    )

    result = search_volumes("intitle:Atomic Habits")

    assert result.status == "found"
    assert [book.provider_volume_id for book in result.books] == ["abc123", "def456"]
    assert result.books[0].cover_image_url == "https://books.google.com/thumb.jpg"
    assert result.books[0].info_link == "https://books.google.com/books?id=abc123"
    assert route.calls.last.request.url.params["maxResults"] == "5"


@respx.mock
def test_search_volumes_sends_api_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_BOOKS_API_KEY", "test-books-key")
    route = respx.get(GOOGLE_BOOKS_API).mock(
        return_value=Response(200, json={"totalItems": 0, "items": []})
    )

    search_volumes("intitle:Atomic Habits", max_results=1)

    assert route.calls.last.request.url.params["key"] == "test-books-key"
    assert route.calls.last.request.url.params["maxResults"] == "1"


@respx.mock
def test_search_volumes_reports_not_found_separately_from_errors():
    respx.get(GOOGLE_BOOKS_API).mock(
        return_value=Response(200, json={"totalItems": 0, "items": []})
    )

    assert search_volumes("intitle:Nonexistent").status == "not_found"


@respx.mock
def test_search_volumes_reports_http_error_without_logging_the_key(monkeypatch, caplog):
    monkeypatch.setenv("GOOGLE_BOOKS_API_KEY", "secret-books-key")
    respx.get(GOOGLE_BOOKS_API).mock(return_value=Response(429))

    with caplog.at_level(logging.WARNING):
        result = search_volumes("intitle:Some Book")

    assert result.status == "error"
    assert result.books == []
    assert "429" in caplog.text
    assert "secret-books-key" not in caplog.text


@respx.mock
def test_search_volumes_reports_network_failure_as_error():
    respx.get(GOOGLE_BOOKS_API).mock(side_effect=httpx.ConnectTimeout("timed out"))

    assert search_volumes("intitle:Some Book").status == "error"
