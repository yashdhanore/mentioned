# Mentioned Backend

Validation scaffold for a backend that turns public Instagram Reel and post URLs into readable
text extracted from captions, media metadata, frames, and post images.

## Run the API

```bash
fastapi dev
```

Production schemas are managed with Alembic migrations:

```bash
alembic upgrade head
```

Local SQLite auto-creates tables only when `AUTO_CREATE_TABLES=true`; production should use
Postgres/Supabase with migrations applied before startup.

## Run the worker

```bash
python -m worker.run
```

In production, the API and worker must use separate database roles:

- `DATABASE_URL` is the FastAPI role and must be non-superuser and non-`BYPASSRLS`.
- `WORKER_DATABASE_URL` is the internal worker role and is required by `mentioned-worker` in
  production.

See [docs/beta-rls-option-b.md](docs/beta-rls-option-b.md) for the beta role setup and release
proof commands. For v1 beta, frontend clients may use Supabase Auth only; direct Supabase table
reads are forbidden.

## Run tests

```bash
python -m pytest
```

The Postgres dedicated-role RLS proof is skipped unless admin/setup, API-role, and worker-role URLs
are provided:

```bash
POSTGRES_TEST_DATABASE_URL=postgresql://admin-or-owner-url \
POSTGRES_TEST_API_DATABASE_URL=postgresql://mentioned_api-url \
POSTGRES_TEST_WORKER_DATABASE_URL=postgresql://mentioned_worker-url \
python -m pytest tests/test_postgres_dedicated_worker_rls.py
```

## Production release check

Before a beta deploy, validate the production environment shape without printing secrets:

```bash
python scripts/check_release_env.py --env-file .env --worker-replicas 1
```

For the full App Store/TestFlight backend gate, follow
[`docs/release-1-backend-readiness.md`](docs/release-1-backend-readiness.md).

Deploy exactly one worker replica for beta until worker claiming uses atomic `SKIP LOCKED`.

## Deploy to Render + Supabase

This repo includes a Dockerfile and `render.yaml` Blueprint for a Render web service plus a Render
background worker backed by Supabase Postgres/Auth. See
[`docs/render-supabase-deploy.md`](docs/render-supabase-deploy.md) for the production setup,
required environment variables, role setup, and mobile app configuration.

## Smoke test the saved-source flow

With the API and worker running, submit a real saved source, poll until terminal, verify extracted
items, and prove another user cannot read the saved source:

```bash
TOKEN='paste-supabase-access-token'
SECOND_TOKEN='paste-second-user-supabase-access-token'
SOURCE_URL='https://www.instagram.com/reel/SHORTCODE/'
python scripts/smoke_job_flow.py --require-items
```

Optional overrides:

```bash
python scripts/smoke_job_flow.py \
  --api-base-url http://127.0.0.1:8000 \
  --source-url "$SOURCE_URL" \
  --token "$TOKEN" \
  --timeout-seconds 600 \
  --require-items
```

## API

- `POST /v1/saved-sources` saves an Instagram Reel/post URL and queues canonical extraction when needed.
- `GET /v1/saved-sources` lists the authenticated user's saved sources.
- `GET /v1/saved-sources/{saved_source_id}` returns source extraction status and extracted items.
- `DELETE /v1/saved-sources/{saved_source_id}` unlinks that saved source for the authenticated user.

Current saved-source status values are `processing`, `done`, and `failed`.

Public endpoints use Supabase Auth in production (`AUTH_MODE=supabase`). Local development defaults
to `AUTH_MODE=dev`; omit `Authorization` to use `DEV_USER_ID`, or pass
`Authorization: Bearer dev:<uuid>` to simulate a different user.

Extraction uses `yt-dlp` to download Instagram media and Gemini to identify mentioned books,
products, and places. Configure `GEMINI_API_KEY` or Vertex AI settings before running the worker.

## Run the Landing Page

The consumer landing page lives in `web/` as a static Astro app. It is separate from the FastAPI API and the Expo mobile app.

```bash
cd web
npm install
npm run dev
```

Useful checks:

```bash
cd web
npm run verify:content
npm run typecheck
npm run build
npm run test:e2e
```

To capture local review screenshots, start the dev server in one terminal and run:

```bash
cd web
npm run capture:screens
```
