from __future__ import annotations

from unittest.mock import patch

import pytest

from src.config import GeminiConfig, Settings, get_settings
from src.extraction.gemini_client import get_gemini_client


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _settings(**gemini_overrides) -> Settings:
    return Settings(gemini=GeminiConfig(**gemini_overrides))


@patch("src.extraction.gemini_client.genai.Client")
def test_get_gemini_client_uses_vertexai_config(mock_client):
    settings = _settings(
        use_vertexai=True,
        vertex_project="mentioned-test",
        vertex_location="europe-west4",
        gemini_timeout_seconds=45,
    )

    get_gemini_client(settings)

    kwargs = mock_client.call_args.kwargs
    assert kwargs["vertexai"] is True
    assert kwargs["project"] == "mentioned-test"
    assert kwargs["location"] == "europe-west4"
    assert kwargs["http_options"].api_version == "v1"
    assert kwargs["http_options"].retry_options.attempts == 1
    assert kwargs["http_options"].timeout == 45_000
    assert "api_key" not in kwargs


def test_get_gemini_client_requires_vertex_project():
    settings = _settings(use_vertexai=True, vertex_project=None)

    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
        get_gemini_client(settings)


@patch("src.extraction.gemini_client.genai.Client")
def test_get_gemini_client_uses_api_key_config(mock_client):
    settings = _settings(gemini_api_key="secret-key", gemini_timeout_seconds=90)

    get_gemini_client(settings)

    kwargs = mock_client.call_args.kwargs
    assert kwargs["api_key"] == "secret-key"
    assert kwargs["http_options"].retry_options.attempts == 1
    assert kwargs["http_options"].timeout == 90_000
    assert "vertexai" not in kwargs


def test_get_gemini_client_requires_api_key():
    settings = _settings(gemini_api_key=None)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        get_gemini_client(settings)
