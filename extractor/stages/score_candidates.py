from __future__ import annotations

from extractor.types import ExtractedBookCandidate


def score_candidates(candidates: list[ExtractedBookCandidate], *, has_probe: bool) -> list[ExtractedBookCandidate]:
    scored: list[ExtractedBookCandidate] = []
    for candidate in candidates:
        confidence = candidate.confidence + (0.1 if has_probe else 0.0)
        candidate.confidence = max(0.0, min(1.0, confidence))
        scored.append(candidate)
    return sorted(scored, key=lambda item: item.confidence, reverse=True)

