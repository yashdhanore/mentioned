# Mentioned Backend

Validation scaffold for a backend that turns public Instagram Reel and post URLs into readable
text extracted from captions, media metadata, frames, and post images.

## Local development (full stack)

Run the API, worker, web app, and mobile app together against a local Postgres, so the real
queue-based extraction pipeline runs the same way it does in production:

```bash
make dev       # starts everything
make dev-logs  # tail all logs together
make dev-down  # stops everything; local DB state is kept for next time
```

First run bootstraps a local Postgres via the Supabase CLI (`supabase start`), creates the
`mentioned_api`/`mentioned_worker` roles, and applies all Alembic and Supabase-managed migrations
automatically. Requires Docker and the Supabase CLI (`brew install supabase/tap/supabase`).

For the API and worker to actually use that Postgres instead of the SQLite default, add to your
`.env`:

```
DATABASE_URL=postgresql://mentioned_api:local-dev-api-pw@127.0.0.1:54322/postgres
WORKER_DATABASE_URL=postgresql://mentioned_worker:local-dev-worker-pw@127.0.0.1:54322/postgres
```

Without this, the API still boots fine on SQLite, but saved sources will get stuck at `pending`
forever: the source-extraction queue only works on Postgres (`pgmq`), so on SQLite
`enqueue_source_extraction` (`src/sources/queue.py`) is a silent no-op.

You'll also need a `GEMINI_API_KEY` (extraction fails without one — `EXTRACTION_BACKEND=local` is
a stub that always returns zero mentions, not a working offline alternative), and `ffmpeg`
installed for video transcoding. A `GOOGLE_BOOKS_API_KEY` is optional but recommended: without it,
book cover/metadata lookups are unauthenticated and get rate-limited almost immediately.

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
mentioned-worker
```

or equivalently `python -m src.worker`.

In production, the API and worker must use separate, non-superuser, non-`BYPASSRLS` database
roles (`DATABASE_URL` for the API, `WORKER_DATABASE_URL` for `mentioned-worker`); see
[role setup](#create-supabase-roles) below. For v1 beta, frontend clients may use Supabase Auth
only; direct Supabase table reads are forbidden.

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

The same env check, role checks, and smoke test below are the App Store/TestFlight backend release
gate.

Deploy exactly one worker replica for beta until worker claiming uses atomic `SKIP LOCKED`.

## Deploy to Render + Supabase

This repo includes a Dockerfile and `render.yaml` Blueprint for two Render services backed by one
Supabase project:

- `mentioned-api`: public FastAPI web service on Render Free.
- `mentioned-worker`: private background worker on Render Starter that processes queued jobs.
- Supabase: Postgres, Supabase Auth, and the production user database.

Keep the worker at exactly one instance until worker claiming uses atomic `SKIP LOCKED`; this keeps
Render compute to the worker cost only (about $7/month).

### Create Supabase roles

Run role setup and verification from a secure local shell with a database admin connection (not
the application/migration role), keeping any role-password SQL out of the repository:

```sql
create role mentioned_api login password 'replace-with-strong-api-password' nosuperuser nobypassrls;
create role mentioned_worker login password 'replace-with-strong-worker-password' nosuperuser nobypassrls;
```

Create these roles before running `alembic upgrade head`; Alembic manages the table grants and RLS
policies for `jobs` and `mentions`. Verify each role with the exact connection string planned for
that service:

```sql
select current_user, rolsuper, rolbypassrls from pg_roles where rolname = current_user;
```

Both `rolsuper` and `rolbypassrls` must be `false`. The API startup check rejects `DATABASE_URL` if
the connected role is a superuser or has `BYPASSRLS`; the worker refuses to start in production
unless `WORKER_DATABASE_URL` is set to an equally restricted role. Use three separate connection
strings:

- `DATABASE_URL`: connects as `mentioned_api` (used by the API).
- `WORKER_DATABASE_URL`: connects as `mentioned_worker` (used by `mentioned-worker`).
- `MIGRATION_DATABASE_URL`: connects as a Supabase owner/admin role, used only by the Render worker
  predeploy command to run Alembic migrations.

Use the Supabase Direct connection if your host supports IPv6, otherwise the Session Pooler; avoid
the Transaction Pooler because SQLAlchemy keeps pooled connections and transaction pooling does not
support all session behavior. For pooler URLs the username usually includes the project ref suffix,
e.g. `mentioned_api.<project-ref>`.

### Render Blueprint

The root `render.yaml` defines one Docker web service (`mentioned-api`, Render Free), one Docker
background worker (`mentioned-worker`, Render Starter), region `frankfurt` for both, `/health` as
the API health check, `alembic upgrade head` as the worker predeploy migration command, and one
worker instance.

Render prompts for `sync: false` environment variables. Set runtime variables on both services, and
set `MIGRATION_DATABASE_URL` plus `SUPABASE_SERVICE_ROLE_KEY` on the worker only:

```text
DATABASE_URL=postgresql://mentioned_api.../postgres
WORKER_DATABASE_URL=postgresql://mentioned_worker.../postgres
MIGRATION_DATABASE_URL=postgresql://postgres.../postgres
SUPABASE_PROJECT_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<worker-only-service-role-key>
CORS_ALLOWED_ORIGINS=https://<your-web-origin>,http://localhost:8082,http://127.0.0.1:8082
TRUSTED_HOSTS=mentioned-api.onrender.com,<your-custom-api-domain>
GEMINI_API_KEY=<Gemini API key>
GOOGLE_BOOKS_API_KEY=<optional Google Books API key>
```

`SUPABASE_SERVICE_ROLE_KEY` is used only by the worker to copy public Reel thumbnails into the
public `job-thumbnails` Supabase Storage bucket; never set it in the mobile app or expose it to
browser clients. The blueprint sets the required non-secret production flags (`APP_ENV=production`,
`AUTH_MODE=supabase`, `AUTO_CREATE_TABLES=false`, `DOCS_ENABLED=false`,
`SOURCE_REQUIRE_HTTPS=true`, `WORKER_REPLICAS=1`, `SUPABASE_JWT_AUDIENCE=authenticated`). For
Supabase projects using JWT Signing Keys, no `SUPABASE_JWT_SECRET` is needed; the API verifies
RS256/ES256 access tokens against Supabase's JWKS endpoint. If you rename the Render API service,
update `TRUSTED_HOSTS` to match the actual Render hostname.

Apply Supabase migrations (`supabase db push --dry-run` then `supabase db push`) before deploying
the worker so the public thumbnail bucket exists.

### Verify release shape

```bash
python scripts/check_release_env.py --env-file .env.production --worker-replicas 1
POSTGRES_TEST_DATABASE_URL=postgresql://admin-or-owner-url \
POSTGRES_TEST_API_DATABASE_URL=postgresql://mentioned_api-url \
POSTGRES_TEST_WORKER_DATABASE_URL=postgresql://mentioned_worker-url \
python -m pytest tests/test_postgres_dedicated_worker_rls.py
```

Then, after Render deploys, run the smoke test flow below against the deployed API. In Render,
inspect deploy status, runtime logs, health checks, and recent deploy/error events to confirm both
services deployed from the intended commit, the health check passed, the worker has one instance,
migrations ran through the worker predeploy, and worker logs show queue claim, retry/failure, and
archive paths clearly.

### Mobile app configuration

Native iOS and Android apps can use this backend; CORS is a browser concern, not a native mobile
HTTP concern, but the API still enforces Supabase bearer tokens in production. Set the mobile build
environment to:

```text
EXPO_PUBLIC_APP_ENV=production
EXPO_PUBLIC_API_BASE_URL=https://mentioned-api.onrender.com
EXPO_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable-or-anon-key>
```

Production mobile builds intentionally reject local or non-HTTPS API URLs.

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
