from __future__ import annotations

from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors

from src.config import get_settings
from src.extraction import gemini


def _api_error(code: int) -> genai_errors.APIError:
    return genai_errors.APIError(code, {"error": {"message": "boom"}})


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_get_client_delegates_to_shared_gemini_client(monkeypatch):
    # scripts/compare_gemini_video_models.py imports this zero-arg wrapper directly.
    sentinel = object()
    captured_settings = []

    def fake_get_gemini_client(settings):
        captured_settings.append(settings)
        return sentinel

    monkeypatch.setattr(gemini, "get_gemini_client", fake_get_gemini_client)

    client = gemini._get_client()

    assert client is sentinel
    assert captured_settings == [get_settings()]


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
    monkeypatch.setattr(gemini, "get_gemini_client", lambda _settings: client)
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


def test_extract_mentions_from_media_rejects_oversized_media_before_client(
    monkeypatch,
    tmp_path,
):
    media_file = tmp_path / "media_001.jpg"
    media_file.write_bytes(b"123456")
    monkeypatch.setenv("MAX_MEDIA_FILE_BYTES", "5")
    monkeypatch.setenv("MAX_MEDIA_TOTAL_BYTES", "10")
    monkeypatch.setattr(
        gemini,
        "get_gemini_client",
        lambda _settings: (_ for _ in ()).throw(AssertionError("client should not be created")),
    )

    with pytest.raises(RuntimeError, match="Media file exceeds limit"):
        gemini.extract_mentions_from_media(media_file)


def test_generate_with_retry_retries_retryable_error_then_succeeds(monkeypatch):
    monkeypatch.setattr(gemini.time, "sleep", lambda _seconds: None)
    calls = {"count": 0}

    class Models:
        def generate_content(self, **kwargs):
            calls["count"] += 1
            if calls["count"] < 3:
                raise _api_error(503)
            return SimpleNamespace(text='{"mentions": []}')

    client = SimpleNamespace(models=Models())

    response = gemini._generate_with_retry(
        client, model="m", contents=[], config=None, total_attempts=3
    )

    assert response.text == '{"mentions": []}'
    assert calls["count"] == 3


def test_generate_with_retry_raises_immediately_on_non_retryable_error(monkeypatch):
    def _fail_if_called(_seconds):
        raise AssertionError("should not sleep on a non-retryable error")

    monkeypatch.setattr(gemini.time, "sleep", _fail_if_called)
    calls = {"count": 0}

    class Models:
        def generate_content(self, **kwargs):
            calls["count"] += 1
            raise _api_error(400)

    client = SimpleNamespace(models=Models())

    with pytest.raises(genai_errors.APIError) as excinfo:
        gemini._generate_with_retry(client, model="m", contents=[], config=None, total_attempts=3)

    assert excinfo.value.code == 400
    assert calls["count"] == 1


def test_generate_with_retry_raises_after_exhausting_attempts(monkeypatch):
    monkeypatch.setattr(gemini.time, "sleep", lambda _seconds: None)
    calls = {"count": 0}

    class Models:
        def generate_content(self, **kwargs):
            calls["count"] += 1
            raise _api_error(503)

    client = SimpleNamespace(models=Models())

    with pytest.raises(genai_errors.APIError) as excinfo:
        gemini._generate_with_retry(client, model="m", contents=[], config=None, total_attempts=3)

    assert excinfo.value.code == 503
    assert calls["count"] == 3
