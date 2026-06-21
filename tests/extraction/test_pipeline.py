from __future__ import annotations

from unittest.mock import patch

import pytest

from src.config import Settings
from src.extraction.download import DownloadedAssets
from src.extraction.pipeline import run_pipeline


@pytest.fixture(autouse=True)
def use_gemini_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.extraction.pipeline.get_settings",
        lambda: Settings(extraction_backend="gemini"),
    )


@patch("src.extraction.pipeline.download_assets_with_metadata")
@patch("src.extraction.pipeline.extract_mentions_from_media")
def test_pipeline_success(mock_extract, mock_download, tmp_path):
    media_file = tmp_path / "media_001.mp4"
    media_file.write_bytes(b"fake video")
    mock_download.return_value = DownloadedAssets(
        paths=[media_file],
        thumbnail_url="https://example.com/reel.jpg",
        source_creator_handle="jamesclear",
    )
    mock_extract.return_value = {
        "mentions": [
            {"title": "Atomic Habits", "author": "James Clear", "category": "book", "confidence": 0.95},
            {"title": "Cafe Nero", "category": "place", "confidence": 0.7},
        ]
    }

    result = run_pipeline("https://instagram.com/reel/ABC123/")

    mock_extract.assert_called_once_with([media_file])
    assert result.error is None
    assert result.thumbnail_url == "https://example.com/reel.jpg"
    assert result.source_creator_handle == "jamesclear"
    assert len(result.mentions) == 2
    assert result.mentions[0].title == "Atomic Habits"
    assert result.mentions[0].author == "James Clear"
    assert result.mentions[0].category == "book"
    assert result.mentions[0].confidence == 0.95
    assert result.mentions[1].title == "Cafe Nero"
    assert result.mentions[1].category == "place"


@patch("src.extraction.pipeline.download_assets_with_metadata")
@patch("src.extraction.pipeline.extract_mentions_from_media")
def test_pipeline_extracts_from_all_downloaded_media(mock_extract, mock_download, tmp_path):
    first_media_file = tmp_path / "media_001.jpg"
    second_media_file = tmp_path / "media_002.jpg"
    first_media_file.write_bytes(b"fake image 1")
    second_media_file.write_bytes(b"fake image 2")
    mock_download.return_value = DownloadedAssets(paths=[first_media_file, second_media_file])
    mock_extract.return_value = {"mentions": []}

    result = run_pipeline("https://instagram.com/p/ABC123/")

    mock_extract.assert_called_once_with([first_media_file, second_media_file])
    assert result.error is None


@patch("src.extraction.pipeline.download_assets_with_metadata")
def test_pipeline_download_failure(mock_download):
    mock_download.side_effect = RuntimeError("Network error")

    result = run_pipeline("https://instagram.com/reel/ABC123/")

    assert result.error is not None
    assert "Download failed" in result.error
    assert result.mentions == []


@patch("src.extraction.pipeline.download_assets_with_metadata")
@patch("src.extraction.pipeline.extract_mentions_from_media")
def test_pipeline_extraction_failure(mock_extract, mock_download, tmp_path):
    media_file = tmp_path / "media_001.mp4"
    media_file.write_bytes(b"fake video")
    mock_download.return_value = DownloadedAssets(
        paths=[media_file],
        thumbnail_url="https://example.com/reel.jpg",
        source_creator_handle="jamesclear",
    )
    mock_extract.side_effect = RuntimeError("Gemini API error")

    result = run_pipeline("https://instagram.com/reel/ABC123/")

    assert result.error is not None
    assert "Extraction failed" in result.error
    assert result.thumbnail_url == "https://example.com/reel.jpg"
    assert result.source_creator_handle == "jamesclear"


@patch("src.extraction.pipeline.download_assets_with_metadata")
@patch("src.extraction.pipeline.extract_mentions_from_media")
def test_pipeline_empty_mentions(mock_extract, mock_download, tmp_path):
    media_file = tmp_path / "media_001.mp4"
    media_file.write_bytes(b"fake video")
    mock_download.return_value = DownloadedAssets(paths=[media_file])
    mock_extract.return_value = {"mentions": []}

    result = run_pipeline("https://instagram.com/reel/ABC123/")

    assert result.error is None
    assert result.mentions == []
