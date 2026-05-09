# Render + Supabase Deployment

This backend deploys as two Render services backed by one Supabase project:

- `mentioned-api`: public FastAPI web service.
- `mentioned-worker`: private background worker that processes queued jobs.
- Supabase: Postgres, Supabase Auth, and the production user database.

For beta, keep the worker at exactly one instance until worker claiming uses atomic `SKIP LOCKED`.

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
- `MIGRATION_DATABASE_URL`: connects as a Supabase owner/admin role, used only by Render predeploy
  to run Alembic migrations.

Use Supabase Direct connection if your host supports IPv6, otherwise use Supabase Session Pooler.
Avoid Transaction Pooler for this app because SQLAlchemy keeps pooled connections and transaction
pooling does not support all session behavior.

For Supabase pooler URLs, the user name usually includes the project reference suffix, for example
`mentioned_api.<project-ref>` and `mentioned_worker.<project-ref>`.

## 2. Create the Render Blueprint

Use the root `render.yaml` file to create the Blueprint in Render. It defines:

- one Docker web service named `mentioned-api`;
- one Docker background worker named `mentioned-worker`;
- `alembic upgrade head` as the API predeploy migration command;
- `/health` as the API health check;
- one worker instance.

Render will prompt for `sync: false` environment variables. Set these on both services:

```text
DATABASE_URL=postgresql://mentioned_api.../postgres
WORKER_DATABASE_URL=postgresql://mentioned_worker.../postgres
MIGRATION_DATABASE_URL=postgresql://postgres.../postgres
SUPABASE_PROJECT_URL=https://<project-ref>.supabase.co
SUPABASE_JWT_SECRET=<Supabase JWT secret>
CORS_ALLOWED_ORIGINS=https://<your-web-origin>
TRUSTED_HOSTS=mentioned-api.onrender.com,<your-custom-api-domain>
GEMINI_API_KEY=<Gemini API key>
GOOGLE_BOOKS_API_KEY=<optional Google Books API key>
```

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
