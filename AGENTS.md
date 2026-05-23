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

## Database & Supabase Workflow

For any database schema, migration, seed, RLS, or Supabase configuration change, use the Supabase CLI directly instead of handing migration steps back to the user. Check commands with `supabase --help` and `supabase <group> --help` because CLI behavior changes. Create migration files with `supabase migration new <descriptive_name>` and keep them under `supabase/migrations/`. Apply and verify migrations yourself with the appropriate local command, such as `supabase migration up --local` or `supabase db reset`. For hosted targets, run `supabase db push --dry-run` first, then run `supabase db push` when the intended linked remote target is clear. End with the commands you ran and any errors. Do not stop at "run the migration" unless the CLI, Docker, or credentials are unavailable.

Prefer local/dev verification before touching a hosted project. Once migrations exist, do not make schema changes directly in the Supabase Dashboard or remote SQL editor; keep remote state synchronized through migration files and `supabase db push`.

Do not commit Supabase passwords, access tokens, service-role keys, `.env` files, local database URLs, or generated artifacts. It is fine to commit non-secret config such as `supabase/config.toml`, migration SQL, seed files, and `.env.example` placeholders. For local automation, use `supabase login` and `supabase link --project-ref <ref>` so the CLI can store credentials in the OS credential store when available. For noninteractive CI or agent runs, provide secrets through environment variables such as `SUPABASE_ACCESS_TOKEN` and `SUPABASE_DB_PASSWORD` from the host environment or secret manager.

## Coding Style & Naming Conventions

Use Python 3.11+ syntax, 4-space indentation, type hints, and small focused functions. Follow existing naming: `snake_case` for modules, functions, variables, and stage files; `PascalCase` for classes and Pydantic/SQLModel models. Keep pipeline stages in `extractor/stages/` narrow and named by action, such as `probe_media.py` or `transcribe_audio.py`. Prefer client wrappers in `extractor/clients/` when calling external binaries or services. No formatter or linter config is currently committed; match the style already present in the repository.

## Testing Guidelines

Tests use pytest and should live in `tests/test_*.py` with functions named `test_*`. Prefer `tmp_path` and `monkeypatch` for file, OCR, OpenAI, and subprocess behavior so tests stay deterministic and offline. For provider integrations, cover both the configured-provider path and the fallback path. Run `pytest` before submitting changes; run the visual manifest script when extraction output or artifact structure changes.

## Security & Configuration Tips

Copy `.env.example` to `.env` for local settings. Do not commit secrets, `.env` files, local databases, or generated artifacts. Defaults disable ASR and multimodal LLM calls; enable OpenAI locally with `OPENAI_API_KEY`, `MULTIMODAL_LLM_PROVIDER=openai`, and related model settings only when needed.

Keep environment variables reserved for secrets, deployment-specific endpoints, credentials, and values that truly differ by environment. Stable product defaults such as bucket names, file size limits, and timeouts should be code constants unless there is a concrete operational need to configure them per deployment.

## Commit & Pull Request Guidelines

The current history only establishes an initial commit, so use clear imperative commit messages, for example `Add visual extraction fallback tests`. Pull requests should include a concise summary, linked issue if available, commands run, and sample API responses or screenshots when behavior changes.
