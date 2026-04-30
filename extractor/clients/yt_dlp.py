from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess


def is_available() -> bool:
    return shutil.which("yt-dlp") is not None


def probe_url(url: str) -> dict:
    if not is_available():
        raise FileNotFoundError("yt-dlp is not installed")
    completed = subprocess.run(
        ["yt-dlp", "--dump-single-json", "--skip-download", url],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def download_assets(url: str, output_dir: Path) -> list[Path]:
    if not is_available():
        raise FileNotFoundError("yt-dlp is not installed")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = output_dir / "media_%(autonumber)03d.%(ext)s"
    completed = subprocess.run(
        [
            "yt-dlp",
            "--no-progress",
            "--print",
            "after_move:filepath",
            "-o",
            str(output_template),
            url,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not output_lines:
        raise RuntimeError("yt-dlp did not report any output paths")
    return [Path(line) for line in output_lines]


def download_media(url: str, output_dir: Path) -> Path:
    return download_assets(url, output_dir)[-1]
