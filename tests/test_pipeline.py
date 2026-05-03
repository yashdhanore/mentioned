from __future__ import annotations

from pathlib import Path

from app.config import Settings
from extractor import pipeline
from extractor.types import ExtractedMentionCandidate, StageOutcome
from extractor.visual.models import VisualExtractionResult


def test_llm_quota_skip_with_useful_text_yields_partial_pipeline_result(tmp_path: Path, monkeypatch) -> None:
    media_path = tmp_path / "media.mp4"
    frame_path = tmp_path / "frame.png"
    audio_path = tmp_path / "audio.wav"
    media_path.write_bytes(b"media")
    frame_path.write_bytes(b"frame")
    audio_path.write_bytes(b"audio")

    monkeypatch.setattr(pipeline, "get_settings", lambda: Settings(data_dir=tmp_path, asr_provider="none"))
    monkeypatch.setattr(pipeline, "fetch_html", lambda url: ("", {"status_code": 200}))
    monkeypatch.setattr(pipeline, "probe_media", lambda url: {"description": "caption"})
    monkeypatch.setattr(pipeline, "download_assets", lambda url, artifact_dir: [media_path])
    monkeypatch.setattr(pipeline, "extract_audio", lambda source, destination: audio_path)
    monkeypatch.setattr(pipeline, "sample_frames", lambda source, destination: [frame_path])
    monkeypatch.setattr(
        pipeline,
        "extract_visual_text",
        lambda **kwargs: VisualExtractionResult(
            visual_text=None,
            image_text=None,
            warnings=[],
            nonfatal_errors=["multimodal_llm_extract"],
            artifacts=[],
            stage_runs=[
                StageOutcome(
                    stage="multimodal_llm_extract",
                    success=True,
                    duration_ms=1,
                    payload={
                        "skipped": True,
                        "skip_reason": "llm_call_limit_exhausted",
                        "provider": "openai",
                    },
                )
            ],
            debug={},
        ),
    )

    result = pipeline.run_pipeline("job-llm-skip", "https://www.instagram.com/reel/test/")

    assert result.final_status == "partial"
    assert result.error_code is None
    assert "Caption:\ncaption" in result.text_result.merged_text
    assert "Visible text:" not in result.text_result.merged_text
    assert result.candidate_mentions == []
    assert result.text_result.debug["nonfatal_errors"] == ["multimodal_llm_extract"]


def test_noisy_ocr_text_does_not_create_candidate_mentions(tmp_path: Path, monkeypatch) -> None:
    media_path = tmp_path / "media.mp4"
    frame_path = tmp_path / "frame.png"
    audio_path = tmp_path / "audio.wav"
    media_path.write_bytes(b"media")
    frame_path.write_bytes(b"frame")
    audio_path.write_bytes(b"audio")

    monkeypatch.setattr(pipeline, "get_settings", lambda: Settings(data_dir=tmp_path, asr_provider="none"))
    monkeypatch.setattr(pipeline, "fetch_html", lambda url: ("", {"status_code": 200}))
    monkeypatch.setattr(pipeline, "probe_media", lambda url: {"description": ""})
    monkeypatch.setattr(pipeline, "download_assets", lambda url, artifact_dir: [media_path])
    monkeypatch.setattr(pipeline, "extract_audio", lambda source, destination: audio_path)
    monkeypatch.setattr(pipeline, "sample_frames", lambda source, destination: [frame_path])
    monkeypatch.setattr(
        pipeline,
        "extract_visual_text",
        lambda **kwargs: VisualExtractionResult(
            visual_text="SSS\nKY\nthe\nVisible text\nthat God",
            image_text=None,
            warnings=[],
            nonfatal_errors=[],
            artifacts=[],
            stage_runs=[],
            debug={},
            candidate_mentions=[],
        ),
    )

    result = pipeline.run_pipeline("job-noisy-ocr", "https://www.instagram.com/reel/test/")

    assert result.candidate_mentions == []


def test_openai_visual_candidates_are_pipeline_mentions(tmp_path: Path, monkeypatch) -> None:
    media_path = tmp_path / "media.mp4"
    frame_path = tmp_path / "frame.png"
    audio_path = tmp_path / "audio.wav"
    media_path.write_bytes(b"media")
    frame_path.write_bytes(b"frame")
    audio_path.write_bytes(b"audio")
    candidate = ExtractedMentionCandidate(
        label="The Visible Book",
        author_or_creator="A. Writer",
        category="book",
        confidence=0.91,
        evidence={"source": "openai"},
        evidence_text="The Visible Book - A. Writer",
    )

    monkeypatch.setattr(pipeline, "get_settings", lambda: Settings(data_dir=tmp_path, asr_provider="none"))
    monkeypatch.setattr(pipeline, "fetch_html", lambda url: ("", {"status_code": 200}))
    monkeypatch.setattr(pipeline, "probe_media", lambda url: {"description": ""})
    monkeypatch.setattr(pipeline, "download_assets", lambda url, artifact_dir: [media_path])
    monkeypatch.setattr(pipeline, "extract_audio", lambda source, destination: audio_path)
    monkeypatch.setattr(pipeline, "sample_frames", lambda source, destination: [frame_path])
    monkeypatch.setattr(
        pipeline,
        "extract_visual_text",
        lambda **kwargs: VisualExtractionResult(
            visual_text="The Visible Book - A. Writer",
            image_text=None,
            candidate_mentions=[candidate],
        ),
    )

    result = pipeline.run_pipeline("job-openai-candidate", "https://www.instagram.com/reel/test/")

    assert result.candidate_mentions == [candidate]
