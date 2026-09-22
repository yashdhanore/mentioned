from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from google.genai.types import GenerateContentConfig

from src.config import get_settings
from src.extraction.download import DownloadedAssets, download_assets_with_metadata
from src.extraction.gemini import (
    EXTRACTION_PROMPT,
    MENTION_SCHEMA,
    generate_with_retry,
    upload_to_gemini,
)
from src.extraction.gemini_client import get_gemini_client

DEFAULT_MODELS = ("gemini-2.5-flash", "gemini-3.1-flash-lite")
PRICING_SOURCE = "Gemini Developer API paid tier, standard mode, checked 2026-09-22"

# USD per 1M tokens. Gemini pricing separates audio input from text/image/video input.
DEFAULT_PRICE_TABLE: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {
        "input_text_image_video": 0.30,
        "input_audio": 1.00,
        "output": 2.50,
    },
    "gemini-3.1-flash-lite": {
        "input_text_image_video": 0.25,
        "input_audio": 0.50,
        "output": 1.50,
    },
    "gemini-3.5-flash-lite": {
        "input_text_image_video": 0.30,
        "input_audio": 0.30,
        "output": 2.50,
    },
    "gemini-3.5-flash": {
        "input_text_image_video": 1.50,
        "input_audio": 1.50,
        "output": 9.00,
    },
    # Launch pricing through 2026-12-31; doubles to 1.50 input / 7.50 output after.
    "gemini-3.8-flash": {
        "input_text_image_video": 0.75,
        "input_audio": 0.75,
        "output": 3.75,
    },
}

SOURCE_URL_RE = re.compile(r"https?://[^\s)\]>\"]+")
MEDIA_MANIFEST_NAME = "media-manifest.json"


class CompareError(RuntimeError):
    pass


def _env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _round_seconds(seconds: float) -> float:
    return round(seconds, 3)


def _round_usd(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 8)


def _normalize_models(models: list[str] | None) -> list[str]:
    stripped = (model.strip() for model in models or DEFAULT_MODELS)
    normalized = list(dict.fromkeys(model for model in stripped if model))
    if not normalized:
        raise CompareError("At least one model is required")
    return normalized


def _source_urls_from_text(value: str | None) -> list[str]:
    if not value:
        return []
    return list(
        dict.fromkeys(match.group(0).rstrip(".,") for match in SOURCE_URL_RE.finditer(value))
    )


def _normalize_source_urls(args: argparse.Namespace) -> list[str]:
    sources: list[str] = []
    for source_url in args.source_urls or []:
        sources.extend(_source_urls_from_text(source_url))
    if args.source_file:
        sources.extend(_source_urls_from_text(args.source_file.read_text(encoding="utf-8")))

    if not sources:
        sources.extend(_source_urls_from_text(_env("SOURCE_URLS")))
    if not sources:
        sources.extend(_source_urls_from_text(_env("SOURCE_URL")))

    normalized = list(dict.fromkeys(sources))
    if not normalized:
        raise CompareError(
            "Missing source URL. Pass one or more URLs, set SOURCE_URLS, or set SOURCE_URL."
        )
    return normalized


def _media_summary(path: Path) -> dict[str, Any]:
    return {
        "name": path.name,
        "path": str(path),
        "suffix": path.suffix,
        "bytes": path.stat().st_size,
    }


def _int_value(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _modality_name(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name.upper()
    return str(value).split(".")[-1].upper()


def _details_by_modality(details: Any) -> dict[str, int]:
    totals: dict[str, int] = {}
    if not isinstance(details, list):
        return totals
    for item in details:
        if not isinstance(item, dict):
            continue
        modality = _modality_name(item.get("modality"))
        token_count = _int_value(item.get("token_count"))
        if token_count:
            totals[modality] = totals.get(modality, 0) + token_count
    return totals


def _usage_token_summary(usage: dict[str, Any] | None) -> dict[str, Any] | None:
    if not usage:
        return None
    prompt_by_modality = _details_by_modality(usage.get("prompt_tokens_details"))
    output_tokens = _int_value(usage.get("candidates_token_count")) + _int_value(
        usage.get("thoughts_token_count")
    )
    return {
        "prompt_tokens": _int_value(usage.get("prompt_token_count")),
        "prompt_tokens_by_modality": prompt_by_modality,
        "candidate_tokens": _int_value(usage.get("candidates_token_count")),
        "thoughts_tokens": _int_value(usage.get("thoughts_token_count")),
        "output_billable_tokens": output_tokens,
        "total_tokens": _int_value(usage.get("total_token_count")),
    }


def _estimate_cost(model: str, usage: dict[str, Any] | None) -> dict[str, Any] | None:
    rates = DEFAULT_PRICE_TABLE.get(model)
    token_summary = _usage_token_summary(usage)
    if not rates or not token_summary:
        return None

    prompt_by_modality = token_summary["prompt_tokens_by_modality"]
    audio_input_tokens = prompt_by_modality.get("AUDIO", 0)
    prompt_tokens = token_summary["prompt_tokens"]
    non_audio_input_tokens = max(prompt_tokens - audio_input_tokens, 0)
    output_tokens = token_summary["output_billable_tokens"]

    input_text_image_video_usd = (
        non_audio_input_tokens * rates["input_text_image_video"] / 1_000_000
    )
    input_audio_usd = audio_input_tokens * rates["input_audio"] / 1_000_000
    output_usd = output_tokens * rates["output"] / 1_000_000
    total_usd = input_text_image_video_usd + input_audio_usd + output_usd

    return {
        "currency": "USD",
        "pricing_source": PRICING_SOURCE,
        "rates_per_million_tokens": rates,
        "input_text_image_video_tokens": non_audio_input_tokens,
        "input_audio_tokens": audio_input_tokens,
        "output_tokens": output_tokens,
        "input_text_image_video_usd": _round_usd(input_text_image_video_usd),
        "input_audio_usd": _round_usd(input_audio_usd),
        "output_usd": _round_usd(output_usd),
        "total_usd": _round_usd(total_usd),
    }


def _extract_mentions_for_model(paths: list[Path], *, model: str) -> dict[str, Any]:
    settings = get_settings()
    client = get_gemini_client(settings)
    file_parts = [
        upload_to_gemini(client, media_path, use_vertexai=settings.gemini.use_vertexai)
        for media_path in paths
    ]
    response = generate_with_retry(
        client,
        model=model,
        contents=[*file_parts, EXTRACTION_PROMPT],
        config=GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=MENTION_SCHEMA,
            temperature=0.1,
        ),
        total_attempts=settings.gemini.gemini_total_attempts,
    )
    try:
        raw = json.loads(response.text)
    except (json.JSONDecodeError, TypeError):
        raw = {"mentions": []}
    usage = response.usage_metadata
    return {
        "raw": raw,
        "usage": usage.model_dump(mode="json", exclude_none=True) if usage else None,
    }


def _run_model(paths: list[Path], model: str) -> dict[str, Any]:
    started = time.monotonic()
    try:
        response = _extract_mentions_for_model(paths, model=model)
    except Exception as exc:
        return {
            "model": model,
            "ok": False,
            "duration_seconds": _round_seconds(time.monotonic() - started),
            "error": f"{type(exc).__name__}: {exc}",
        }

    raw = response["raw"]
    usage = response["usage"]
    mentions = raw.get("mentions") if isinstance(raw, dict) else None
    return {
        "model": model,
        "ok": True,
        "duration_seconds": _round_seconds(time.monotonic() - started),
        "mention_count": len(mentions) if isinstance(mentions, list) else None,
        "usage": usage,
        "token_summary": _usage_token_summary(usage),
        "estimated_cost": _estimate_cost(model, usage),
        "raw": raw,
    }


def _write_media_manifest(media_dir: Path, source_url: str, assets: DownloadedAssets) -> None:
    manifest = {
        "source_url": source_url,
        "paths": [path.name for path in assets.paths],
        "thumbnail_url": assets.thumbnail_url,
        "source_creator_handle": assets.source_creator_handle,
    }
    (media_dir / MEDIA_MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")


def _reusable_media(media_dir: Path, source_url: str) -> DownloadedAssets | None:
    """Return a previous download of this exact source, or None to download again."""
    try:
        manifest = json.loads((media_dir / MEDIA_MANIFEST_NAME).read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if manifest.get("source_url") != source_url or not manifest.get("paths"):
        return None
    paths = [media_dir / name for name in manifest["paths"]]
    if not all(path.is_file() for path in paths):
        return None
    return DownloadedAssets(
        paths=paths,
        thumbnail_url=manifest.get("thumbnail_url"),
        source_creator_handle=manifest.get("source_creator_handle"),
    )


def _compare_in_dir(
    source_url: str,
    models: list[str],
    media_dir: Path,
    *,
    keep_media: bool,
    reuse_media: bool = False,
) -> dict[str, Any]:
    download_started = time.monotonic()
    assets = _reusable_media(media_dir, source_url) if reuse_media else None
    reused = assets is not None
    if assets is None:
        assets = download_assets_with_metadata(source_url, media_dir)
        if keep_media and assets.paths:
            _write_media_manifest(media_dir, source_url, assets)
    download_seconds = _round_seconds(time.monotonic() - download_started)
    paths = assets.paths

    payload: dict[str, Any] = {
        "source_url": source_url,
        "models": models,
        "download": {
            "duration_seconds": download_seconds,
            "media_dir": str(media_dir),
            "media_dir_kept": keep_media,
            "media_reused": reused,
            "media_count": len(paths),
            "media": [_media_summary(path) for path in paths],
            "thumbnail_url": assets.thumbnail_url,
            "source_creator_handle": assets.source_creator_handle,
        },
        "results": [],
    }

    if not paths:
        payload["error"] = "No media downloaded"
        return payload

    with ThreadPoolExecutor(max_workers=len(models)) as executor:
        futures = {executor.submit(_run_model, paths, model): model for model in models}
        results_by_model = {futures[future]: future.result() for future in as_completed(futures)}

    payload["results"] = [results_by_model[model] for model in models]
    return payload


def _media_dir_for_source(media_dir: Path, source_count: int, index: int) -> Path:
    if source_count == 1:
        return media_dir
    return media_dir / f"source_{index + 1:03d}"


def _failed_source(source_url: str, exc: Exception) -> dict[str, Any]:
    return {
        "source_url": source_url,
        "download_error": f"{type(exc).__name__}: {exc}",
        "results": [],
    }


def _summarize_batch(sources: list[dict[str, Any]], models: list[str]) -> dict[str, Any]:
    by_model = {
        model: {
            "model": model,
            "sources": 0,
            "successful_sources": 0,
            "failed_sources": 0,
            "mentions": 0,
            "duration_seconds": 0.0,
            "prompt_tokens": 0,
            "output_billable_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "cost_estimate_missing": False,
        }
        for model in models
    }

    failed_downloads = 0
    for source in sources:
        if source.get("error") == "No media downloaded" or "download_error" in source:
            failed_downloads += 1
        for result in source["results"]:
            item = by_model[result["model"]]
            item["sources"] += 1
            item["duration_seconds"] += result["duration_seconds"]
            if result["ok"]:
                item["successful_sources"] += 1
                item["mentions"] += result["mention_count"] or 0
            else:
                item["failed_sources"] += 1

            token_summary = result.get("token_summary")
            if token_summary:
                item["prompt_tokens"] += token_summary["prompt_tokens"]
                item["output_billable_tokens"] += token_summary["output_billable_tokens"]
                item["total_tokens"] += token_summary["total_tokens"]

            estimated_cost = result.get("estimated_cost")
            if estimated_cost:
                item["estimated_cost_usd"] += estimated_cost["total_usd"]
            elif result["ok"]:
                item["cost_estimate_missing"] = True

    model_summaries = []
    total_cost_usd = 0.0
    missing_cost = False
    for model in models:
        item = by_model[model]
        item["duration_seconds"] = _round_seconds(item["duration_seconds"])
        item["estimated_cost_usd"] = _round_usd(item["estimated_cost_usd"])
        total_cost_usd += item["estimated_cost_usd"] or 0
        missing_cost = missing_cost or bool(item["cost_estimate_missing"])
        model_summaries.append(item)

    return {
        "source_count": len(sources),
        "failed_downloads": failed_downloads,
        "models": model_summaries,
        "estimated_total_cost_usd": _round_usd(total_cost_usd),
        "cost_estimate_missing": missing_cost,
        "pricing_source": PRICING_SOURCE,
    }


def compare_sources(
    source_urls: list[str],
    *,
    models: list[str] | None = None,
    media_dir: Path | None = None,
    reuse_media: bool = False,
) -> dict[str, Any]:
    model_names = _normalize_models(models)
    started = time.monotonic()
    sources: list[dict[str, Any]] = []

    if media_dir:
        media_dir.mkdir(parents=True, exist_ok=True)
        for index, source_url in enumerate(source_urls):
            source_media_dir = _media_dir_for_source(media_dir, len(source_urls), index)
            source_media_dir.mkdir(parents=True, exist_ok=True)
            try:
                sources.append(
                    _compare_in_dir(
                        source_url,
                        model_names,
                        source_media_dir,
                        keep_media=True,
                        reuse_media=reuse_media,
                    )
                )
            except Exception as exc:
                sources.append(_failed_source(source_url, exc))
    else:
        for source_url in source_urls:
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    sources.append(
                        _compare_in_dir(source_url, model_names, Path(tmp), keep_media=False)
                    )
                except Exception as exc:
                    sources.append(_failed_source(source_url, exc))

    return {
        "models": model_names,
        "total_duration_seconds": _round_seconds(time.monotonic() - started),
        "summary": _summarize_batch(sources, model_names),
        "sources": sources,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Instagram sources and compare Gemini video extraction models."
    )
    parser.add_argument(
        "source_urls",
        nargs="*",
        help="Instagram Reel/post URLs. Defaults to SOURCE_URLS or SOURCE_URL.",
    )
    parser.add_argument(
        "--source-file",
        type=Path,
        default=None,
        help="Text file containing source URLs separated by whitespace, commas, or newlines.",
    )
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        default=None,
        help=(
            "Gemini model to run. Repeat to compare more models. "
            "Defaults to gemini-2.5-flash and gemini-3.1-flash-lite."
        ),
    )
    parser.add_argument(
        "--media-dir",
        type=Path,
        default=None,
        help=(
            "Directory for downloaded media. Multiple sources use source_001, source_002, "
            "... subdirectories."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the comparison JSON.",
    )
    parser.add_argument(
        "--reuse-media",
        action="store_true",
        help=(
            "Reuse media a previous run saved under --media-dir for the same source URL "
            "instead of downloading it again, e.g. when iterating on the prompt."
        ),
    )
    args = parser.parse_args()
    if args.reuse_media and args.media_dir is None:
        parser.error("--reuse-media requires --media-dir")
    return args


def main() -> int:
    args = parse_args()
    try:
        source_urls = _normalize_source_urls(args)
        payload = compare_sources(
            source_urls,
            models=args.models,
            media_dir=args.media_dir,
            reuse_media=args.reuse_media,
        )
    except Exception as exc:
        print(f"comparison failed: {exc}", file=sys.stderr)
        return 1

    output = json.dumps(payload, indent=2, sort_keys=True, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{output}\n", encoding="utf-8")
    print(output)

    results = [result for source in payload["sources"] for result in source["results"]]
    if results and not any(result["ok"] for result in results):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
