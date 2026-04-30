from __future__ import annotations

from pathlib import Path
import subprocess


def extract_audio(media_path: Path, audio_path: Path) -> Path:
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(media_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return audio_path


def sample_frames(media_path: Path, frames_dir: Path, *, fps: int = 1, scale_factor: int = 2) -> list[Path]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = frames_dir / "frame_%03d.png"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(media_path),
            "-vf",
            f"fps={fps},scale=iw*{scale_factor}:ih*{scale_factor}",
            str(output_pattern),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(frames_dir.glob("frame_*.png"))
