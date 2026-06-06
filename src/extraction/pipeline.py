from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from src.extraction.download import download_assets_with_metadata
from src.extraction.gemini import extract_mentions_from_media
from src.extraction.schemas import ExtractedMention, PipelineResult

logger = logging.getLogger(__name__)


def run_pipeline(source_url: str) -> PipelineResult:
    """Download media, send to Gemini, return structured mentions."""
    with tempfile.TemporaryDirectory() as tmp:
        logger.info("Downloading media from %s", source_url)
        try:
            assets = download_assets_with_metadata(source_url, Path(tmp))
        except Exception as exc:
            logger.warning("Download failed for %s: %s", source_url, exc)
            return PipelineResult(error=f"Download failed: {exc}")

        paths = assets.paths
        if not paths:
            return PipelineResult(
                thumbnail_url=assets.thumbnail_url,
                source_creator_handle=assets.source_creator_handle,
                error="No media downloaded",
            )

        total_size_mb = sum(path.stat().st_size for path in paths) / 1024 / 1024
        logger.info("Downloaded %d media file(s) (%.1f MB)", len(paths), total_size_mb)

        logger.info("Sending to Gemini for extraction...")
        try:
            raw = extract_mentions_from_media(paths)
        except Exception as exc:
            logger.warning("Gemini extraction failed: %s", exc)
            return PipelineResult(
                thumbnail_url=assets.thumbnail_url,
                source_creator_handle=assets.source_creator_handle,
                error=f"Extraction failed: {exc}",
            )

        logger.info("Gemini returned %d mentions", len(raw.get("mentions", [])))

        mentions = []
        for item in raw.get("mentions", []):
            title = item.get("title")
            if not title:
                continue
            mentions.append(
                ExtractedMention(
                    title=title,
                    author=item.get("author"),
                    category=item.get("category", "book"),
                    confidence=float(item.get("confidence", 0.5)),
                )
            )

        return PipelineResult(
            mentions=mentions,
            thumbnail_url=assets.thumbnail_url,
            source_creator_handle=assets.source_creator_handle,
        )
