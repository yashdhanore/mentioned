from __future__ import annotations

import pytest

from src.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_rejects_media_duration_above_hard_cap(monkeypatch):
    monkeypatch.setenv("MAX_MEDIA_DURATION_SECONDS", "301")

    with pytest.raises(RuntimeError, match="MAX_MEDIA_DURATION_SECONDS"):
        get_settings()


def test_settings_rejects_gemini_attempts_above_hard_cap(monkeypatch):
    monkeypatch.setenv("GEMINI_TOTAL_ATTEMPTS", "4")

    with pytest.raises(RuntimeError, match="GEMINI_TOTAL_ATTEMPTS"):
        get_settings()
