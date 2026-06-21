# Backend Agent Guide

`src/` contains the FastAPI backend, worker, SQLModel data access, job queues, auth, mentions, books, push notifications, storage helpers, waitlist endpoints, and extraction integration points.

## Commands

- Run the API from the repo root with `fastapi dev`.
- Run the worker with `mentioned-worker` or `python -m src.worker`.
- Run backend tests with `pytest`; narrow with a path such as `pytest tests/jobs`.

## Backend Patterns

- Use Python 3.11+ syntax, 4-space indentation, type hints, and small focused functions.
- Keep feature modules organized around routers, schemas, models, dependencies, and services.
- Prefer structured helpers around external services or binaries so tests can monkeypatch them cleanly.
- Keep stable product defaults in code constants unless they truly differ by environment; reserve environment variables for secrets, credentials, endpoints, and deployment-specific values.
- Do not commit local databases, generated artifacts, or values from `.env`.

## Deployment Troubleshooting

- For hosted backend failures, use the Render plugin to inspect deploy status, runtime logs, health checks, service configuration, and recent deploy/error events before changing code.
- Summarize the Render evidence used, then connect it to any local code or configuration change.
