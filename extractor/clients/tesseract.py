from __future__ import annotations

from pathlib import Path
import subprocess


def ocr_image(image_path: Path, *, psm: int = 11) -> str:
    completed = subprocess.run(
        [
            "tesseract",
            str(image_path),
            "stdout",
            "--psm",
            str(psm),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
