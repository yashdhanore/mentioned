from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors

from src.config import Settings
from src.extraction.relevance import (
    RelevanceAssessment,
    Verdict,
    assess_relevance,
)


@pytest.fixture(autouse=True)
def gate_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.extraction.relevance.get_settings",
        lambda: Settings(),
    )


def _fake_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text)


def test_assess_relevance_parses_irrelevant_verdict(monkeypatch):
    def fake_generate(*, caption, thumbnail_bytes, thumbnail_mime):
        return _fake_response('{"verdict": "irrelevant", "reason": "dance clip"}')

    monkeypatch.setattr("src.extraction.relevance._call_gate_model", fake_generate)
    monkeypatch.setattr("src.extraction.relevance._fetch_thumbnail_bytes", lambda url: None)

    result = assess_relevance(caption="just vibing", thumbnail_url=None)

    assert isinstance(result, RelevanceAssessment)
    assert result.verdict is Verdict.IRRELEVANT
    assert result.reason == "dance clip"


def test_assess_relevance_parses_relevant_verdict(monkeypatch):
    def fake_generate(*, caption, thumbnail_bytes, thumbnail_mime):
        return _fake_response('{"verdict": "relevant", "reason": "book cover shown"}')

    monkeypatch.setattr("src.extraction.relevance._call_gate_model", fake_generate)
    monkeypatch.setattr("src.extraction.relevance._fetch_thumbnail_bytes", lambda url: None)

    result = assess_relevance(caption="top reads", thumbnail_url=None)

    assert result.verdict is Verdict.RELEVANT


def test_assess_relevance_fails_open_on_model_error(monkeypatch):
    def boom(*, caption, thumbnail_bytes, thumbnail_mime):
        raise RuntimeError("Gemini exploded")

    monkeypatch.setattr("src.extraction.relevance._call_gate_model", boom)
    monkeypatch.setattr("src.extraction.relevance._fetch_thumbnail_bytes", lambda url: None)

    result = assess_relevance(caption="anything", thumbnail_url=None)

    assert result.verdict is Verdict.UNCERTAIN


def test_assess_relevance_logs_error_when_gate_model_is_misconfigured(monkeypatch, caplog):
    # A retired or misspelled GEMINI_GATE_MODEL returns 404 on every call; failing open
    # hides that, so it must surface as an error rather than a routine warning.
    def retired_model(*, caption, thumbnail_bytes, thumbnail_mime):
        raise genai_errors.ClientError(404, {"error": {"message": "model retired"}})

    monkeypatch.setattr("src.extraction.relevance._call_gate_model", retired_model)
    monkeypatch.setattr("src.extraction.relevance._fetch_thumbnail_bytes", lambda url: None)

    with caplog.at_level(logging.WARNING, logger="src.extraction.relevance"):
        result = assess_relevance(caption="anything", thumbnail_url=None)

    assert result.verdict is Verdict.UNCERTAIN
    assert [record.levelno for record in caplog.records] == [logging.ERROR]


def test_assess_relevance_logs_warning_when_gate_is_rate_limited(monkeypatch, caplog):
    def rate_limited(*, caption, thumbnail_bytes, thumbnail_mime):
        raise genai_errors.ClientError(429, {"error": {"message": "slow down"}})

    monkeypatch.setattr("src.extraction.relevance._call_gate_model", rate_limited)
    monkeypatch.setattr("src.extraction.relevance._fetch_thumbnail_bytes", lambda url: None)

    with caplog.at_level(logging.WARNING, logger="src.extraction.relevance"):
        result = assess_relevance(caption="anything", thumbnail_url=None)

    assert result.verdict is Verdict.UNCERTAIN
    assert [record.levelno for record in caplog.records] == [logging.WARNING]


def test_assess_relevance_fails_open_on_unparseable_response(monkeypatch):
    def fake_generate(*, caption, thumbnail_bytes, thumbnail_mime):
        return _fake_response("not json at all")

    monkeypatch.setattr("src.extraction.relevance._call_gate_model", fake_generate)
    monkeypatch.setattr("src.extraction.relevance._fetch_thumbnail_bytes", lambda url: None)

    result = assess_relevance(caption="anything", thumbnail_url=None)

    assert result.verdict is Verdict.UNCERTAIN


def test_assess_relevance_fails_open_on_unknown_verdict(monkeypatch):
    def fake_generate(*, caption, thumbnail_bytes, thumbnail_mime):
        return _fake_response('{"verdict": "banana", "reason": "?"}')

    monkeypatch.setattr("src.extraction.relevance._call_gate_model", fake_generate)
    monkeypatch.setattr("src.extraction.relevance._fetch_thumbnail_bytes", lambda url: None)

    result = assess_relevance(caption="anything", thumbnail_url=None)

    assert result.verdict is Verdict.UNCERTAIN


def test_assess_relevance_passes_thumbnail_bytes_to_model(monkeypatch):
    seen = {}

    def fake_generate(*, caption, thumbnail_bytes, thumbnail_mime):
        seen["caption"] = caption
        seen["bytes"] = thumbnail_bytes
        seen["mime"] = thumbnail_mime
        return _fake_response('{"verdict": "relevant", "reason": "ok"}')

    monkeypatch.setattr("src.extraction.relevance._call_gate_model", fake_generate)
    monkeypatch.setattr(
        "src.extraction.relevance._fetch_thumbnail_bytes",
        lambda url: (b"imgdata", "image/jpeg"),
    )

    assess_relevance(caption="a caption", thumbnail_url="https://cdn/x.jpg")

    assert seen["caption"] == "a caption"
    assert seen["bytes"] == b"imgdata"
    assert seen["mime"] == "image/jpeg"
