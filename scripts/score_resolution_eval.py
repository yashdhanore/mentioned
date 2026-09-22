"""Score book resolution: does each mention end up attached to the right catalog entry?

Extraction evals (`score_extraction_eval.py`) grade the titles the video model writes
down. This grades the next step, where production looks each title up in Google
Books and attaches the result's cover and metadata. Three strategies are compared:

- `first_hit`: the first catalog result, unchecked (production before this change).
- `catalog`: the top 5 results, checked on title and author (`src/books/resolution.py`).
- `catalog+agent`: the same, then a text-only agent for mentions nothing passed
  (`src/books/resolution_agent.py`), only with `--agent-model`.

Two inputs:

- The labeled titles in `evals/reel-labels.json`, which measures resolution alone.
- With `--results`, the book mentions each model actually predicted in a
  `compare_gemini_video_models.py` run, which also measures whether "the catalog
  could not confirm it" flags the model's invented or wrong titles.

Catalog responses are cached under `--cache-dir`, so reruns are reproducible and
make no Books API calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.compare_gemini_video_models import DEFAULT_PRICE_TABLE
from scripts.score_extraction_eval import (
    DEFAULT_LABELS_PATH,
    ExpectedMention,
    LabeledReel,
    LabelsError,
    load_labels,
    predicted_mentions,
    result_sources,
    score_source,
    source_key_for,
)
from src.books.resolution import (
    DERIVATIVE_TITLE_RE,
    BookSearch,
    Resolution,
    catalog_titles,
    resolve_book,
)
from src.books.schemas import GoogleBook
from src.books.titles import (
    TITLE_MATCH_THRESHOLD,
    authors_match,
    best_title_similarity,
    normalize_text,
    title_forms,
)
from src.extraction.google_books import (
    BooksSearchResult,
    book_search_query,
    parse_google_book,
    search_volumes,
)

DEFAULT_CACHE_DIR = Path("outputs/books-cache")
STRATEGIES = ("first_hit", "catalog", "catalog+agent")
GRADES = ("same_work", "container", "wrong", "unresolved")
LIVE_RETRY_DELAYS = (5, 15, 30)
LIVE_CALL_SPACING_SECONDS = 1.0


class CachedBooksSearch:
    """Google Books search with an on-disk cache. Errors are never cached, and live
    calls are spaced and retried because the API rate-limits bursts."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        live_search: Callable[..., BooksSearchResult] = search_volumes,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._cache_dir = cache_dir
        self._live_search = live_search
        self._sleep = sleep
        self.live_calls = 0
        self.cache_hits = 0

    def __call__(self, query: str, *, max_results: int = 5) -> BooksSearchResult:
        key = hashlib.sha256(f"{max_results}|{query}".encode()).hexdigest()[:32]
        path = self._cache_dir / f"{key}.json"
        if path.exists():
            self.cache_hits += 1
            return _cached_result(json.loads(path.read_text(encoding="utf-8")))

        result = self._search_live(query, max_results)
        if result.status != "error":
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "query": query,
                "max_results": max_results,
                "status": result.status,
                "volumes": [book.raw_provider_payload for book in result.books],
            }
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
        return result

    def _search_live(self, query: str, max_results: int) -> BooksSearchResult:
        result = BooksSearchResult(status="error")
        for delay in (0, *LIVE_RETRY_DELAYS):
            self._sleep(delay or LIVE_CALL_SPACING_SECONDS)
            self.live_calls += 1
            result = self._live_search(query, max_results=max_results)
            if result.status != "error":
                return result
        return result


def _cached_result(payload: dict[str, Any]) -> BooksSearchResult:
    books = [
        book
        for book in (parse_google_book(volume) for volume in payload.get("volumes", []))
        if book is not None
    ]
    return BooksSearchResult(status=payload["status"], books=books)


@dataclass(frozen=True)
class Resolver:
    """Runs each strategy once per (title, author), however often a mention repeats."""

    search: CachedBooksSearch
    agent: Callable[[str, str | None, Resolution], Resolution] | None
    memo: dict[tuple[str, str, str | None], Resolution] = field(default_factory=dict)

    def resolve(self, strategy: str, title: str, author: str | None) -> Resolution:
        key = (strategy, title, author)
        if key not in self.memo:
            self.memo[key] = self._resolve(strategy, title, author)
        return self.memo[key]

    def _resolve(self, strategy: str, title: str, author: str | None) -> Resolution:
        if strategy == "first_hit":
            query = book_search_query(title, author)
            result = self.search(query, max_results=1)
            if result.status != "found":
                return Resolution(status=result.status, queries=(query,), searches=1)
            return Resolution(status="resolved", book=result.books[0], queries=(query,))
        catalog = resolve_book(title, author, search=self._top_five)
        if strategy == "catalog" or self.agent is None:
            return catalog
        if catalog.status not in ("ambiguous", "not_found"):
            return catalog
        return self.agent(title, author, catalog)

    def _top_five(self, query: str) -> BooksSearchResult:
        return self.search(query, max_results=5)


def _author_ok(book: GoogleBook, author: str | None) -> bool:
    if not author or not book.authors:
        return True
    return any(authors_match(candidate, author) for candidate in book.authors)


def grade(resolution: Resolution, expected: ExpectedMention) -> str:
    """Grade a resolution against the label, independently of how it was chosen."""
    book = resolution.book
    if resolution.status != "resolved" or book is None:
        return "unresolved"
    labels = (expected.title, *expected.aliases)
    derivative = DERIVATIVE_TITLE_RE.search(normalize_text(f"{book.title} {book.subtitle or ''}"))
    if derivative or not _author_ok(book, expected.author):
        return "wrong"
    titles = catalog_titles(book)
    if max(best_title_similarity(label, titles) for label in labels) >= TITLE_MATCH_THRESHOLD:
        return "same_work"
    haystack = f" {normalize_text(' '.join(titles))} "
    for label in labels:
        for form in title_forms(label):
            if re.search(rf"\b{re.escape(form)}\b", haystack):
                return "container"
    return "wrong"


def _resolution_view(resolution: Resolution) -> dict[str, Any]:
    book = resolution.book
    return {
        "status": resolution.status,
        "method": resolution.method,
        "book": None
        if book is None
        else {
            "volume_id": book.provider_volume_id,
            "title": book.title,
            "subtitle": book.subtitle,
            "authors": book.authors,
        },
        "queries": list(resolution.queries),
        "reason": resolution.reason,
        "rejected": [
            {"title": c.book.title, "authors": c.book.authors, "because": c.rejected_because}
            for c in resolution.candidates
            if c.rejected_because
        ],
    }


def _labeled_books(labels: dict[str, LabeledReel]) -> list[ExpectedMention]:
    unique: dict[tuple[str, str], ExpectedMention] = {}
    for reel in labels.values():
        if reel.status != "labeled":
            continue
        for expected in reel.expected:
            if expected.category == "book":
                key = (normalize_text(expected.title), normalize_text(expected.author or ""))
                unique.setdefault(key, expected)
    return list(unique.values())


def score_labeled_titles(
    labels: dict[str, LabeledReel], resolver: Resolver, strategies: tuple[str, ...]
) -> dict[str, Any]:
    books = _labeled_books(labels)
    items = []
    totals = {strategy: Counter() for strategy in strategies}
    for expected in books:
        item: dict[str, Any] = {"title": expected.title, "author": expected.author}
        for strategy in strategies:
            resolution = resolver.resolve(strategy, expected.title, expected.author)
            item_grade = grade(resolution, expected)
            totals[strategy][item_grade] += 1
            totals[strategy][f"status:{resolution.status}"] += 1
            item[strategy] = {"grade": item_grade, **_resolution_view(resolution)}
        items.append(item)
    return {
        "labeled_books": len(books),
        "strategies": {strategy: dict(totals[strategy]) for strategy in strategies},
        "items": items,
    }


def _find_label(expected: tuple[ExpectedMention, ...], view: dict[str, Any]) -> ExpectedMention:
    return next(
        label
        for label in expected
        if label.title == view["title"] and label.category == view["category"]
    )


def score_predictions(
    labels: dict[str, LabeledReel],
    results: dict[str, Any],
    resolver: Resolver,
    strategies: tuple[str, ...],
) -> dict[str, Any]:
    """Resolve each model's predicted books, split by whether extraction got them right."""
    per_model: dict[str, dict[str, Counter]] = {}
    flagged_false_positives: list[dict[str, Any]] = []
    for source in result_sources(results):
        source_url = source.get("source_url")
        reel = labels.get(source_key_for(source_url)) if isinstance(source_url, str) else None
        if reel is None or reel.status != "labeled":
            continue
        for result in source.get("results", []):
            if not isinstance(result, dict) or result.get("ok") is not True:
                continue
            model = result["model"]
            counters = per_model.setdefault(model, {strategy: Counter() for strategy in strategies})
            predicted = [
                m for m in predicted_mentions(result) if m.get("category", "book") == "book"
            ]
            score = score_source(predicted, reel.expected)
            for match in score.true_positives:
                expected = _find_label(reel.expected, match["expected"])
                for strategy in strategies:
                    resolution = resolver.resolve(strategy, match["title"], match.get("author"))
                    counters[strategy]["tp"] += 1
                    counters[strategy][f"tp_{grade(resolution, expected)}"] += 1
            for mention in score.false_positives:
                for strategy in strategies:
                    resolution = resolver.resolve(strategy, mention["title"], mention.get("author"))
                    counters[strategy]["fp"] += 1
                    flagged = resolution.status in ("ambiguous", "not_found")
                    counters[strategy]["fp_flagged"] += int(flagged)
                    if strategy == strategies[-1]:
                        flagged_false_positives.append(
                            {
                                "model": model,
                                "source_url": source_url,
                                "title": mention["title"],
                                "author": mention.get("author"),
                                "flagged": flagged,
                                **_resolution_view(resolution),
                            }
                        )
    return {
        "models": {
            model: {strategy: dict(counter) for strategy, counter in counters.items()}
            for model, counters in per_model.items()
        },
        "false_positives": flagged_false_positives,
    }


def _agent_cost(model: str, usage: dict[str, int]) -> float | None:
    prices = DEFAULT_PRICE_TABLE.get(model)
    if prices is None:
        return None
    return round(
        usage.get("input_tokens", 0) * prices["input_text_image_video"] / 1_000_000
        + usage.get("output_tokens", 0) * prices["output"] / 1_000_000,
        6,
    )


def format_report(report: dict[str, Any]) -> str:
    strategies = report["strategy_names"]
    labeled = report["labeled_titles"]
    width = max(len(s) for s in strategies) + 4
    lines = [f"Labeled titles: {labeled['labeled_books']} unique books", ""]
    lines.append(" " * 14 + "".join(s.ljust(width) for s in strategies))
    for name in GRADES:
        values = [str(labeled["strategies"][s].get(name, 0)) for s in strategies]
        lines.append(name.ljust(14) + "".join(v.ljust(width) for v in values))

    predictions = report.get("predictions")
    if predictions:
        lines += ["", "Model predictions (books only)"]
        for model, by_strategy in predictions["models"].items():
            lines.append(f"  {model}")
            for strategy in strategies:
                c = by_strategy[strategy]
                lines.append(
                    f"    {strategy.ljust(width)}"
                    f"correct mentions {c.get('tp', 0)}: same work {c.get('tp_same_work', 0)}, "
                    f"container {c.get('tp_container', 0)}, wrong {c.get('tp_wrong', 0)}, "
                    f"unresolved {c.get('tp_unresolved', 0)} | "
                    f"wrong mentions flagged {c.get('fp_flagged', 0)}/{c.get('fp', 0)}"
                )

    agent = report.get("agent")
    if agent:
        lines += [
            "",
            f"Agent ({agent['model']}): {agent['usage'].get('calls', 0)} calls, "
            f"{agent['usage'].get('input_tokens', 0)} input / "
            f"{agent['usage'].get('output_tokens', 0)} output tokens, "
            f"about ${agent['estimated_cost_usd']}",
        ]
    search = report["books_api"]
    lines.append(f"Books API: {search['live_calls']} live calls, {search['cache_hits']} cache hits")
    return "\n".join(lines)


def build_agent(model: str, search: BookSearch, usage: dict[str, int]):
    from src.books.resolution_agent import resolve_with_agent
    from src.config import get_settings
    from src.extraction.gemini_client import get_gemini_client

    client = get_gemini_client(get_settings())

    def agent(title: str, author: str | None, prior: Resolution) -> Resolution:
        return resolve_with_agent(
            title, author, prior, search=search, client=client, model=model, usage=usage
        )

    return agent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score book resolution against labels.")
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS_PATH)
    parser.add_argument(
        "--results",
        type=Path,
        default=None,
        help="JSON written by scripts/compare_gemini_video_models.py --output.",
    )
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument(
        "--agent-model",
        default=None,
        help="Gemini model for the catalog+agent strategy; omit to skip the agent.",
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        labels = load_labels(args.labels)
        results = json.loads(args.results.read_text("utf-8")) if args.results else None
    except (LabelsError, OSError, json.JSONDecodeError) as exc:
        print(f"scoring failed: {exc}", file=sys.stderr)
        return 1

    search = CachedBooksSearch(args.cache_dir)
    usage: dict[str, int] = {}
    agent = None
    strategies = STRATEGIES[:2]
    if args.agent_model:
        agent = build_agent(args.agent_model, lambda q: search(q, max_results=5), usage)
        strategies = STRATEGIES
    resolver = Resolver(search=search, agent=agent)

    report: dict[str, Any] = {
        "strategy_names": list(strategies),
        "labeled_titles": score_labeled_titles(labels, resolver, strategies),
    }
    if results is not None:
        report["predictions"] = score_predictions(labels, results, resolver, strategies)
    if args.agent_model:
        report["agent"] = {
            "model": args.agent_model,
            "usage": usage,
            "estimated_cost_usd": _agent_cost(args.agent_model, usage),
        }
    report["books_api"] = {"live_calls": search.live_calls, "cache_hits": search.cache_hits}

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{json.dumps(report, indent=2, sort_keys=True)}\n", "utf-8")
    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
