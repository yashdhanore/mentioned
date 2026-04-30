from __future__ import annotations

from pathlib import Path

from app.config import Settings
from extractor.clients.openai_audio import AudioTranscriptionResult
from extractor.stages import transcribe_audio as transcribe_stage


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values = {
        "app_name": "Mentioned Backend",
        "database_url": "sqlite://",
        "data_dir": tmp_path,
        "worker_poll_interval_seconds": 0.0,
        "asr_provider": "openai",
        "ocr_provider": "tesseract",
        "multimodal_llm_provider": "none",
        "openai_api_key": "test",
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
        "max_image_long_edge_px": 1280,
        "llm_timeout_seconds": 60.0,
    }
    values.update(overrides)
    return Settings(**values)


def test_transcribe_audio_routes_to_openai_provider(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake wav")

    def fake_transcribe(path: Path, settings: Settings) -> AudioTranscriptionResult:
        assert path == audio_path
        assert settings.openai_asr_model == "gpt-4o-mini-transcribe"
        return AudioTranscriptionResult(
            text="A spoken book mention.",
            provider="openai",
            model=settings.openai_asr_model,
            response={"text": "A spoken book mention."},
        )

    monkeypatch.setattr(transcribe_stage, "transcribe_audio_with_openai", fake_transcribe)

    result = transcribe_stage.transcribe_audio(audio_path, _settings(tmp_path))

    assert result.text == "A spoken book mention."
    assert result.provider == "openai"
    assert result.model == "gpt-4o-mini-transcribe"
