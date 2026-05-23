from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Any

from src.config import get_settings

logger = logging.getLogger(__name__)

VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


@dataclass(frozen=True)
class DownloadedAssets:
    paths: list[Path]
    thumbnail_url: str | None = None


def is_available() -> bool:
    return shutil.which("yt-dlp") is not None


def _yt_dlp_size_limit(max_file_bytes: int) -> str:
    mib = max(1, max_file_bytes // (1024 * 1024))
    return f"{mib}M"


def _default_format_selector(max_file_bytes: int) -> str:
    size_limit = _yt_dlp_size_limit(max_file_bytes)
    return (
        f"best[filesize<={size_limit}]/"
        f"best[filesize_approx<={size_limit}]/"
        "best[height<=720]/"
        "worst"
    )


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


def _text_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _numeric(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _thumbnail_url(metadata: dict[str, Any]) -> str | None:
    best_url = None
    best_area = -1.0
    thumbnails = metadata.get("thumbnails")
    if isinstance(thumbnails, list):
        for item in thumbnails:
            if not isinstance(item, dict):
                continue
            url = _text_or_none(item.get("url"))
            if not url:
                continue
            area = _numeric(item.get("width")) * _numeric(item.get("height"))
            if area > best_area:
                best_url = url
                best_area = area
    if best_url:
        return best_url
    return _text_or_none(metadata.get("thumbnail"))


def _check_size_limits(paths: list[Path], *, max_file_bytes: int, max_total_bytes: int) -> None:
    total_bytes = 0
    for path in paths:
        file_bytes = path.stat().st_size
        if file_bytes > max_file_bytes:
            raise RuntimeError(
                f"Downloaded media file exceeds limit of {max_file_bytes} bytes "
                f"({path.name}: {file_bytes} bytes)"
            )
        total_bytes += file_bytes
    if total_bytes > max_total_bytes:
        raise RuntimeError(
            f"Downloaded media total exceeds limit of {max_total_bytes} bytes "
            f"({total_bytes} bytes)"
        )


def _compress_video(
    path: Path,
    *,
    timeout_seconds: int,
    video_bitrate: str,
    audio_bitrate: str,
) -> Path:
    compressed_path = path.with_name(f"{path.stem}.compressed.mp4")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(path),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-b:v",
            video_bitrate,
            "-maxrate",
            video_bitrate,
            "-bufsize",
            "2M",
            "-c:a",
            "aac",
            "-b:a",
            audio_bitrate,
            "-movflags",
            "+faststart",
            str(compressed_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return compressed_path


def _compress_oversized_video(
    path: Path,
    *,
    max_file_bytes: int,
    timeout_seconds: int,
    video_bitrate: str,
    audio_bitrate: str,
) -> Path:
    if path.stat().st_size <= max_file_bytes:
        return path
    if path.suffix.lower() not in VIDEO_SUFFIXES:
        return path
    if shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg is unavailable; cannot compress oversized media %s", path.name)
        return path

    logger.info("Compressing oversized media %s before extraction", path.name)
    try:
        compressed_path = _compress_video(
            path,
            timeout_seconds=timeout_seconds,
            video_bitrate=video_bitrate,
            audio_bitrate=audio_bitrate,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("Failed to compress oversized media %s: %s", path.name, exc)
        return path

    if not compressed_path.exists():
        logger.warning("ffmpeg completed without producing %s", compressed_path.name)
        return path
    if compressed_path.stat().st_size >= path.stat().st_size:
        logger.warning("Compressed media is not smaller than source: %s", compressed_path.name)
        return path

    path.unlink(missing_ok=True)
    return compressed_path


def _compress_oversized_media(
    paths: list[Path],
    *,
    max_file_bytes: int,
    timeout_seconds: int,
    video_bitrate: str,
    audio_bitrate: str,
) -> list[Path]:
    return [
        _compress_oversized_video(
            path,
            max_file_bytes=max_file_bytes,
            timeout_seconds=timeout_seconds,
            video_bitrate=video_bitrate,
            audio_bitrate=audio_bitrate,
        )
        for path in paths
    ]


def download_assets_with_metadata(url: str, output_dir: Path) -> DownloadedAssets:
    if not is_available():
        raise FileNotFoundError("yt-dlp is not installed")
    settings = get_settings()
    metadata = _preflight_metadata(url, timeout_seconds=settings.media_download_timeout_seconds)
    thumbnail_url = _thumbnail_url(metadata)
    _check_duration_limit(
        metadata,
        max_duration_seconds=settings.max_media_duration_seconds,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = output_dir / "media_%(autonumber)03d.%(ext)s"
    raw_size_limit = _yt_dlp_size_limit(
        max(settings.max_media_file_bytes, settings.max_media_total_bytes)
    )
    format_selector = settings.media_download_format or _default_format_selector(
        settings.max_media_file_bytes
    )
    completed = subprocess.run(
        [
            "yt-dlp",
            "--no-progress",
            "--format",
            format_selector,
            "--max-filesize",
            raw_size_limit,
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
    paths = _compress_oversized_media(
        paths,
        max_file_bytes=settings.max_media_file_bytes,
        timeout_seconds=settings.media_download_timeout_seconds,
        video_bitrate=settings.media_transcode_video_bitrate,
        audio_bitrate=settings.media_transcode_audio_bitrate,
    )
    _check_size_limits(
        paths,
        max_file_bytes=settings.max_media_file_bytes,
        max_total_bytes=settings.max_media_total_bytes,
    )
    return DownloadedAssets(paths=paths, thumbnail_url=thumbnail_url)


def download_assets(url: str, output_dir: Path) -> list[Path]:
    return download_assets_with_metadata(url, output_dir).paths
