from __future__ import annotations

from pathlib import Path

from extractor.clients.yt_dlp import download_assets as download_assets_with_ytdlp
from extractor.clients.yt_dlp import download_media as download_media_with_ytdlp


def download_media(url: str, artifact_dir: Path) -> Path:
    return download_media_with_ytdlp(url, artifact_dir)


def download_assets(url: str, artifact_dir: Path) -> list[Path]:
    return download_assets_with_ytdlp(url, artifact_dir)
