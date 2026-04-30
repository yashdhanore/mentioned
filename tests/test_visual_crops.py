from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from app.config import Settings
from extractor.visual.crops import generate_visual_inputs


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
        "max_image_long_edge_px": 40,
        "llm_timeout_seconds": 60.0,
    }
    values.update(overrides)
    return Settings(**values)


def _make_split_image(path: Path, *, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Path:
    image = Image.new("RGB", (100, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 99, 99), fill=top)
    draw.rectangle((0, 100, 99, 199), fill=bottom)
    image.save(path)
    return path


def test_generate_visual_inputs_uses_stable_ids_bboxes_resizing_and_dedupe(tmp_path: Path) -> None:
    source_a = _make_split_image(tmp_path / "a.png", top=(255, 0, 0), bottom=(0, 0, 255))
    source_b = _make_split_image(tmp_path / "b.png", top=(255, 0, 0), bottom=(0, 0, 255))

    bundle = generate_visual_inputs(
        selected_frames=[source_a, source_b],
        selected_post_images=[],
        artifact_dir=tmp_path / "artifacts",
        settings=_settings(tmp_path),
    )

    assert [entry.id for entry in bundle.selected_images] == ["frame_001_full", "frame_002_full"]
    assert [entry.id for entry in bundle.crops] == ["frame_001_overlay", "frame_001_object"]
    assert bundle.crops[0].bbox_normalized == (0.0, 0.0, 1.0, 0.65)
    assert bundle.crops[1].bbox_normalized == (0.0, 0.5, 1.0, 0.5)
    assert bundle.crops[0].path.name == "frame_001_overlay.png"
    assert bundle.crops[1].path.name == "frame_001_object.png"

    for crop in bundle.crops:
        with Image.open(crop.path) as image:
            assert max(image.size) <= 40


def test_generate_visual_inputs_applies_llm_crop_limit(tmp_path: Path) -> None:
    source_a = _make_split_image(tmp_path / "a.png", top=(255, 0, 0), bottom=(0, 0, 255))
    source_b = _make_split_image(tmp_path / "b.png", top=(0, 255, 0), bottom=(255, 255, 0))

    bundle = generate_visual_inputs(
        selected_frames=[source_a, source_b],
        selected_post_images=[],
        artifact_dir=tmp_path / "artifacts",
        settings=_settings(tmp_path, max_llm_images=10, max_llm_crops=1),
    )

    llm_crop_ids = [entry.id for entry in bundle.llm_images if entry.role != "full"]
    assert llm_crop_ids == ["frame_001_overlay"]
    assert [entry.id for entry in bundle.llm_images if entry.role == "full"] == [
        "frame_001_full",
        "frame_002_full",
    ]
