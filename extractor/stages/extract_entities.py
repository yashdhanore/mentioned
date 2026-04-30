from __future__ import annotations

import re

from extractor.types import ExtractedBookCandidate


QUOTED_BY_AUTHOR_PATTERN = re.compile(
    r'["“](?P<title>[^"”]{2,120})["”]\s+by\s+(?P<author>[A-Z][A-Za-z0-9 .\'-]{2,80})',
    re.IGNORECASE,
)
PLAIN_BY_AUTHOR_PATTERN = re.compile(
    r"(?P<title>(?:[A-Za-z0-9][A-Za-z0-9'’:&,\-.]*)(?:\s+(?:[A-Za-z0-9][A-Za-z0-9'’:&,\-.]*)){0,7})\s+by\s+(?P<author>[A-Za-z][A-Za-z.'’\-]*(?:\s+[A-Za-z][A-Za-z.'’\-]*){1,4})",
    re.IGNORECASE,
)
QUOTED_TITLE_PATTERN = re.compile(r'["“](?P<title>[^"”]{2,120})["”]')
LEADING_RECOMMENDATION_PREFIX = re.compile(
    r"^(?:also\s+)?(?:read|reading|loved|love|recommend(?:ed|ing)?|try|trying|saved?|liked?)\s+",
    re.IGNORECASE,
)

GENERIC_TITLES = {
    "instagram",
    "video",
    "reel",
    "book",
    "books",
    "essay",
    "essays",
    "post",
    "posts",
    "newsletter",
    "newsletters",
    "substack",
    "kindle",
}


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \t\r\n-:;,.!?")


def _is_plausible_title(title: str) -> bool:
    cleaned = _normalize_space(title)
    if not cleaned or len(cleaned) > 120:
        return False
    if not any(char.isalpha() for char in cleaned):
        return False
    words = cleaned.split()
    if len(words) > 12:
        return False
    if cleaned.lower() in GENERIC_TITLES:
        return False
    if cleaned.lower().startswith("video by "):
        return False
    return True


def _is_plausible_author(author: str) -> bool:
    cleaned = _normalize_space(author)
    words = cleaned.split()
    if len(words) < 2 or len(words) > 5:
        return False
    if any(any(char.isdigit() for char in word) for word in words):
        return False
    return True


def _should_use_title_case_line(line: str) -> bool:
    cleaned = _normalize_space(line)
    if not _is_plausible_title(cleaned):
        return False
    words = cleaned.split()
    alpha_words = [word for word in words if any(char.isalpha() for char in word)]
    if not alpha_words:
        return False
    titleish_words = sum(
        1
        for word in alpha_words
        if word[:1].isupper() or word.lower() in {"the", "a", "an", "and", "of", "to", "in"}
    )
    return titleish_words >= max(1, len(alpha_words) - 1)


def _upsert_candidate(
    candidate_map: dict[str, ExtractedBookCandidate],
    *,
    title: str,
    author: str | None,
    confidence: float,
    evidence: dict,
) -> None:
    cleaned_title = _normalize_space(title)
    cleaned_author = _normalize_space(author) if author else None
    if not _is_plausible_title(cleaned_title):
        return
    if cleaned_author and not _is_plausible_author(cleaned_author):
        return
    key = cleaned_title.lower()
    current = candidate_map.get(key)
    candidate = ExtractedBookCandidate(
        title=cleaned_title,
        author=cleaned_author,
        confidence=confidence,
        evidence=evidence,
    )
    if current is None:
        candidate_map[key] = candidate
        return
    if current.author is None and candidate.author is not None:
        candidate_map[key] = candidate
        return
    if candidate.confidence > current.confidence:
        candidate_map[key] = candidate


def extract_book_candidates(raw_text: str) -> list[ExtractedBookCandidate]:
    candidate_map: dict[str, ExtractedBookCandidate] = {}

    for match in QUOTED_BY_AUTHOR_PATTERN.finditer(raw_text):
        _upsert_candidate(
            candidate_map,
            title=match.group("title"),
            author=match.group("author"),
            confidence=0.72,
            evidence={"pattern": "quoted_title_by_author", "text": match.group(0)},
        )

    for raw_line in raw_text.splitlines():
        cleaned_line = _normalize_space(raw_line)
        if not cleaned_line:
            continue
        for match in PLAIN_BY_AUTHOR_PATTERN.finditer(cleaned_line):
            raw_title = LEADING_RECOMMENDATION_PREFIX.sub("", match.group("title")).strip()
            _upsert_candidate(
                candidate_map,
                title=raw_title,
                author=match.group("author"),
                confidence=0.62,
                evidence={"pattern": "plain_title_by_author", "text": match.group(0)},
            )

    for match in QUOTED_TITLE_PATTERN.finditer(raw_text):
        _upsert_candidate(
            candidate_map,
            title=match.group("title"),
            author=None,
            confidence=0.42,
            evidence={"pattern": "quoted_title", "text": match.group(0)},
        )

    for raw_line in raw_text.splitlines():
        if _should_use_title_case_line(raw_line):
            _upsert_candidate(
                candidate_map,
                title=raw_line,
                author=None,
                confidence=0.35,
                evidence={"pattern": "title_case_line", "text": raw_line},
            )

    return sorted(candidate_map.values(), key=lambda candidate: candidate.confidence, reverse=True)
