from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from app.config import Settings
from extractor.visual import extraction as visual_extraction
from extractor.visual.models import (
    CandidateMention,
    OpenAIVisualResponse,
    VisibleTextBlock,
    VisualReconstruction,
)


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values = {
        "app_name": "Mentioned Backend",
        "database_url": "sqlite://",
        "data_dir": tmp_path,
        "worker_poll_interval_seconds": 0.0,
        "asr_provider": "none",
        "ocr_provider": "tesseract",
        "multimodal_llm_provider": "none",
        "openai_api_key": None,
        "openai_base_url": None,
        "openai_asr_model": "gpt-4o-mini-transcribe",
        "openai_asr_prompt": None,
        "max_asr_audio_bytes": 25 * 1024 * 1024,
        "openai_multimodal_model": "gpt-5.4-nano",
        "openai_reasoning_effort": "low",
        "openai_text_verbosity": "low",
        "openai_store_responses": False,
        "max_selected_frames": 8,
        "max_selected_post_images": 10,
        "max_llm_images": 20,
        "max_llm_crops": 12,
        "max_llm_calls_per_job": 1,
        "max_image_long_edge_px": 80,
        "llm_timeout_seconds": 60.0,
    }
    values.update(overrides)
    return Settings(**values)


def _make_image(path: Path) -> Path:
    image = Image.new("RGB", (120, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 119, 89), fill=(255, 255, 255))
    draw.rectangle((0, 90, 119, 179), fill=(200, 220, 255))
    image.save(path)
    return path


def test_provider_none_uses_ocr_without_partial_status_signal(tmp_path: Path, monkeypatch) -> None:
    source = _make_image(tmp_path / "frame.png")

    def fake_ocr(path: Path, *, psm: int = 11) -> str:
        if "overlay" in path.name:
            return "Overlay line\nInstagram"
        if "object" in path.name:
            return "Book title"
        return "Full-frame fallback"

    monkeypatch.setattr(visual_extraction, "ocr_image", fake_ocr)

    result = visual_extraction.extract_visual_text(
        job_id="job-1",
        artifact_dir=tmp_path / "artifacts",
        source_url="https://www.instagram.com/reel/test/",
        source_kind="instagram_reel",
        selected_frames=[source],
        selected_post_images=[],
        caption_text="caption",
        settings=_settings(tmp_path),
    )

    assert result.nonfatal_errors == []
    assert "Multimodal LLM provider is not configured" in " ".join(result.warnings)
    assert "Overlay line" in (result.visual_text or "")
    assert "Book title" in (result.visual_text or "")
    assert "Instagram" not in (result.visual_text or "")
    assert result.debug["ocr_openai_comparison"]["frame_text_source"] == "ocr"
    assert result.debug["ocr_openai_comparison"]["post_image_text_source"] == "none"


def test_openai_success_prefers_structured_text_and_artifacts_candidates(tmp_path: Path, monkeypatch) -> None:
    source = _make_image(tmp_path / "frame.png")
    monkeypatch.setattr(visual_extraction, "ocr_image", lambda path, *, psm=11: "OCR noise")

    def fake_openai(**kwargs) -> OpenAIVisualResponse:
        reconstruction = VisualReconstruction(
            schema_version="visual_reconstruction.v1",
            cleaned_frame_text="Clean frame text",
            cleaned_post_image_text="",
            confidence=0.86,
            visible_text_blocks=[
                VisibleTextBlock(
                    text="Clean frame text",
                    kind="overlay",
                    source_surface="frame",
                    source_image_ids=["frame_001_full"],
                    source_crop_ids=["frame_001_overlay"],
                    confidence=0.9,
                    include_in_merged_text=True,
                    ignored_reason=None,
                )
            ],
            candidate_mentions=[
                CandidateMention(
                    label="The Visible Book",
                    author_or_creator="A. Writer",
                    category="book",
                    evidence_basis="direct_visible_text",
                    creator_supplied_context=None,
                    visible_evidence="The Visible Book - A. Writer",
                    normalization_notes=None,
                    source_image_ids=["frame_001_full"],
                    source_crop_ids=["frame_001_object"],
                    confidence=0.91,
                )
            ],
            ignored_text_summary=None,
            uncertainty_notes=[],
        )
        return OpenAIVisualResponse(
            reconstruction=reconstruction,
            raw_response={"id": "resp_test", "output": []},
            usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        )

    monkeypatch.setattr(visual_extraction, "run_openai_visual_reconstruction", fake_openai)

    result = visual_extraction.extract_visual_text(
        job_id="job-2",
        artifact_dir=tmp_path / "artifacts",
        source_url="https://www.instagram.com/reel/test/",
        source_kind="instagram_reel",
        selected_frames=[source],
        selected_post_images=[],
        caption_text="caption",
        settings=_settings(tmp_path, multimodal_llm_provider="openai", openai_api_key="test"),
    )

    assert result.visual_text == "Clean frame text"
    assert result.nonfatal_errors == []
    assert result.debug["ocr_openai_comparison"]["frame_text_source"] == "openai"
    assert result.debug["candidate_mentions"][0]["label"] == "The Visible Book"
    assert {"llm_output", "llm_usage", "visual_reconstruction"}.issubset(
        {artifact.kind for artifact in result.artifacts}
    )


def test_openai_failure_falls_back_to_ocr_and_marks_nonfatal_error(tmp_path: Path, monkeypatch) -> None:
    source = _make_image(tmp_path / "frame.png")
    monkeypatch.setattr(visual_extraction, "ocr_image", lambda path, *, psm=11: "OCR fallback")

    def fake_openai(**kwargs) -> OpenAIVisualResponse:
        raise ValueError("bad schema")

    monkeypatch.setattr(visual_extraction, "run_openai_visual_reconstruction", fake_openai)

    result = visual_extraction.extract_visual_text(
        job_id="job-3",
        artifact_dir=tmp_path / "artifacts",
        source_url="https://www.instagram.com/reel/test/",
        source_kind="instagram_reel",
        selected_frames=[source],
        selected_post_images=[],
        caption_text="caption",
        settings=_settings(tmp_path, multimodal_llm_provider="openai", openai_api_key="test"),
    )

    assert result.visual_text == "OCR fallback"
    assert result.nonfatal_errors == ["multimodal_llm_extract"]
    assert "OpenAI visual reconstruction failed" in " ".join(result.warnings)
    assert result.debug["ocr_openai_comparison"]["frame_text_source"] == "ocr"
    llm_stage = next(stage for stage in result.stage_runs if stage.stage == "multimodal_llm_extract")
    assert llm_stage.success is False
    assert llm_stage.error_text == "bad schema"


def test_openai_is_skipped_when_llm_call_limit_is_zero(tmp_path: Path, monkeypatch) -> None:
    source = _make_image(tmp_path / "frame.png")
    monkeypatch.setattr(visual_extraction, "ocr_image", lambda path, *, psm=11: "OCR fallback")

    def fail_if_called(**kwargs) -> OpenAIVisualResponse:
        raise AssertionError("OpenAI visual reconstruction should not be invoked")

    monkeypatch.setattr(visual_extraction, "run_openai_visual_reconstruction", fail_if_called)

    result = visual_extraction.extract_visual_text(
        job_id="job-4",
        artifact_dir=tmp_path / "artifacts",
        source_url="https://www.instagram.com/reel/test/",
        source_kind="instagram_reel",
        selected_frames=[source],
        selected_post_images=[],
        caption_text="caption",
        settings=_settings(
            tmp_path,
            multimodal_llm_provider="openai",
            openai_api_key="test",
            max_llm_calls_per_job=0,
        ),
    )

    assert result.visual_text == "OCR fallback"
    assert result.nonfatal_errors == ["multimodal_llm_extract"]
    assert result.warnings == []
    assert "llm_output" not in {artifact.kind for artifact in result.artifacts}
    llm_stage = next(stage for stage in result.stage_runs if stage.stage == "multimodal_llm_extract")
    assert llm_stage.success is True
    assert llm_stage.payload == {
        "skipped": True,
        "skip_reason": "llm_call_limit_exhausted",
        "provider": "openai",
        "model": "gpt-5.4-nano",
        "selected_image_count": 3,
    }
