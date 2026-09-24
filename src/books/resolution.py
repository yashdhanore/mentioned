"""Resolve an extracted book mention to a catalog entry, and say how sure we are.

The catalog returns its best guesses for a query, not an answer: the first hit for
"The Bluest Eye" can be a book titled "Toni Morrison", and the first hit for "The
Nightingale" can be a summary of it. So every candidate is checked against the
extracted title and author before it is attached, and a mention that nothing
passes is kept as unverified rather than attached to the wrong book or dropped.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from src.books.schemas import GoogleBook
from src.books.titles import (
    TITLE_MATCH_THRESHOLD,
    authors_match,
    best_title_similarity,
    normalize_text,
    normalize_title,
)
from src.extraction.google_books import BooksSearchResult, book_search_query, search_volumes
from src.observability import observe_step

ResolutionStatus = Literal["resolved", "ambiguous", "not_found", "error"]
ResolutionMethod = Literal["catalog", "agent"]
BookSearch = Callable[[str], BooksSearchResult]

# Catalog entries that are about a book rather than the book itself.
DERIVATIVE_TITLE_RE = re.compile(
    r"\b(summary|summaries|study guide|analysis|workbook|sparknotes|cliffsnotes|"
    r"reader s guide|readers guide|book review)\b"
)
PARENTHETICAL_RE = re.compile(r"\s*[(\[][^)\]]*[)\]]")
BY_AUTHOR_SUFFIX_RE = re.compile(r"\s+by\s+.+$", re.IGNORECASE)
AUTHOR_MATCH_BONUS = 0.1
BOOK_PRINT_TYPE_BONUS = 0.05
# Among editions that all pass, prefer one titled plainly: the catalog title is what the
# app shows, and "Anna Karenina (Illustrated)" reads worse than "Anna Karenina".
UNDECORATED_TITLE_BONUS = 0.02


@dataclass(frozen=True)
class ScoredCandidate:
    book: GoogleBook
    title_similarity: float
    author_match: bool | None
    rejected_because: str | None
    score: float


@dataclass(frozen=True)
class Resolution:
    """`resolved`: a candidate passed the title and author check.
    `ambiguous`: the catalog returned books, but none passed.
    `not_found`: the catalog returned nothing, even for the title alone.
    `error`: the catalog could not be asked; says nothing about the mention."""

    status: ResolutionStatus
    book: GoogleBook | None = None
    candidates: tuple[ScoredCandidate, ...] = ()
    queries: tuple[str, ...] = ()
    method: ResolutionMethod = "catalog"
    reason: str | None = None
    searches: int = 0


def catalog_titles(book: GoogleBook) -> list[str]:
    """Title forms a catalog entry can match on. Editions decorate titles with
    "(Illustrated)" or "by Author"; those are stripped so an edition still counts."""
    titles = [book.title]
    if book.subtitle:
        titles.append(f"{book.title}: {book.subtitle}")
    for title in list(titles):
        for cleaned in (
            PARENTHETICAL_RE.sub("", title).strip(),
            BY_AUTHOR_SUFFIX_RE.sub("", title).strip(),
        ):
            if cleaned and cleaned not in titles:
                titles.append(cleaned)
    return titles


def score_candidate(book: GoogleBook, title: str, author: str | None) -> ScoredCandidate:
    similarity = best_title_similarity(title, catalog_titles(book))
    author_match: bool | None = None
    if author and book.authors:
        author_match = any(authors_match(candidate, author) for candidate in book.authors)

    rejected_because = None
    if DERIVATIVE_TITLE_RE.search(normalize_text(f"{book.title} {book.subtitle or ''}")):
        rejected_because = "derivative work"
    elif similarity < TITLE_MATCH_THRESHOLD:
        rejected_because = "title mismatch"
    elif author_match is False:
        rejected_because = "author mismatch"

    score = similarity
    if author_match:
        score += AUTHOR_MATCH_BONUS
    if book.print_type == "BOOK":
        score += BOOK_PRINT_TYPE_BONUS
    if normalize_title(book.title) == normalize_title(title):
        score += UNDECORATED_TITLE_BONUS
    return ScoredCandidate(
        book=book,
        title_similarity=round(similarity, 3),
        author_match=author_match,
        rejected_because=rejected_because,
        score=round(score, 3),
    )


def resolve_book(title: str, author: str | None, *, search: BookSearch) -> Resolution:
    """Check the catalog's top results for `title` and attach the best one that passes.

    Traced as the `resolve-book` retriever, with every query and why each candidate was
    rejected, so a book left without a cover can be explained from the trace alone."""
    with observe_step(
        "resolve-book", as_type="retriever", input={"title": title, "author": author}
    ) as step:
        resolution = _check_catalog(title, author, search=search)
        step.update(output=resolution_view(resolution), metadata=resolution_details(resolution))
        return resolution


def resolution_view(resolution: Resolution) -> dict[str, Any]:
    book = resolution.book
    return {
        "status": resolution.status,
        "method": resolution.method,
        "book": _book_view(book) if book else None,
        "reason": resolution.reason,
    }


def resolution_details(resolution: Resolution) -> dict[str, Any]:
    return {
        "queries": list(resolution.queries),
        "searches": resolution.searches,
        "candidates": [
            {
                **_book_view(candidate.book),
                "title_similarity": candidate.title_similarity,
                "author_match": candidate.author_match,
                "rejected_because": candidate.rejected_because,
                "score": candidate.score,
            }
            for candidate in resolution.candidates
        ],
    }


def _book_view(book: GoogleBook) -> dict[str, Any]:
    return {"volume_id": book.provider_volume_id, "title": book.title, "authors": book.authors}


def _check_catalog(title: str, author: str | None, *, search: BookSearch) -> Resolution:
    queries = [book_search_query(title, author)]
    result = search(queries[0])
    if result.status == "not_found" and author:
        # An author spelled differently from the catalog ("Dostoyevsky") empties the
        # combined query; the title alone still gets checked against the author.
        queries.append(book_search_query(title, None))
        result = search(queries[1])
    if result.status == "error":
        return Resolution(status="error", queries=tuple(queries), searches=len(queries))
    if result.status == "not_found":
        return Resolution(status="not_found", queries=tuple(queries), searches=len(queries))

    candidates = tuple(score_candidate(book, title, author) for book in result.books)
    accepted = [candidate for candidate in candidates if candidate.rejected_because is None]
    if not accepted:
        return Resolution(
            status="ambiguous",
            candidates=candidates,
            queries=tuple(queries),
            searches=len(queries),
        )
    best = max(accepted, key=lambda candidate: candidate.score)
    return Resolution(
        status="resolved",
        book=best.book,
        candidates=candidates,
        queries=tuple(queries),
        searches=len(queries),
    )


def find_resolved_book(title: str, author: str | None) -> GoogleBook | None:
    """The worker's book finder: a catalog entry only when it passed the check."""
    resolution = resolve_book(title, author, search=search_volumes)
    return resolution.book if resolution.status == "resolved" else None
