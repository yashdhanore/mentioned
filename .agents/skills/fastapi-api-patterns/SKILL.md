---
name: fastapi-api-patterns
description: Use when adding or changing FastAPI endpoints, routers, schemas, dependencies, auth behavior, SQLModel models, services, or endpoint tests in this repo.
---

# FastAPI API Patterns

Use this skill for repo-specific FastAPI work. For general FastAPI conventions,
prefer the local FastAPI plugin skill (`FastAPI:fastapi` / `@fastapi`) and then
apply this repo's patterns below.

## First Reads

Read only the relevant feature area:

- App registration: `src/main.py`
- Database/session setup: `src/database.py`
- Config: `src/config.py`
- Auth: `src/auth/`
- Jobs API: `src/jobs/router.py`, `src/jobs/schemas.py`, `src/jobs/service.py`
- Mentions API: `src/mentions/router.py`, `src/mentions/schemas.py`, `src/mentions/service.py`
- Push API: `src/push/router.py`, `src/push/schemas.py`, `src/push/service.py`
- Tests: matching folder under `tests/`

## Endpoint Workflow

1. Start from the public contract: method, path, auth mode, status code, request
   schema, response schema, and error shape.
2. Follow existing module boundaries:
   - `router.py` handles HTTP boundary and dependency injection.
   - `schemas.py` owns request/response shapes.
   - `service.py` owns business logic.
   - `models.py` owns SQLModel/database shapes.
   - `dependencies.py` owns feature-local dependencies.
   - `exceptions.py` owns typed domain errors where present.
3. Keep dev auth and Supabase auth behavior explicit. Do not weaken production auth
   to simplify local testing.
4. If schema, migration, RLS, seed, or Supabase config changes are needed, follow
   `AGENTS.md` and use the Supabase CLI directly.
5. Add or update tests at the API boundary and the service boundary when behavior
   crosses both.

## FastAPI Conventions

- Prefer typed request and response schemas.
- Prefer explicit dependencies over hidden globals.
- Keep response payloads stable for the mobile app.
- Do not leak internal fields, stack traces, secrets, or database details.
- Keep routes thin; push behavior into services.

## Validation

Use targeted tests first, then broader tests:

```bash
python -m pytest tests/jobs
python -m pytest tests/mentions
python -m pytest tests/auth
python -m pytest tests
```

Pick the smallest set that covers the change.
