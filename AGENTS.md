# Repository Guidelines

## Project Structure & Module Organization

`app/` contains the FastAPI application: routers, schemas, SQLModel models, config, database setup, and job services. `extractor/` contains the extraction pipeline, with individual stages in `extractor/stages/`, external tool wrappers in `extractor/clients/`, and OCR/LLM visual logic in `extractor/visual/`. `worker/` runs queued extraction jobs. `tests/` contains pytest coverage, `evals/` stores visual regression manifests, and `scripts/` holds utility commands. Runtime outputs such as `app.db` and `data/artifacts/` are generated locally and should not be committed.

## Build, Test, and Development Commands

Create an environment and install the project with dev dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the API locally with `fastapi dev`. Run the worker with `python -m worker.run` or, after installation, `mentioned-worker`. Run tests with `pytest`. Evaluate saved visual extraction outputs with:

```bash
python scripts/evaluate_visual_manifest.py --artifacts-dir data/artifacts
```

Media extraction paths may require local `ffmpeg`, `yt-dlp`, and `tesseract` installations.

## Coding Style & Naming Conventions

Use Python 3.11+ syntax, 4-space indentation, type hints, and small focused functions. Follow existing naming: `snake_case` for modules, functions, variables, and stage files; `PascalCase` for classes and Pydantic/SQLModel models. Keep pipeline stages in `extractor/stages/` narrow and named by action, such as `probe_media.py` or `transcribe_audio.py`. Prefer client wrappers in `extractor/clients/` when calling external binaries or services. No formatter or linter config is currently committed; match the style already present in the repository.

## Testing Guidelines

Tests use pytest and should live in `tests/test_*.py` with functions named `test_*`. Prefer `tmp_path` and `monkeypatch` for file, OCR, OpenAI, and subprocess behavior so tests stay deterministic and offline. For provider integrations, cover both the configured-provider path and the fallback path. Run `pytest` before submitting changes; run the visual manifest script when extraction output or artifact structure changes.

## Security & Configuration Tips

Copy `.env.example` to `.env` for local settings. Do not commit secrets, `.env` files, local databases, or generated artifacts. Defaults disable ASR and multimodal LLM calls; enable OpenAI locally with `OPENAI_API_KEY`, `MULTIMODAL_LLM_PROVIDER=openai`, and related model settings only when needed.

## Commit & Pull Request Guidelines

The current history only establishes an initial commit, so use clear imperative commit messages, for example `Add visual extraction fallback tests`. Pull requests should include a concise summary, linked issue if available, commands run, and sample API responses or screenshots when behavior changes.
