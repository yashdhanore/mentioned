# Render + Supabase Deployment

This backend deploys as two Render services backed by one Supabase project:

- `mentioned-api`: public FastAPI web service on Render Free.
- `mentioned-worker`: private background worker on Render Starter that processes queued jobs.
- Supabase: Postgres, Supabase Auth, and the production user database.

For beta, keep the worker at exactly one instance until worker claiming uses atomic `SKIP LOCKED`.
This keeps Render compute to the worker cost only, currently about $7/month.

## 1. Create Supabase roles

In Supabase SQL editor, run the role setup from `docs/beta-rls-option-b.md` with strong passwords:

```sql
create role mentioned_api
  login
  password 'replace-with-strong-api-password'
  nosuperuser
  nobypassrls;

create role mentioned_worker
  login
  password 'replace-with-strong-worker-password'
  nosuperuser
  nobypassrls;
```

Use separate connection strings for the two roles:

- `DATABASE_URL`: connects as `mentioned_api`.
- `WORKER_DATABASE_URL`: connects as `mentioned_worker`.
- `MIGRATION_DATABASE_URL`: connects as a Supabase owner/admin role, used only by the Render worker
  predeploy command to run Alembic migrations.

Use Supabase Direct connection if your host supports IPv6, otherwise use Supabase Session Pooler.
Avoid Transaction Pooler for this app because SQLAlchemy keeps pooled connections and transaction
pooling does not support all session behavior.

For Supabase pooler URLs, the user name usually includes the project reference suffix, for example
`mentioned_api.<project-ref>` and `mentioned_worker.<project-ref>`.

## 2. Create the Render Blueprint

Use the root `render.yaml` file to create the Blueprint in Render. It defines:

- one Docker web service named `mentioned-api` on Render Free;
- one Docker background worker named `mentioned-worker` on Render Starter;
- Render region `frankfurt` for both services;
- `alembic upgrade head` as the worker predeploy migration command;
- `/health` as the API health check;
- one worker instance.

Render will prompt for `sync: false` environment variables. Set the runtime variables on both
services, and set `MIGRATION_DATABASE_URL` plus `SUPABASE_SERVICE_ROLE_KEY` on the worker service
only:

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
public `job-thumbnails` Supabase Storage bucket. Do not set it in the mobile app or expose it to
browser clients.

Optional worker media limits can be set on `mentioned-worker` if you need to tune extraction:

```text
MAX_MEDIA_FILE_BYTES=52428800
MAX_MEDIA_TOTAL_BYTES=104857600
MEDIA_DOWNLOAD_TIMEOUT_SECONDS=120
MEDIA_TRANSCODE_VIDEO_BITRATE=1100k
MEDIA_TRANSCODE_AUDIO_BITRATE=96k
```

Apply Supabase migrations before deploying the worker so the public thumbnail bucket exists:

```bash
supabase db push --dry-run
supabase db push
```

For Supabase projects using JWT Signing Keys, no `SUPABASE_JWT_SECRET` is needed. The API verifies
RS256/ES256 access tokens with Supabase's JWKS endpoint at
`https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json`. If a project still uses legacy
HS256 JWTs, set `SUPABASE_JWT_SECRET` manually on the API service.

The blueprint sets the required non-secret production flags:

```text
APP_ENV=production
AUTH_MODE=supabase
AUTO_CREATE_TABLES=false
DOCS_ENABLED=false
SOURCE_REQUIRE_HTTPS=true
WORKER_REPLICAS=1
SUPABASE_JWT_AUDIENCE=authenticated
```

If you rename the Render API service, update `TRUSTED_HOSTS` to match the actual Render hostname.

## 3. Verify release shape

Before shipping beta traffic, run the production release check against the same values used on
Render:

```bash
python scripts/check_release_env.py --env-file .env.production --worker-replicas 1
```

Then run the Postgres RLS proof with admin, API-role, and worker-role connection strings:

```bash
POSTGRES_TEST_DATABASE_URL=postgresql://admin-or-owner-url \
POSTGRES_TEST_API_DATABASE_URL=postgresql://mentioned_api-url \
POSTGRES_TEST_WORKER_DATABASE_URL=postgresql://mentioned_worker-url \
python -m pytest tests/test_postgres_dedicated_worker_rls.py
```

After Render deploys, run the full job smoke test:

```bash
TOKEN='user-a-access-token' \
SECOND_TOKEN='user-b-access-token' \
SOURCE_URL='https://www.instagram.com/reel/SHORTCODE/' \
python scripts/smoke_job_flow.py --api-base-url https://mentioned-api.onrender.com
```

## 4. Mobile app configuration

Native iOS and Android apps can use this backend. CORS is a browser concern, not a native mobile
HTTP concern, but the API still enforces Supabase bearer tokens in production.

Set the mobile build environment to:

```text
EXPO_PUBLIC_APP_ENV=production
EXPO_PUBLIC_API_BASE_URL=https://mentioned-api.onrender.com
EXPO_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable-or-anon-key>
```

Use a custom API domain if you add one to Render. Production mobile builds intentionally reject
local or non-HTTPS API URLs.
