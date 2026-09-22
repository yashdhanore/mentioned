# Extraction Agent Guide

`src/extraction/` contains the extraction pipeline, provider clients, URL and download helpers, media handling, and extraction schemas.

## Implementation Notes

- Keep modules narrow and named by action or provider, such as `download.py`, `pipeline.py`, or provider-specific modules.
- Prefer deterministic fallback behavior when provider calls, downloads, or metadata lookups fail.
- `relevance.py` is a cheap caption+thumbnail gate that runs in `pipeline.py` before the expensive Gemini video call. It fails open: only a confident `irrelevant` verdict skips extraction, and it skips only when `RELEVANCE_GATE_MODE=active`. See the dated note in `docs/strategy/technical.md`.
- Wrap external binaries and network providers behind small functions so tests can monkeypatch them.
- `gemini.py` and `relevance.py` both build their Gemini client through `get_gemini_client()` in `gemini_client.py`; it applies the configurable `GEMINI_TIMEOUT_SECONDS` HTTP timeout (hard ceiling in `src/config.py`) so one hung call cannot stall the worker forever. `gemini.py` keeps a thin `_get_client()` wrapper only because `scripts/compare_gemini_video_models.py` imports it directly.
- When the extraction prompt, schema, or model changes, run a comparison and score it against the labeled Reels in `evals/reel-labels.json` (see `evals/README.md`).

## Checks

- Run targeted extraction tests with `pytest tests/extraction`.
- Score a comparison run against labels with `python scripts/score_extraction_eval.py --results outputs/<run>/result.json`; run it without `--results` to validate labels and see coverage.
- Compare Gemini video extraction models on one or more sources with `python scripts/compare_gemini_video_models.py <instagram-url> [...]`.
- Media extraction paths may require local `ffmpeg` and `yt-dlp`.
- Update this guide when extraction commands, artifact shape, provider behavior, or required local tools change.
