# Backend Agent Guide

`src/` contains the FastAPI backend, worker, SQLModel data access, saved-source queues, auth, books, places, push notifications, storage helpers, waitlist endpoints, and extraction integration points.
The live contract is `sources` / `source_items` / `saved_sources` (`src/sources/`); the legacy `jobs`/`mentions` compatibility surface was removed on 2026-09-21 (see the dated note in `docs/strategy/technical.md`).
Saved source ingestion behavior lives under `src/ingestion/`; keep `src/worker.py` focused on process wiring.
Saved-source response assembly lives in `src/sources/read_models.py`; keep routers focused on HTTP/auth/quota adapters.
Book enrichment behavior lives under `src/books/`; keep provider-specific fetch/parsing out of ingestion callers.
Shared HTTP error types live in `src/errors.py` (`AppError`); domain modules subclass it and `src/main.py` registers one exception handler for the whole hierarchy.

## Commands

- Run the API from the repo root with `fastapi dev`.
- Run the worker with `mentioned-worker` or `python -m src.worker`.
- Run backend tests with `pytest`; narrow with a path such as `pytest tests/sources`.

## Backend Patterns

- Use Python 3.11+ syntax, 4-space indentation, type hints, and small focused functions.
- Keep feature modules organized around routers, schemas, models, dependencies, and services.
- Prefer structured helpers around external services or binaries so tests can monkeypatch them cleanly.
- Keep stable product defaults in code constants unless they truly differ by environment; reserve environment variables for secrets, credentials, endpoints, and deployment-specific values.
- Do not commit local databases, generated artifacts, or values from `.env`.

## Deployment Troubleshooting

- For hosted backend failures, use the Render plugin to inspect deploy status, runtime logs, health checks, service configuration, and recent deploy/error events before changing code.
- Summarize the Render evidence used, then connect it to any local code or configuration change.
- Update this guide when backend commands, entrypoints, module boundaries, environment policy, or deployment troubleshooting workflow changes.
