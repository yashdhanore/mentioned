from __future__ import annotations

from pathlib import Path

from scripts import compare_gemini_video_models
from src.extraction.download import DownloadedAssets

USAGE = {
    "prompt_token_count": 1000,
    "prompt_tokens_details": [
        {"modality": "VIDEO", "token_count": 800},
        {"modality": "AUDIO", "token_count": 200},
    ],
    "candidates_token_count": 50,
    "thoughts_token_count": 0,
    "total_token_count": 1050,
}


def test_compare_sources_downloads_once_and_runs_default_models(monkeypatch, tmp_path):
    download_calls = []
    model_calls = []

    def fake_download(source_url: str, output_dir: Path) -> DownloadedAssets:
        download_calls.append((source_url, output_dir))
        media_file = output_dir / "media_001.mp4"
        media_file.write_bytes(b"fake video")
        return DownloadedAssets(
            paths=[media_file],
            thumbnail_url="https://example.com/thumb.jpg",
            source_creator_handle="reader",
        )

    def fake_extract(paths: list[Path], *, model: str) -> dict:
        model_calls.append((model, [path.name for path in paths]))
        return {
            "raw": {
                "mentions": [
                    {
                        "title": f"Book from {model}",
                        "category": "book",
                        "confidence": 0.9,
                    }
                ]
            },
            "usage": USAGE,
        }

    monkeypatch.setattr(compare_gemini_video_models, "download_assets_with_metadata", fake_download)
    monkeypatch.setattr(compare_gemini_video_models, "_extract_mentions_for_model", fake_extract)

    payload = compare_gemini_video_models.compare_sources(
        ["https://www.instagram.com/reel/SHORTCODE/"],
        media_dir=tmp_path / "downloads",
    )

    [source] = payload["sources"]
    assert len(download_calls) == 1
    assert download_calls[0][1] == tmp_path / "downloads"
    assert source["download"]["media_dir_kept"] is True
    assert source["download"]["media_count"] == 1
    assert source["download"]["source_creator_handle"] == "reader"
    assert [result["model"] for result in source["results"]] == [
        "gemini-2.5-flash",
        "gemini-3.1-flash-lite",
    ]
    assert all(result["ok"] is True for result in source["results"])
    assert all(result["mention_count"] == 1 for result in source["results"])
    assert all(result["token_summary"]["prompt_tokens"] == 1000 for result in source["results"])
    assert all(result["estimated_cost"]["total_usd"] is not None for result in source["results"])
    assert {model for model, _paths in model_calls} == {
        "gemini-2.5-flash",
        "gemini-3.1-flash-lite",
    }
    assert all(paths == ["media_001.mp4"] for _model, paths in model_calls)


def test_compare_sources_keeps_result_order_for_custom_models(monkeypatch, tmp_path):
    def fake_download(source_url: str, output_dir: Path) -> DownloadedAssets:
        media_file = output_dir / "media_001.mp4"
        media_file.write_bytes(b"fake video")
        return DownloadedAssets(paths=[media_file])

    def fake_extract(paths: list[Path], *, model: str) -> dict:
        return {
            "raw": {"mentions": [{"title": model, "category": "book", "confidence": 0.8}]},
            "usage": USAGE,
        }

    monkeypatch.setattr(compare_gemini_video_models, "download_assets_with_metadata", fake_download)
    monkeypatch.setattr(compare_gemini_video_models, "_extract_mentions_for_model", fake_extract)

    payload = compare_gemini_video_models.compare_sources(
        ["https://www.instagram.com/reel/SHORTCODE/"],
        models=["model-b", "model-a"],
        media_dir=tmp_path / "downloads",
    )

    assert [result["model"] for result in payload["sources"][0]["results"]] == [
        "model-b",
        "model-a",
    ]


def test_compare_sources_summarizes_cost_by_model(monkeypatch, tmp_path):
    download_calls = []

    def fake_download(source_url: str, output_dir: Path) -> DownloadedAssets:
        download_calls.append((source_url, output_dir))
        media_file = output_dir / "media_001.mp4"
        media_file.write_bytes(b"fake video")
        return DownloadedAssets(paths=[media_file])

    def fake_extract(paths: list[Path], *, model: str) -> dict:
        return {
            "raw": {"mentions": [{"title": model, "category": "book", "confidence": 0.8}]},
            "usage": USAGE,
        }

    monkeypatch.setattr(compare_gemini_video_models, "download_assets_with_metadata", fake_download)
    monkeypatch.setattr(compare_gemini_video_models, "_extract_mentions_for_model", fake_extract)

    payload = compare_gemini_video_models.compare_sources(
        [
            "https://www.instagram.com/reel/ONE/",
            "https://www.instagram.com/reel/TWO/",
        ],
        media_dir=tmp_path / "downloads",
    )

    assert len(download_calls) == 2
    assert [call[1].name for call in download_calls] == ["source_001", "source_002"]
    assert payload["summary"]["source_count"] == 2
    assert payload["summary"]["estimated_total_cost_usd"] is not None
    assert [item["sources"] for item in payload["summary"]["models"]] == [2, 2]
    assert [item["successful_sources"] for item in payload["summary"]["models"]] == [2, 2]
    assert [item["mentions"] for item in payload["summary"]["models"]] == [2, 2]


def test_compare_sources_reuses_media_only_for_the_same_source(monkeypatch, tmp_path):
    download_calls = []

    def fake_download(source_url: str, output_dir: Path) -> DownloadedAssets:
        download_calls.append(source_url)
        media_file = output_dir / "media_001.mp4"
        media_file.write_bytes(source_url.encode())
        return DownloadedAssets(paths=[media_file], source_creator_handle="reader")

    extracted_media = []

    def fake_extract(paths: list[Path], *, model: str) -> dict:
        extracted_media.append(paths[0].read_bytes().decode())
        return {"raw": {"mentions": []}, "usage": USAGE}

    monkeypatch.setattr(compare_gemini_video_models, "download_assets_with_metadata", fake_download)
    monkeypatch.setattr(compare_gemini_video_models, "_extract_mentions_for_model", fake_extract)
    media_dir = tmp_path / "downloads"
    one = "https://www.instagram.com/reel/ONE/"
    two = "https://www.instagram.com/reel/TWO/"
    three = "https://www.instagram.com/reel/THREE/"

    compare_gemini_video_models.compare_sources([one, two], models=["m"], media_dir=media_dir)
    download_calls.clear()
    extracted_media.clear()
    # source_002 now belongs to a different URL, so it must not be reused for THREE.
    payload = compare_gemini_video_models.compare_sources(
        [one, three], models=["m"], media_dir=media_dir, reuse_media=True
    )

    assert download_calls == [three]
    assert extracted_media == [one, three]
    assert [source["download"]["media_reused"] for source in payload["sources"]] == [True, False]
    assert payload["sources"][0]["download"]["source_creator_handle"] == "reader"


def test_source_urls_from_text_extracts_only_urls():
    text = """
    # Saved Reels

    - https://www.instagram.com/reel/ONE/?igsh=abc==
    - [https://www.instagram.com/reel/TWO/](https://www.instagram.com/reel/TWO/)
    plain text should be ignored
    """

    assert compare_gemini_video_models._source_urls_from_text(text) == [
        "https://www.instagram.com/reel/ONE/?igsh=abc==",
        "https://www.instagram.com/reel/TWO/",
    ]
