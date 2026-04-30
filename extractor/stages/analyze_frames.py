from __future__ import annotations

from pathlib import Path
import re

from extractor.clients.tesseract import ocr_image


def _normalize_ocr_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def analyze_frames(frame_paths: list[Path]) -> tuple[list[dict], str]:
    entries: list[dict] = []
    lines: list[str] = []
    for frame_path in frame_paths:
        raw_text = ocr_image(frame_path)
        normalized_text = _normalize_ocr_text(raw_text)
        if normalized_text:
            lines.append(normalized_text)
        entries.append(
            {
                "frame": frame_path.name,
                "text": normalized_text,
                "has_text": bool(normalized_text),
            }
        )
    return entries, "\n".join(lines)
