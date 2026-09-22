from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import score_extraction_eval
from scripts.score_extraction_eval import LabelsError, load_labels, score_results
from src.books.titles import TITLE_MATCH_THRESHOLD

REEL_A = "https://www.instagram.com/reel/AAA111/"
REEL_B = "https://www.instagram.com/reel/BBB222/?igsh=tracking"
REEL_EMPTY = "https://www.instagram.com/reel/EMPTY33/"
REEL_TODO = "https://www.instagram.com/reel/TODO444/"


def _write_labels(tmp_path: Path, reels: list[dict]) -> Path:
    path = tmp_path / "labels.json"
    path.write_text(json.dumps({"schema_version": "reel_labels.v1", "reels": reels}))
    return path


def _book(title: str, author: str | None = None, **extra) -> dict:
    return {"category": "book", "title": title, "author": author, **extra}


def _result(model: str, mentions: list[dict], *, cost: float = 0.001, ok: bool = True) -> dict:
    result = {
        "model": model,
        "ok": ok,
        "duration_seconds": 4.0,
        "estimated_cost": {"total_usd": cost},
    }
    if ok:
        result["raw"] = {"mentions": mentions}
    else:
        result["error"] = "RuntimeError: boom"
    return result


def _labels(tmp_path: Path) -> dict:
    return load_labels(
        _write_labels(
            tmp_path,
            [
                {
                    "source_url": REEL_A,
                    "status": "labeled",
                    "expected_mentions": [
                        _book("The Picture of Dorian Gray", "Oscar Wilde"),
                        _book("Nineteen Eighty-Four", "George Orwell", aliases=["1984"]),
                        _book("Atomic Habits", "James Clear", optional=True),
                    ],
                },
                {
                    "source_url": "https://www.instagram.com/reel/BBB222/",
                    "status": "labeled",
                    "expected_mentions": [_book("Song of Solomon", "Toni Morrison")],
                },
                {"source_url": REEL_EMPTY, "status": "labeled", "expected_mentions": []},
                {"source_url": REEL_TODO, "status": "todo", "expected_mentions": []},
            ],
        )
    )


def test_fuzzy_matching_scores_precision_recall_and_authors(tmp_path):
    labels = _labels(tmp_path)
    results = {
        "sources": [
            {
                "source_url": REEL_A,
                "results": [
                    _result(
                        "flash",
                        [
                            _book("Picture of Dorian Gray: A Novel", "Wilde", confidence=0.9),
                            _book("1984", "Orwell", confidence=0.8),
                            _book("Atomic Habits", "James Clear", confidence=0.7),
                            _book("Invented Book", "Nobody", confidence=0.4),
                        ],
                    )
                ],
            },
            {
                "source_url": REEL_B,
                "results": [_result("flash", [_book("Song of Solomon", "Morrison")])],
            },
            {
                "source_url": REEL_EMPTY,
                "results": [_result("flash", [_book("Dance Moves", confidence=0.2)])],
            },
        ]
    }

    report = score_results(labels, results)

    [flash] = report["models"]
    assert flash["true_positives"] == 3
    assert flash["false_positives"] == 2
    assert flash["false_negatives"] == 0
    assert flash["optional_hits"] == 1
    assert flash["precision"] == 0.6
    assert flash["recall"] == 1.0
    assert flash["author_accuracy"] == 1.0
    assert flash["empty_source_false_positives"] == 1
    assert flash["mean_confidence_false_positives"] == 0.3
    assert flash["precision_ci95"][0] < 0.6 < flash["precision_ci95"][1]
    assert flash["estimated_cost_usd"] == 0.003
    assert flash["cost_per_true_positive_usd"] == 0.001


def test_misses_wrong_category_and_failed_extractions_count_against_recall(tmp_path):
    labels = _labels(tmp_path)
    results = {
        "sources": [
            {
                "source_url": REEL_A,
                "results": [
                    _result(
                        "lite",
                        [{"category": "product", "title": "The Picture of Dorian Gray"}],
                    ),
                    _result("flash", [], ok=False),
                ],
            }
        ]
    }

    report = score_results(labels, results)
    by_model = {model["model"]: model for model in report["models"]}

    assert by_model["lite"]["true_positives"] == 0
    assert by_model["lite"]["false_positives"] == 1
    assert by_model["lite"]["false_negatives"] == 2
    assert by_model["flash"]["failed_extractions"] == 1
    assert by_model["flash"]["false_negatives"] == 2
    assert by_model["flash"]["precision"] is None


def test_unlabeled_and_undownloaded_reels_are_reported_not_scored(tmp_path):
    labels = _labels(tmp_path)
    results = {
        "sources": [
            {"source_url": REEL_TODO, "results": [_result("flash", [_book("X")])]},
            {"source_url": "https://www.instagram.com/reel/NEW555/", "results": []},
            {"source_url": REEL_B, "download_error": "DownloadError: gone", "results": []},
        ]
    }

    report = score_results(labels, results)

    assert report["models"] == []
    assert report["unlabeled_sources"] == [
        REEL_TODO,
        "https://www.instagram.com/reel/NEW555/",
    ]
    assert report["unscored_sources"][0]["source_url"] == REEL_B


def test_single_source_compare_output_is_accepted(tmp_path):
    labels = _labels(tmp_path)
    results = {"source_url": REEL_B, "results": [_result("flash", [_book("Song of Solomon")])]}

    [flash] = score_results(labels, results)["models"]

    assert flash["recall"] == 1.0
    assert flash["author_accuracy"] == 0.0


def test_evidence_and_timestamp_coverage_are_reported(tmp_path):
    labels = _labels(tmp_path)
    mentions = [
        _book(
            "Song of Solomon",
            evidence={"source": "speech", "timestamp": "0:07", "quote": "Song of Solomon"},
        ),
        _book("Beloved", evidence={"source": "visual", "timestamp": "around the end"}),
        _book("Sula"),
    ]
    results = {"source_url": REEL_B, "results": [_result("flash", mentions)]}

    [flash] = score_results(labels, results)["models"]

    assert flash["evidence_coverage"] == 0.667
    assert flash["timestamp_coverage"] == 0.333


@pytest.mark.parametrize(
    ("predicted", "expected"),
    [
        ("Partition The Long Shadow", "Partition: The Long Shadow"),
        ("Mga Ibong Mandaragit / The Preying Birds", "The Preying Birds"),
        ("Mga Ibong Mandaragit (The Preying Birds)", "The Preying Birds"),
        ("Luha ng Buwaya (Crocodile's Tears)", "Luha ng Buwaya"),
        ("Dune: Deluxe Edition", "Dune"),
    ],
)
def test_title_matching_handles_subtitles_and_bilingual_titles(predicted, expected):
    label = score_extraction_eval.ExpectedMention(
        category="book", title=expected, author=None, aliases=(), optional=False
    )
    assert score_extraction_eval.title_similarity(predicted, label) == 1.0


def test_unrelated_titles_do_not_match():
    label = score_extraction_eval.ExpectedMention(
        category="book", title="The Trial", author=None, aliases=(), optional=False
    )
    assert score_extraction_eval.title_similarity("The Castle", label) < TITLE_MATCH_THRESHOLD


@pytest.mark.parametrize(
    ("reel", "message"),
    [
        ({"source_url": REEL_A, "status": "done"}, "status must be one of"),
        (
            {"source_url": REEL_A, "status": "labeled", "expected_mentions": [{"title": "X"}]},
            "category must be one of",
        ),
        (
            {
                "source_url": REEL_A,
                "status": "labeled",
                "expected_mentions": [{"category": "book", "title": "  "}],
            },
            "title is required",
        ),
        ({"source_url": "https://example.com/reel/1/", "status": "todo"}, "Instagram"),
    ],
)
def test_invalid_labels_are_rejected(tmp_path, reel, message):
    with pytest.raises(LabelsError, match=message):
        load_labels(_write_labels(tmp_path, [reel]))


def test_duplicate_reels_are_rejected_after_url_canonicalization(tmp_path):
    reels = [
        {"source_url": REEL_B, "status": "todo"},
        {"source_url": "https://instagram.com/reel/BBB222/", "status": "todo"},
    ]
    with pytest.raises(LabelsError, match="duplicate Reel"):
        load_labels(_write_labels(tmp_path, reels))


def test_main_without_results_reports_label_coverage(tmp_path, capsys):
    labels_path = _write_labels(
        tmp_path,
        [
            {"source_url": REEL_A, "status": "labeled", "expected_mentions": [_book("A")]},
            {"source_url": REEL_TODO, "status": "todo"},
        ],
    )

    exit_code = score_extraction_eval.main(["--labels", str(labels_path)])

    assert exit_code == 0
    assert "Labels: 1/2 labeled, 1 todo" in capsys.readouterr().out


def test_main_writes_full_report(tmp_path, capsys):
    labels_path = _write_labels(
        tmp_path,
        [{"source_url": REEL_A, "status": "labeled", "expected_mentions": [_book("A Book")]}],
    )
    results_path = tmp_path / "result.json"
    results_path.write_text(
        json.dumps(
            {"sources": [{"source_url": REEL_A, "results": [_result("m", [_book("A Book")])]}]}
        )
    )
    output_path = tmp_path / "out" / "score.json"

    exit_code = score_extraction_eval.main(
        ["--labels", str(labels_path), "--results", str(results_path), "--output", str(output_path)]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text())
    assert payload["coverage"]["labeled"] == 1
    assert payload["models"][0]["f1"] == 1.0
    assert "recall" in capsys.readouterr().out


def test_repo_labels_file_is_valid():
    labels = load_labels(Path("evals/reel-labels.json"))
    reel_list_urls = [
        url
        for name in ("gemini-video-smoke-4.txt", "gemini-video-comparison-20.txt")
        for url in Path("evals/reel-lists", name).read_text().split()
    ]

    assert {score_extraction_eval.source_key_for(url) for url in reel_list_urls} == set(labels)
