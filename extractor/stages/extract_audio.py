from __future__ import annotations

from pathlib import Path

from extractor.clients.ffmpeg import extract_audio as extract_audio_with_ffmpeg


def extract_audio(media_path: Path, audio_path: Path) -> Path:
    return extract_audio_with_ffmpeg(media_path, audio_path)
