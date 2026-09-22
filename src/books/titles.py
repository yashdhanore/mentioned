"""Title and author comparison shared by book resolution and the extraction evals."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from difflib import SequenceMatcher

TITLE_MATCH_THRESHOLD = 0.88
AUTHOR_MATCH_THRESHOLD = 0.85
LEADING_ARTICLE_RE = re.compile(r"^(the|a|an) ")
NON_WORD_RE = re.compile(r"[^\w\s]")
WHITESPACE_RE = re.compile(r"\s+")
BILINGUAL_PARENTHETICAL_RE = re.compile(r"^(.+?)\s*\((.+)\)\s*$")


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    lowered = without_accents.casefold().replace("&", " and ")
    no_punctuation = NON_WORD_RE.sub(" ", lowered)
    return WHITESPACE_RE.sub(" ", no_punctuation).strip()


def normalize_title(value: str) -> str:
    """Normalize a title for comparison, dropping subtitles and leading articles."""
    main_title = re.split(r":| - | \u2013 | \u2014 ", value, maxsplit=1)[0]
    return LEADING_ARTICLE_RE.sub("", normalize_text(main_title))


def title_forms(value: str) -> set[str]:
    """Comparable forms of a title: with and without subtitle, and each side of a
    bilingual "Original / Translation" or "Original (Translation)" title."""
    parts = [value, *value.split(" / ")] if " / " in value else [value]
    bilingual = BILINGUAL_PARENTHETICAL_RE.match(value)
    if bilingual:
        parts += [bilingual.group(1), bilingual.group(2)]
    forms = set()
    for part in parts:
        forms.add(LEADING_ARTICLE_RE.sub("", normalize_text(part)))
        forms.add(normalize_title(part))
    forms.discard("")
    return forms


def best_title_similarity(title: str, candidates: Iterable[str]) -> float:
    """Highest similarity between any form of `title` and any form of a candidate."""
    forms = title_forms(title)
    best = 0.0
    for candidate in candidates:
        for candidate_form in title_forms(candidate):
            if candidate_form in forms:
                return 1.0
            for form in forms:
                best = max(best, SequenceMatcher(None, form, candidate_form).ratio())
    return best


def authors_match(predicted: str, expected: str) -> bool:
    predicted_norm = normalize_text(predicted)
    expected_norm = normalize_text(expected)
    if not predicted_norm or not expected_norm:
        return False
    if predicted_norm == expected_norm:
        return True
    if predicted_norm.split()[-1] == expected_norm.split()[-1]:
        return True
    return SequenceMatcher(None, predicted_norm, expected_norm).ratio() >= AUTHOR_MATCH_THRESHOLD
