from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config import get_settings
from src.extraction.download import download_assets, download_assets_with_metadata


@pytest.fixture(autouse=True)
def download_limit_env(monkeypatch):
    monkeypatch.setenv("MEDIA_DOWNLOAD_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("MAX_MEDIA_FILE_BYTES", "5")
    monkeypatch.setenv("MAX_MEDIA_TOTAL_BYTES", "7")
    monkeypatch.setenv("MAX_MEDIA_DURATION_SECONDS", "10")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _completed(stdout: str = "") -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout)


def test_download_assets_uses_timeout(monkeypatch, tmp_path):
    calls = []
    media_file = tmp_path / "media_001.mp4"

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        if "--dump-single-json" in args:
            return _completed(json.dumps({"duration": 8}))
        media_file.write_bytes(b"12345")
        return _completed(str(media_file))

    monkeypatch.setattr("src.extraction.download.is_available", lambda: True)
    monkeypatch.setattr("src.extraction.download.subprocess.run", fake_run)

    paths = download_assets("https://instagram.com/reel/ABC123/", tmp_path)

    assert paths == [media_file]
    assert len(calls) == 2
    assert all(kwargs["timeout"] == 7 for _args, kwargs in calls)
    download_args = calls[1][0]
    assert "--format" in download_args
    assert "--max-filesize" in download_args


def test_download_assets_with_metadata_returns_largest_thumbnail(monkeypatch, tmp_path):
    media_file = tmp_path / "media_001.mp4"

    def fake_run(args, **kwargs):
        if "--dump-single-json" in args:
            return _completed(
                json.dumps(
                    {
                        "duration": 8,
                        "thumbnail": "https://example.com/default.jpg",
                        "thumbnails": [
                            {
                                "url": "https://example.com/small.jpg",
                                "width": 320,
                                "height": 568,
                            },
                            {
                                "url": "https://example.com/large.jpg",
                                "width": 1080,
                                "height": 1917,
                            },
                        ],
                    }
                )
            )
        media_file.write_bytes(b"12345")
        return _completed(str(media_file))

    monkeypatch.setattr("src.extraction.download.is_available", lambda: True)
    monkeypatch.setattr("src.extraction.download.subprocess.run", fake_run)

    assets = download_assets_with_metadata("https://instagram.com/reel/ABC123/", tmp_path)

    assert assets.paths == [media_file]
    assert assets.thumbnail_url == "https://example.com/large.jpg"


def test_download_assets_rejects_duration_over_limit(monkeypatch, tmp_path):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return _completed(json.dumps({"duration": 12}))

    monkeypatch.setattr("src.extraction.download.is_available", lambda: True)
    monkeypatch.setattr("src.extraction.download.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="duration"):
        download_assets("https://instagram.com/reel/ABC123/", tmp_path)

    assert len(calls) == 1


def test_download_assets_rejects_single_file_over_limit(monkeypatch, tmp_path):
    media_file = tmp_path / "media_001.mp4"

    def fake_run(args, **kwargs):
        if "--dump-single-json" in args:
            return _completed(json.dumps({"duration": 8}))
        media_file.write_bytes(b"123456")
        return _completed(str(media_file))

    monkeypatch.setattr("src.extraction.download.is_available", lambda: True)
    monkeypatch.setattr("src.extraction.download.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="file exceeds limit"):
        download_assets("https://instagram.com/reel/ABC123/", tmp_path)


def test_download_assets_rejects_total_size_over_limit(monkeypatch, tmp_path):
    first_file = tmp_path / "media_001.jpg"
    second_file = tmp_path / "media_002.jpg"

    def fake_run(args, **kwargs):
        if "--dump-single-json" in args:
            return _completed(json.dumps({"entries": [{"duration": 0}, {"duration": 0}]}))
        first_file.write_bytes(b"1234")
        second_file.write_bytes(b"5678")
        return _completed(f"{first_file}\n{second_file}")

    monkeypatch.setattr("src.extraction.download.is_available", lambda: True)
    monkeypatch.setattr("src.extraction.download.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="total exceeds limit"):
        download_assets("https://instagram.com/p/ABC123/", tmp_path)


def test_download_assets_compresses_oversized_video(monkeypatch, tmp_path):
    media_file = tmp_path / "media_001.mp4"

    def fake_run(args, **kwargs):
        if args[0] == "ffmpeg":
            Path(args[-1]).write_bytes(b"12345")
            return _completed()
        if "--dump-single-json" in args:
            return _completed(json.dumps({"duration": 8}))
        media_file.write_bytes(b"123456")
        return _completed(str(media_file))

    monkeypatch.setattr("src.extraction.download.is_available", lambda: True)
    monkeypatch.setattr(
        "src.extraction.download.shutil.which",
        lambda name: f"/usr/bin/{name}" if name == "ffmpeg" else None,
    )
    monkeypatch.setattr("src.extraction.download.subprocess.run", fake_run)

    paths = download_assets("https://instagram.com/reel/ABC123/", tmp_path)

    assert paths == [tmp_path / "media_001.compressed.mp4"]
    assert paths[0].read_bytes() == b"12345"
    assert not media_file.exists()
