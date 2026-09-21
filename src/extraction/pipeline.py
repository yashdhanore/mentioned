from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from src.config import get_settings
from src.extraction.download import download_assets_with_metadata
from src.extraction.gemini import extract_mentions_from_media
from src.extraction.local_pipeline import extract_mentions_locally
from src.extraction.relevance import Verdict, assess_relevance
from src.extraction.schemas import ExtractedMention, PipelineResult
from src.sources.failure import SourceFailureReason, safe_source_error_message

logger = logging.getLogger(__name__)


def run_pipeline(source_url: str) -> PipelineResult:
    """Download media and return structured mentions."""
    with tempfile.TemporaryDirectory() as tmp:
        logger.info("Downloading media from %s", source_url)
        try:
            assets = download_assets_with_metadata(source_url, Path(tmp))
        except Exception as exc:
            logger.warning("Download failed for %s: %s", source_url, exc)
            return PipelineResult(
                error=safe_source_error_message(SourceFailureReason.DOWNLOAD_FAILED)
            )

        paths = assets.paths
        if not paths:
            return PipelineResult(
                thumbnail_url=assets.thumbnail_url,
                source_creator_handle=assets.source_creator_handle,
                error=safe_source_error_message(SourceFailureReason.NO_MEDIA),
            )

        total_size_mb = sum(path.stat().st_size for path in paths) / 1024 / 1024
        logger.info("Downloaded %d media file(s) (%.1f MB)", len(paths), total_size_mb)

        settings = get_settings()

        gate_mode = settings.relevance_gate_mode
        if gate_mode != "off":
            assessment = assess_relevance(
                caption=assets.caption,
                thumbnail_url=assets.thumbnail_url,
            )
            logger.info(
                "Relevance gate (mode=%s) for %s: verdict=%s reason=%s",
                gate_mode,
                source_url,
                assessment.verdict.value,
                assessment.reason,
            )
            if gate_mode == "active" and assessment.verdict is Verdict.IRRELEVANT:
                logger.info("Relevance gate skipping extraction for %s", source_url)
                return PipelineResult(
                    thumbnail_url=assets.thumbnail_url,
                    source_creator_handle=assets.source_creator_handle,
                    skip_reason=assessment.reason or "gated as irrelevant",
                )

        backend = settings.extraction_backend
        logger.info("Using %s extraction backend", backend)
        try:
            if backend == "local":
                raw = extract_mentions_locally(paths)
            else:
                raw = extract_mentions_from_media(paths)
        except Exception as exc:
            logger.warning("%s extraction failed: %s", backend, exc)
            return PipelineResult(
                thumbnail_url=assets.thumbnail_url,
                source_creator_handle=assets.source_creator_handle,
                error=safe_source_error_message(SourceFailureReason.EXTRACTION_FAILED),
            )

        logger.info("%s extraction returned %d mentions", backend, len(raw.get("mentions", [])))

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
                    location_hint=item.get("location_hint"),
                )
            )

        return PipelineResult(
            mentions=mentions,
            thumbnail_url=assets.thumbnail_url,
            source_creator_handle=assets.source_creator_handle,
        )
