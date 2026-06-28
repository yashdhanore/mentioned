# Extraction Agent Guide

`src/extraction/` contains the extraction pipeline, provider clients, URL and download helpers, media handling, and extraction schemas.

## Implementation Notes

- Keep modules narrow and named by action or provider, such as `download.py`, `pipeline.py`, or provider-specific modules.
- Prefer deterministic fallback behavior when provider calls, OCR, ASR, downloads, or metadata lookups fail.
- `relevance.py` is a cheap caption+thumbnail gate that runs in `pipeline.py` before the expensive Gemini video call. It fails open: only a confident `irrelevant` verdict skips extraction, and it skips only when `RELEVANCE_GATE_MODE=active`. See the dated note in `docs/strategy/technical.md`.
- Wrap external binaries and network providers behind small functions so tests can monkeypatch them.
- Keep artifact structure stable; if extraction output or saved artifacts change, run the visual manifest evaluator.

## Checks

- Run targeted extraction tests with `pytest tests/extraction`.
- Evaluate saved visual extraction outputs with `python scripts/evaluate_visual_manifest.py --artifacts-dir data/artifacts` when artifact shape or visual extraction output changes.
- Compare Gemini video extraction models on one or more sources with `python scripts/compare_gemini_video_models.py <instagram-url> [...]`.
- Media extraction paths may require local `ffmpeg`, `yt-dlp`, and `tesseract`.
- Update this guide when extraction commands, artifact shape, provider behavior, or required local tools change.
