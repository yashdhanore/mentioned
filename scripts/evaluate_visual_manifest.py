from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _contains(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


def evaluate(manifest_path: Path, artifacts_dir: Path) -> list[dict]:
    manifest = _load_json(manifest_path)
    reports: list[dict] = []
    for job in manifest.get("jobs", []):
        job_id = job["job_id"]
        result_path = artifacts_dir / job_id / "result.json"
        if not result_path.exists():
            reports.append(
                {
                    "job_id": job_id,
                    "result_path": str(result_path),
                    "error": "result.json not found",
                }
            )
            continue

        result = _load_json(result_path)
        text = result.get("text", {})
        visual_text = text.get("visual_text") or ""
        expected_lines = job.get("expected_visible_lines", [])
        noise_terms = job.get("known_noise_terms", [])
        found_lines = [line for line in expected_lines if _contains(visual_text, line)]
        found_noise = [term for term in noise_terms if _contains(visual_text, term)]
        reports.append(
            {
                "job_id": job_id,
                "expected_line_count": len(expected_lines),
                "found_line_count": len(found_lines),
                "visible_line_recall": (len(found_lines) / len(expected_lines)) if expected_lines else None,
                "missing_lines": [line for line in expected_lines if line not in found_lines],
                "known_noise_hits": found_noise,
            }
        )
    return reports


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("evals/visual_regression_manifest.json"),
    )
    parser.add_argument("--artifacts-dir", type=Path, default=Path("data/artifacts"))
    args = parser.parse_args()
    print(json.dumps(evaluate(args.manifest, args.artifacts_dir), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
