# AGENTS.md

## Cursor Cloud specific instructions

### Overview

This is a Python FastAPI backend ("Mentioned Backend") that extracts readable text from Instagram Reel/Post URLs. It consists of two processes: an API server and a background worker.

### Running Services

| Service | Command | Notes |
|---------|---------|-------|
| API Server | `fastapi dev` | Runs on http://127.0.0.1:8000, auto-reloads |
| Worker | `python3 -m worker.run` | Polls SQLite for queued jobs silently |

Both must run for end-to-end job processing. The worker produces no stdout output during normal polling.

### Testing

- `python3 -m pytest tests/ -v` — runs all unit tests (currently 6)
- `ruff check .` — lint (no config file; uses defaults)

### Key Gotchas

- **Editable install (`pip install -e .`) fails** due to multiple top-level packages (`app`, `worker`, `extractor`, `evals`) without explicit setuptools package discovery config. Install dependencies directly instead: `pip install "fastapi[standard]>=0.115.0" "httpx>=0.27.0" "openai>=2.31.0" "pillow>=10.0.0" "python-dotenv>=1.0.0" "sqlmodel>=0.0.22" "pytest>=8.0.0"`.
- **`python` is not on PATH** — use `python3` for all commands.
- **yt-dlp installs to `~/.local/bin`** — ensure `$HOME/.local/bin` is on PATH.
- **SQLite DB (`app.db`)** is auto-created on first API/worker start; no migrations needed.
- **Default config works without API keys** — `MULTIMODAL_LLM_PROVIDER=none` and `ASR_PROVIDER=none` are defaults; the pipeline runs locally with OCR only.
- **System dependencies required**: `ffmpeg`, `tesseract-ocr`, `yt-dlp` must be on PATH.
