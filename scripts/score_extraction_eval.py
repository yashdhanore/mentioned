"""Score extraction output against hand-labeled Reels.

Reads `evals/reel-labels.json` and, optionally, a result file written by
`scripts/compare_gemini_video_models.py`. Without `--results` it only validates
the labels and reports labeling coverage.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.books.titles import TITLE_MATCH_THRESHOLD, authors_match, best_title_similarity
from src.sources.identity import identify_source

LABELS_SCHEMA_VERSION = "reel_labels.v1"
DEFAULT_LABELS_PATH = Path("evals/reel-labels.json")
LABEL_STATUSES = {"todo", "labeled", "excluded"}
CATEGORIES = {"book", "product", "place"}
TIMESTAMP_RE = re.compile(r"^\d{1,2}:\d{2}$")


class LabelsError(ValueError):
    pass


@dataclass(frozen=True)
class ExpectedMention:
    category: str
    title: str
    author: str | None
    aliases: tuple[str, ...]
    optional: bool


@dataclass(frozen=True)
class LabeledReel:
    source_key: str
    source_url: str
    status: str
    expected: tuple[ExpectedMention, ...]


@dataclass
class SourceScore:
    true_positives: list[dict[str, Any]] = field(default_factory=list)
    false_positives: list[dict[str, Any]] = field(default_factory=list)
    false_negatives: list[dict[str, Any]] = field(default_factory=list)
    optional_hits: list[dict[str, Any]] = field(default_factory=list)


def title_similarity(predicted: str, expected: ExpectedMention) -> float:
    return best_title_similarity(predicted, (expected.title, *expected.aliases))


def _source_key(source_url: str) -> str:
    return identify_source(source_url).source_key


def _optional_str(value: Any, where: str, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise LabelsError(f"{where}: {name} must be a string")
    return value.strip() or None


def _parse_expected(raw: Any, where: str) -> ExpectedMention:
    if not isinstance(raw, dict):
        raise LabelsError(f"{where}: expected mention must be an object")
    title = _optional_str(raw.get("title"), where, "title")
    if not title:
        raise LabelsError(f"{where}: title is required")
    category = raw.get("category")
    if category not in CATEGORIES:
        raise LabelsError(f"{where}: category must be one of {sorted(CATEGORIES)}")
    aliases = raw.get("aliases", [])
    if not isinstance(aliases, list) or not all(isinstance(alias, str) for alias in aliases):
        raise LabelsError(f"{where}: aliases must be a list of strings")
    optional = raw.get("optional", False)
    if not isinstance(optional, bool):
        raise LabelsError(f"{where}: optional must be true or false")
    return ExpectedMention(
        category=category,
        title=title,
        author=_optional_str(raw.get("author"), where, "author"),
        aliases=tuple(alias.strip() for alias in aliases if alias.strip()),
        optional=optional,
    )


def load_labels(path: Path) -> dict[str, LabeledReel]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LabelsError(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(document, dict) or document.get("schema_version") != LABELS_SCHEMA_VERSION:
        raise LabelsError(f"{path}: schema_version must be {LABELS_SCHEMA_VERSION!r}")
    raw_reels = document.get("reels")
    if not isinstance(raw_reels, list):
        raise LabelsError(f"{path}: reels must be a list")

    reels: dict[str, LabeledReel] = {}
    for index, raw_reel in enumerate(raw_reels):
        where = f"reels[{index}]"
        if not isinstance(raw_reel, dict):
            raise LabelsError(f"{where}: must be an object")
        source_url = raw_reel.get("source_url")
        if not isinstance(source_url, str):
            raise LabelsError(f"{where}: source_url is required")
        try:
            source_key = _source_key(source_url)
        except ValueError as exc:
            raise LabelsError(f"{where}: {exc}") from exc
        if source_key in reels:
            raise LabelsError(f"{where}: duplicate Reel {source_key}")
        status = raw_reel.get("status")
        if status not in LABEL_STATUSES:
            raise LabelsError(f"{where}: status must be one of {sorted(LABEL_STATUSES)}")
        raw_expected = raw_reel.get("expected_mentions", [])
        if not isinstance(raw_expected, list):
            raise LabelsError(f"{where}: expected_mentions must be a list")
        expected = tuple(
            _parse_expected(item, f"{where}.expected_mentions[{item_index}]")
            for item_index, item in enumerate(raw_expected)
        )
        reels[source_key] = LabeledReel(
            source_key=source_key,
            source_url=source_url,
            status=status,
            expected=expected,
        )
    return reels


def _predicted_mentions(result: dict[str, Any]) -> list[dict[str, Any]]:
    raw = result.get("raw")
    mentions = raw.get("mentions") if isinstance(raw, dict) else None
    if not isinstance(mentions, list):
        return []
    return [
        mention
        for mention in mentions
        if isinstance(mention, dict) and isinstance(mention.get("title"), str)
    ]


def _mention_view(mention: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": mention.get("title"),
        "author": mention.get("author"),
        "category": mention.get("category"),
        "confidence": mention.get("confidence"),
    }


def _expected_view(expected: ExpectedMention) -> dict[str, Any]:
    return {"title": expected.title, "author": expected.author, "category": expected.category}


def score_source(
    predicted: list[dict[str, Any]], expected: tuple[ExpectedMention, ...]
) -> SourceScore:
    """Greedily match predictions to labels one-to-one, best title similarity first."""
    candidates: list[tuple[float, int, int]] = []
    for predicted_index, mention in enumerate(predicted):
        for expected_index, label in enumerate(expected):
            if mention.get("category", "book") != label.category:
                continue
            similarity = title_similarity(mention["title"], label)
            if similarity >= TITLE_MATCH_THRESHOLD:
                candidates.append((similarity, predicted_index, expected_index))
    candidates.sort(key=lambda item: item[0], reverse=True)

    score = SourceScore()
    matched_predicted: set[int] = set()
    matched_expected: set[int] = set()
    for similarity, predicted_index, expected_index in candidates:
        if predicted_index in matched_predicted or expected_index in matched_expected:
            continue
        matched_predicted.add(predicted_index)
        matched_expected.add(expected_index)
        mention = predicted[predicted_index]
        label = expected[expected_index]
        match = {
            **_mention_view(mention),
            "expected": _expected_view(label),
            "title_similarity": round(similarity, 3),
            "author_correct": _author_correct(mention.get("author"), label.author),
        }
        if label.optional:
            score.optional_hits.append(match)
        else:
            score.true_positives.append(match)

    score.false_positives = [
        _mention_view(mention)
        for index, mention in enumerate(predicted)
        if index not in matched_predicted
    ]
    score.false_negatives = [
        _expected_view(label)
        for index, label in enumerate(expected)
        if index not in matched_expected and not label.optional
    ]
    return score


def _count_evidence(totals: dict[str, Any], predicted: list[dict[str, Any]]) -> None:
    for mention in predicted:
        totals["predicted_mentions"] += 1
        evidence = mention.get("evidence")
        if isinstance(evidence, dict) and evidence.get("source"):
            totals["with_evidence"] += 1
            if TIMESTAMP_RE.match(str(evidence.get("timestamp") or "")):
                totals["with_timestamp"] += 1


def _author_correct(predicted: Any, expected: str | None) -> bool | None:
    if not expected:
        return None
    if not isinstance(predicted, str) or not predicted.strip():
        return False
    return authors_match(predicted, expected)


def wilson_interval(successes: int, total: int, z: float = 1.96) -> list[float] | None:
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
    margin /= denominator
    return [round(max(0.0, center - margin), 3), round(min(1.0, center + margin), 3)]


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 3)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def _confidences(mentions: list[dict[str, Any]]) -> list[float]:
    return [
        float(mention["confidence"])
        for mention in mentions
        if isinstance(mention.get("confidence"), (int, float))
    ]


def _result_sources(results: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(results.get("sources"), list):
        return [source for source in results["sources"] if isinstance(source, dict)]
    if isinstance(results.get("source_url"), str):
        return [results]
    raise LabelsError("results file must come from scripts/compare_gemini_video_models.py")


def _empty_model_totals() -> dict[str, Any]:
    return {
        "scored_sources": 0,
        "failed_extractions": 0,
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "optional_hits": 0,
        "empty_source_false_positives": 0,
        "author_checked": 0,
        "author_correct": 0,
        "tp_confidences": [],
        "fp_confidences": [],
        "cost_usd": 0.0,
        "duration_seconds": [],
        "predicted_mentions": 0,
        "with_evidence": 0,
        "with_timestamp": 0,
    }


def score_results(labels: dict[str, LabeledReel], results: dict[str, Any]) -> dict[str, Any]:
    per_model: dict[str, dict[str, Any]] = {}
    per_source: list[dict[str, Any]] = []
    unlabeled: list[str] = []
    unscored: list[dict[str, str]] = []

    for source in _result_sources(results):
        source_url = source.get("source_url")
        if not isinstance(source_url, str):
            continue
        reel = labels.get(_source_key(source_url))
        if reel is None or reel.status == "todo":
            unlabeled.append(source_url)
            continue
        if reel.status == "excluded":
            continue
        download_error = source.get("download_error") or source.get("error")
        if download_error:
            unscored.append({"source_url": source_url, "reason": str(download_error)})
            continue

        required_count = sum(1 for label in reel.expected if not label.optional)
        source_report: dict[str, Any] = {"source_url": source_url, "models": {}}
        for result in source.get("results", []):
            if not isinstance(result, dict) or not isinstance(result.get("model"), str):
                continue
            model = result["model"]
            totals = per_model.setdefault(model, _empty_model_totals())
            totals["scored_sources"] += 1
            if isinstance(result.get("duration_seconds"), (int, float)):
                totals["duration_seconds"].append(float(result["duration_seconds"]))
            cost = result.get("estimated_cost")
            if isinstance(cost, dict) and isinstance(cost.get("total_usd"), (int, float)):
                totals["cost_usd"] += float(cost["total_usd"])

            if result.get("ok") is not True:
                totals["failed_extractions"] += 1
                totals["fn"] += required_count
                source_report["models"][model] = {
                    "error": result.get("error", "extraction failed"),
                    "false_negatives": [
                        _expected_view(label) for label in reel.expected if not label.optional
                    ],
                }
                continue

            predicted = _predicted_mentions(result)
            score = score_source(predicted, reel.expected)
            _count_evidence(totals, predicted)
            totals["tp"] += len(score.true_positives)
            totals["fp"] += len(score.false_positives)
            totals["fn"] += len(score.false_negatives)
            totals["optional_hits"] += len(score.optional_hits)
            if required_count == 0:
                totals["empty_source_false_positives"] += len(score.false_positives)
            for match in score.true_positives:
                if match["author_correct"] is not None:
                    totals["author_checked"] += 1
                    totals["author_correct"] += int(match["author_correct"])
            totals["tp_confidences"].extend(_confidences(score.true_positives))
            totals["fp_confidences"].extend(_confidences(score.false_positives))
            source_report["models"][model] = {
                "true_positives": score.true_positives,
                "false_positives": score.false_positives,
                "false_negatives": score.false_negatives,
                "optional_hits": score.optional_hits,
            }
        per_source.append(source_report)

    return {
        "models": [_summarize_model(model, totals) for model, totals in per_model.items()],
        "sources": per_source,
        "unlabeled_sources": unlabeled,
        "unscored_sources": unscored,
    }


def _summarize_model(model: str, totals: dict[str, Any]) -> dict[str, Any]:
    tp, fp, fn = totals["tp"], totals["fp"], totals["fn"]
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = None
    if precision is not None and recall is not None and precision + recall > 0:
        f1 = round(2 * precision * recall / (precision + recall), 3)
    cost_usd = round(totals["cost_usd"], 6)
    return {
        "model": model,
        "scored_sources": totals["scored_sources"],
        "failed_extractions": totals["failed_extractions"],
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "optional_hits": totals["optional_hits"],
        "precision": precision,
        "precision_ci95": wilson_interval(tp, tp + fp),
        "recall": recall,
        "recall_ci95": wilson_interval(tp, tp + fn),
        "f1": f1,
        "author_accuracy": _ratio(totals["author_correct"], totals["author_checked"]),
        "empty_source_false_positives": totals["empty_source_false_positives"],
        "mean_confidence_true_positives": _mean(totals["tp_confidences"]),
        "mean_confidence_false_positives": _mean(totals["fp_confidences"]),
        "estimated_cost_usd": cost_usd,
        "cost_per_true_positive_usd": round(cost_usd / tp, 6) if tp else None,
        "mean_duration_seconds": _mean(totals["duration_seconds"]),
        "evidence_coverage": _ratio(totals["with_evidence"], totals["predicted_mentions"]),
        "timestamp_coverage": _ratio(totals["with_timestamp"], totals["predicted_mentions"]),
    }


def labels_coverage(labels: dict[str, LabeledReel]) -> dict[str, Any]:
    statuses = [reel.status for reel in labels.values()]
    labeled = [reel for reel in labels.values() if reel.status == "labeled"]
    return {
        "total": len(statuses),
        "labeled": statuses.count("labeled"),
        "todo": statuses.count("todo"),
        "excluded": statuses.count("excluded"),
        "expected_mentions": sum(
            1 for reel in labeled for label in reel.expected if not label.optional
        ),
        "labeled_empty_reels": sum(
            1 for reel in labeled if not any(not label.optional for label in reel.expected)
        ),
    }


def _format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, list):
        return f"[{value[0]:.2f}, {value[1]:.2f}]"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def format_report(coverage: dict[str, Any], report: dict[str, Any] | None) -> str:
    lines = [
        f"Labels: {coverage['labeled']}/{coverage['total']} labeled, {coverage['todo']} todo, "
        f"{coverage['excluded']} excluded, {coverage['expected_mentions']} expected mentions"
    ]
    if report is None:
        return "\n".join(lines)

    rows = [
        ("precision", "precision"),
        ("  95% CI", "precision_ci95"),
        ("recall", "recall"),
        ("  95% CI", "recall_ci95"),
        ("f1", "f1"),
        ("author accuracy", "author_accuracy"),
        ("TP / FP / FN", None),
        ("FP on empty Reels", "empty_source_false_positives"),
        ("mean conf. TP", "mean_confidence_true_positives"),
        ("mean conf. FP", "mean_confidence_false_positives"),
        ("failed extractions", "failed_extractions"),
        ("cost USD", "estimated_cost_usd"),
        ("USD per TP", "cost_per_true_positive_usd"),
        ("mean seconds", "mean_duration_seconds"),
        ("with evidence", "evidence_coverage"),
        ("with timestamp", "timestamp_coverage"),
    ]
    models = report["models"]
    if models:
        width = max(len(model["model"]) for model in models) + 2
        lines.append("")
        lines.append(" " * 20 + "".join(model["model"].ljust(width) for model in models))
        for label, key in rows:
            if key is None:
                values = [
                    f"{m['true_positives']} / {m['false_positives']} / {m['false_negatives']}"
                    for m in models
                ]
            else:
                values = [_format_value(m[key]) for m in models]
            lines.append(label.ljust(20) + "".join(value.ljust(width) for value in values))
    else:
        lines.append("No labeled Reels in the results file yet.")

    if report["unlabeled_sources"]:
        lines.append("")
        lines.append(f"Skipped {len(report['unlabeled_sources'])} unlabeled Reel(s).")
    if report["unscored_sources"]:
        lines.append(f"Skipped {len(report['unscored_sources'])} Reel(s) that failed to download.")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score Gemini extraction output against hand-labeled Reels."
    )
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS_PATH)
    parser.add_argument(
        "--results",
        type=Path,
        default=None,
        help="JSON written by scripts/compare_gemini_video_models.py --output.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path for the full per-Reel score report as JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        labels = load_labels(args.labels)
        report = None
        if args.results:
            results = json.loads(args.results.read_text(encoding="utf-8"))
            report = score_results(labels, results)
    except (LabelsError, OSError, json.JSONDecodeError) as exc:
        print(f"scoring failed: {exc}", file=sys.stderr)
        return 1

    coverage = labels_coverage(labels)
    if args.output and report is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = {"coverage": coverage, **report}
        args.output.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", "utf-8")
    print(format_report(coverage, report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
