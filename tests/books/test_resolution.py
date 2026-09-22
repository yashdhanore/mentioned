from __future__ import annotations

from src.books import resolution
from src.books.resolution import catalog_titles, find_resolved_book, resolve_book
from src.books.schemas import GoogleBook
from src.extraction.google_books import BooksSearchResult


def _book(volume_id: str, title: str, authors: list[str], **extra) -> GoogleBook:
    return GoogleBook(provider_volume_id=volume_id, title=title, authors=authors, **extra)


def _search(*results: BooksSearchResult):
    queries: list[str] = []
    remaining = list(results)

    def search(query: str) -> BooksSearchResult:
        queries.append(query)
        return remaining.pop(0)

    search.queries = queries
    return search


def test_skips_a_summary_that_the_catalog_ranks_first():
    summary = _book("s1", "Kristin Hannah's The Nightingale", ["Honest Reviews Staff"])
    novel = _book("n1", "The Nightingale", ["Kristin Hannah"], print_type="BOOK")
    search = _search(BooksSearchResult(status="found", books=[summary, novel]))

    result = resolve_book("The Nightingale", "Kristin Hannah", search=search)

    assert result.status == "resolved"
    assert result.book is novel
    assert result.candidates[0].rejected_because == "title mismatch"


def test_rejects_derivative_works_even_when_the_title_matches():
    guide = _book("g1", "The Great Gatsby", ["F. Scott Fitzgerald"], subtitle="A Study Guide")
    search = _search(BooksSearchResult(status="found", books=[guide]))

    result = resolve_book("The Great Gatsby", "F. Scott Fitzgerald", search=search)

    assert result.status == "ambiguous"
    assert result.book is None
    assert result.candidates[0].rejected_because == "derivative work"


def test_is_ambiguous_when_no_candidate_is_the_book():
    wrong = _book("w1", "Toni Morrison", ["Toni Morrison"])
    search = _search(BooksSearchResult(status="found", books=[wrong]))

    result = resolve_book("The Bluest Eye", "Toni Morrison", search=search)

    assert result.status == "ambiguous"
    assert result.book is None


def test_rejects_the_right_title_by_a_different_author():
    other = _book("o1", "The Nightingale", ["Someone Else"])
    search = _search(BooksSearchResult(status="found", books=[other]))

    result = resolve_book("The Nightingale", "Kristin Hannah", search=search)

    assert result.status == "ambiguous"
    assert result.candidates[0].rejected_because == "author mismatch"


def test_accepts_editions_decorated_with_edition_or_author_text():
    illustrated = _book("i1", "Dubliners (Illustrated)", ["James Joyce"])
    by_author = _book("b1", "The Brothers Karamazov by Fyodor Dostoyevsky", ["Fyodor Dostoyevsky"])

    assert "Dubliners" in catalog_titles(illustrated)
    assert "The Brothers Karamazov" in catalog_titles(by_author)
    assert (
        resolve_book(
            "Dubliners",
            "James Joyce",
            search=_search(BooksSearchResult(status="found", books=[illustrated])),
        ).status
        == "resolved"
    )
    assert (
        resolve_book(
            "The Brothers Karamazov",
            "Fyodor Dostoevsky",
            search=_search(BooksSearchResult(status="found", books=[by_author])),
        ).status
        == "resolved"
    )


def test_prefers_a_matching_author_and_a_printed_book():
    no_author = _book("a1", "Dune", [])
    magazine = _book("a2", "Dune", ["Frank Herbert"], print_type="MAGAZINE")
    printed = _book("a3", "Dune", ["Frank Herbert"], print_type="BOOK")
    search = _search(BooksSearchResult(status="found", books=[no_author, magazine, printed]))

    assert resolve_book("Dune", "Frank Herbert", search=search).book is printed


def test_prefers_a_plainly_titled_edition_over_a_decorated_one():
    illustrated = _book("i1", "Anna Karenina (Illustrated)", ["Leo Tolstoy"], print_type="BOOK")
    plain = _book("p1", "Anna Karenina", ["Leo Tolstoy"], print_type="BOOK")
    search = _search(BooksSearchResult(status="found", books=[illustrated, plain]))

    assert resolve_book("Anna Karenina", "Leo Tolstoy", search=search).book is plain


def test_retries_without_the_author_when_the_combined_query_finds_nothing():
    book = _book("k1", "Devils", ["Fyodor Dostoevsky"])
    search = _search(
        BooksSearchResult(status="not_found"),
        BooksSearchResult(status="found", books=[book]),
    )

    result = resolve_book("Devils", "Fyodor Dostoevsky", search=search)

    assert result.status == "resolved"
    assert search.queries == ["intitle:Devils+inauthor:Fyodor Dostoevsky", "intitle:Devils"]


def test_not_found_when_even_the_title_alone_finds_nothing():
    search = _search(BooksSearchResult(status="not_found"), BooksSearchResult(status="not_found"))

    result = resolve_book("Lives not Lived", "Monika Ghatti", search=search)

    assert result.status == "not_found"
    assert result.searches == 2


def test_error_is_kept_apart_from_not_found():
    search = _search(BooksSearchResult(status="error"))

    result = resolve_book("Dune", "Frank Herbert", search=search)

    assert result.status == "error"
    assert search.queries == ["intitle:Dune+inauthor:Frank Herbert"]


def test_find_resolved_book_only_returns_checked_books(monkeypatch):
    monkeypatch.setattr(
        resolution,
        "search_volumes",
        lambda _query: BooksSearchResult(
            status="found", books=[_book("w1", "Toni Morrison", ["Toni Morrison"])]
        ),
    )
    assert find_resolved_book("The Bluest Eye", "Toni Morrison") is None

    book = _book("r1", "The Bluest Eye", ["Toni Morrison"])
    monkeypatch.setattr(
        resolution,
        "search_volumes",
        lambda _query: BooksSearchResult(status="found", books=[book]),
    )
    assert find_resolved_book("The Bluest Eye", "Toni Morrison") is book
