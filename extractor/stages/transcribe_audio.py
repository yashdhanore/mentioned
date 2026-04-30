from __future__ import annotations

from pathlib import Path

from app.config import Settings
from extractor.clients.openai_audio import AudioTranscriptionResult, transcribe_audio_with_openai


def transcribe_audio(audio_path: Path, settings: Settings) -> AudioTranscriptionResult:
    if settings.asr_provider == "openai":
        return transcribe_audio_with_openai(audio_path, settings)
    raise ValueError(f"Unsupported ASR provider: {settings.asr_provider}")
