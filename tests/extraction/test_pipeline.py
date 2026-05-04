from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.extraction.pipeline import run_pipeline
from src.extraction.schemas import ExtractedMention, PipelineResult


@patch("src.extraction.pipeline.download_assets")
@patch("src.extraction.pipeline.extract_mentions_from_media")
def test_pipeline_success(mock_extract, mock_download, tmp_path):
    media_file = tmp_path / "media_001.mp4"
    media_file.write_bytes(b"fake video")
    mock_download.return_value = [media_file]
    mock_extract.return_value = {
        "mentions": [
            {"title": "Atomic Habits", "author": "James Clear", "category": "book", "confidence": 0.95},
            {"title": "Cafe Nero", "category": "place", "confidence": 0.7},
        ]
    }

    result = run_pipeline("https://instagram.com/reel/ABC123/")

    assert result.error is None
    assert len(result.mentions) == 2
    assert result.mentions[0].title == "Atomic Habits"
    assert result.mentions[0].author == "James Clear"
    assert result.mentions[0].category == "book"
    assert result.mentions[0].confidence == 0.95
    assert result.mentions[1].title == "Cafe Nero"
    assert result.mentions[1].category == "place"


@patch("src.extraction.pipeline.download_assets")
def test_pipeline_download_failure(mock_download):
    mock_download.side_effect = RuntimeError("Network error")

    result = run_pipeline("https://instagram.com/reel/ABC123/")

    assert result.error is not None
    assert "Download failed" in result.error
    assert result.mentions == []


@patch("src.extraction.pipeline.download_assets")
@patch("src.extraction.pipeline.extract_mentions_from_media")
def test_pipeline_extraction_failure(mock_extract, mock_download, tmp_path):
    media_file = tmp_path / "media_001.mp4"
    media_file.write_bytes(b"fake video")
    mock_download.return_value = [media_file]
    mock_extract.side_effect = RuntimeError("Gemini API error")

    result = run_pipeline("https://instagram.com/reel/ABC123/")

    assert result.error is not None
    assert "Extraction failed" in result.error


@patch("src.extraction.pipeline.download_assets")
@patch("src.extraction.pipeline.extract_mentions_from_media")
def test_pipeline_empty_mentions(mock_extract, mock_download, tmp_path):
    media_file = tmp_path / "media_001.mp4"
    media_file.write_bytes(b"fake video")
    mock_download.return_value = [media_file]
    mock_extract.return_value = {"mentions": []}

    result = run_pipeline("https://instagram.com/reel/ABC123/")

    assert result.error is None
    assert result.mentions == []
