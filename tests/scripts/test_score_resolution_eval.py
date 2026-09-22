from __future__ import annotations

from scripts.score_extraction_eval import ExpectedMention
from scripts.score_resolution_eval import CachedBooksSearch, Resolver, grade
from src.books.resolution import Resolution
from src.books.schemas import GoogleBook
from src.extraction.google_books import BooksSearchResult


def _expected(title: str, author: str | None = None, aliases: tuple[str, ...] = ()):
    return ExpectedMention(
        category="book", title=title, author=author, aliases=aliases, optional=False
    )


def _resolved(title: str, authors: list[str], subtitle: str | None = None) -> Resolution:
    book = GoogleBook(
        provider_volume_id="v1",
        title=title,
        subtitle=subtitle,
        authors=authors,
        raw_provider_payload={"id": "v1", "volumeInfo": {"title": title, "authors": authors}},
    )
    return Resolution(status="resolved", book=book)


def test_grade_separates_same_work_container_wrong_and_unresolved():
    white_nights = _expected("White Nights", "Fyodor Dostoevsky")

    assert grade(_resolved("White Nights", ["Fyodor Dostoyevsky"]), white_nights) == "same_work"
    assert (
        grade(_resolved("White Nights and Other Stories", ["Fyodor Dostoyevsky"]), white_nights)
        == "container"
    )
    assert grade(_resolved("Notes from Underground", ["Fyodor Dostoyevsky"]), white_nights) == (
        "wrong"
    )
    assert grade(Resolution(status="ambiguous"), white_nights) == "unresolved"


def test_grade_counts_summaries_and_other_authors_as_wrong():
    nightingale = _expected("The Nightingale", "Kristin Hannah")

    assert (
        grade(_resolved("The Nightingale", ["Kristin Hannah"], subtitle="A Summary"), nightingale)
        == "wrong"
    )
    assert grade(_resolved("The Nightingale", ["Someone Else"]), nightingale) == "wrong"


def test_grade_accepts_label_aliases():
    expected = _expected("Nineteen Eighty-Four", "George Orwell", aliases=("1984",))

    assert grade(_resolved("1984", ["George Orwell"]), expected) == "same_work"


def test_cache_serves_repeat_queries_without_calling_the_api(tmp_path):
    calls: list[tuple[str, int]] = []

    def live(query: str, *, max_results: int) -> BooksSearchResult:
        calls.append((query, max_results))
        return BooksSearchResult(status="found", books=[_resolved("Dune", ["Frank Herbert"]).book])

    search = CachedBooksSearch(tmp_path, live_search=live, sleep=lambda _s: None)

    first = search("intitle:Dune", max_results=5)
    second = search("intitle:Dune", max_results=5)
    search("intitle:Dune", max_results=1)

    assert first.status == second.status == "found"
    assert second.books[0].title == "Dune"
    assert calls == [("intitle:Dune", 5), ("intitle:Dune", 1)]
    assert search.cache_hits == 1


def test_cache_retries_errors_and_never_stores_them(tmp_path):
    attempts: list[str] = []

    def live(query: str, *, max_results: int) -> BooksSearchResult:
        attempts.append(query)
        return BooksSearchResult(status="error")

    search = CachedBooksSearch(tmp_path, live_search=live, sleep=lambda _s: None)

    assert search("intitle:Dune").status == "error"
    assert len(attempts) == 4
    assert list(tmp_path.iterdir()) == []


def test_resolver_runs_each_strategy_once_per_title(tmp_path):
    calls: list[str] = []

    def live(query: str, *, max_results: int) -> BooksSearchResult:
        calls.append(query)
        return BooksSearchResult(status="not_found")

    resolver = Resolver(
        search=CachedBooksSearch(tmp_path, live_search=live, sleep=lambda _s: None),
        agent=lambda _title, _author, prior: Resolution(status="resolved", method="agent"),
        memo={},
    )

    first = resolver.resolve("catalog+agent", "Dune", None)
    again = resolver.resolve("catalog+agent", "Dune", None)

    assert first is again
    assert first.method == "agent"
    assert calls == ["intitle:Dune"]
