from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.config import get_settings
from src.extraction import gemini


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@patch("src.extraction.gemini.genai.Client")
def test_get_client_uses_vertexai_config(mock_client, monkeypatch):
    monkeypatch.setenv("GEMINI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GEMINI_VERTEX_PROJECT", "mentioned-test")
    monkeypatch.setenv("GEMINI_VERTEX_LOCATION", "europe-west4")

    gemini._get_client()

    kwargs = mock_client.call_args.kwargs
    assert kwargs["vertexai"] is True
    assert kwargs["project"] == "mentioned-test"
    assert kwargs["location"] == "europe-west4"
    assert kwargs["http_options"].api_version == "v1"
    assert "api_key" not in kwargs


def test_upload_to_gemini_uses_vertex_inline_limit(monkeypatch, tmp_path):
    media_file = tmp_path / "media_001.mp4"
    media_file.write_bytes(b"fake video")
    monkeypatch.setattr(gemini, "INLINE_SIZE_LIMIT", 1)
    monkeypatch.setattr(gemini, "VERTEX_INLINE_SIZE_LIMIT", 20)

    class Files:
        def upload(self, **kwargs):
            raise AssertionError("Vertex mode should not use Gemini File API upload")

    class Client:
        files = Files()

    part = gemini.upload_to_gemini(Client(), media_file, use_vertexai=True)

    assert part.inline_data is not None
    assert part.inline_data.mime_type == "video/mp4"
    assert part.inline_data.data == b"fake video"


def test_upload_to_gemini_rejects_oversized_vertex_local_media(monkeypatch, tmp_path):
    media_file = tmp_path / "media_001.mp4"
    media_file.write_bytes(b"fake video")
    monkeypatch.setattr(gemini, "VERTEX_INLINE_SIZE_LIMIT", 1)

    with pytest.raises(RuntimeError, match="Google Cloud Storage"):
        gemini.upload_to_gemini(object(), media_file, use_vertexai=True)


def test_extract_mentions_from_media_sends_all_media_parts(monkeypatch, tmp_path):
    first_media_file = tmp_path / "media_001.jpg"
    second_media_file = tmp_path / "media_002.jpg"
    first_media_file.write_bytes(b"fake image 1")
    second_media_file.write_bytes(b"fake image 2")
    captured = {}

    class Models:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text='{"mentions": []}')

    client = SimpleNamespace(models=Models())
    monkeypatch.setattr(gemini, "_get_client", lambda: client)
    monkeypatch.setattr(
        gemini,
        "upload_to_gemini",
        lambda _client, media_path, *, use_vertexai: f"part:{media_path.name}",
    )

    result = gemini.extract_mentions_from_media([first_media_file, second_media_file])

    assert result == {"mentions": []}
    assert captured["contents"] == [
        "part:media_001.jpg",
        "part:media_002.jpg",
        gemini.EXTRACTION_PROMPT,
    ]
