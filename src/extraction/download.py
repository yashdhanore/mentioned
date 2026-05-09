from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from src.config import get_settings


def is_available() -> bool:
    return shutil.which("yt-dlp") is not None


def _duration_values(metadata: dict[str, Any]) -> list[float]:
    durations: list[float] = []
    value = metadata.get("duration")
    if isinstance(value, (int, float)):
        durations.append(float(value))
    entries = metadata.get("entries")
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict):
                durations.extend(_duration_values(entry))
    return durations


def _preflight_metadata(url: str, *, timeout_seconds: int) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "yt-dlp",
            "--no-progress",
            "--dump-single-json",
            "--skip-download",
            url,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    try:
        metadata = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("yt-dlp returned invalid metadata JSON") from exc
    if not isinstance(metadata, dict):
        raise RuntimeError("yt-dlp returned unexpected metadata")
    return metadata


def _check_duration_limit(metadata: dict[str, Any], *, max_duration_seconds: int) -> None:
    for duration in _duration_values(metadata):
        if duration > max_duration_seconds:
            raise RuntimeError(
                f"Media duration {duration:.1f}s exceeds limit of {max_duration_seconds}s"
            )


def _check_size_limits(paths: list[Path], *, max_file_bytes: int, max_total_bytes: int) -> None:
    total_bytes = 0
    for path in paths:
        file_bytes = path.stat().st_size
        if file_bytes > max_file_bytes:
            raise RuntimeError(f"Downloaded media file exceeds limit of {max_file_bytes} bytes")
        total_bytes += file_bytes
    if total_bytes > max_total_bytes:
        raise RuntimeError(f"Downloaded media total exceeds limit of {max_total_bytes} bytes")


def download_assets(url: str, output_dir: Path) -> list[Path]:
    if not is_available():
        raise FileNotFoundError("yt-dlp is not installed")
    settings = get_settings()
    metadata = _preflight_metadata(url, timeout_seconds=settings.media_download_timeout_seconds)
    _check_duration_limit(
        metadata,
        max_duration_seconds=settings.max_media_duration_seconds,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = output_dir / "media_%(autonumber)03d.%(ext)s"
    completed = subprocess.run(
        [
            "yt-dlp",
            "--no-progress",
            "--print",
            "after_move:filepath",
            "-o",
            str(output_template),
            url,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=settings.media_download_timeout_seconds,
    )
    output_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not output_lines:
        raise RuntimeError("yt-dlp did not report any output paths")
    paths = [Path(line) for line in output_lines]
    _check_size_limits(
        paths,
        max_file_bytes=settings.max_media_file_bytes,
        max_total_bytes=settings.max_media_total_bytes,
    )
    return paths
