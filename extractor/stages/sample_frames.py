from __future__ import annotations

from pathlib import Path

from extractor.clients.ffmpeg import sample_frames as sample_frames_with_ffmpeg


def sample_frames(media_path: Path, frames_dir: Path) -> list[Path]:
    return sample_frames_with_ffmpeg(media_path, frames_dir)
