# Render + Supabase Deployment

This zero-cost Render Blueprint deploys one free Render service backed by one Supabase project:

- `mentioned-api`: public FastAPI web service.
- Supabase: Postgres, Supabase Auth, and the production user database.

This keeps Render compute at $0, but it does not run the extraction worker on Render. Jobs can be
created and listed, but they remain pending until `mentioned-worker` runs somewhere else. To process
jobs continuously on Render, add a Render background worker; Render does not offer free background
worker instances, so that starts at the paid worker instance price.

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
- `MIGRATION_DATABASE_URL`: connects as a Supabase owner/admin role, used locally to run Alembic
  migrations before deploying the free Render API.

Use Supabase Direct connection if your host supports IPv6, otherwise use Supabase Session Pooler.
Avoid Transaction Pooler for this app because SQLAlchemy keeps pooled connections and transaction
pooling does not support all session behavior.

For Supabase pooler URLs, the user name usually includes the project reference suffix, for example
`mentioned_api.<project-ref>` and `mentioned_worker.<project-ref>`.

## 2. Create the Render Blueprint

Use the root `render.yaml` file to create the Blueprint in Render. It defines:

- one Docker web service named `mentioned-api` on Render Free;
- Render region `frankfurt`;
- `/health` as the API health check;

Render will prompt for `sync: false` environment variables. Set these on the API service:

```text
DATABASE_URL=postgresql://mentioned_api.../postgres
SUPABASE_PROJECT_URL=https://<project-ref>.supabase.co
SUPABASE_JWT_SECRET=<Supabase JWT secret>
CORS_ALLOWED_ORIGINS=https://<your-web-origin>
TRUSTED_HOSTS=mentioned-api.onrender.com,<your-custom-api-domain>
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

## 3. Run migrations

Free Render web services do not support predeploy commands, so run migrations outside Render before
deploying the API. From a local shell with dependencies installed:

```bash
DATABASE_URL='postgresql://postgres-owner-url' alembic upgrade head
```

Then run the Postgres RLS proof with admin, API-role, and worker-role connection strings:

```bash
POSTGRES_TEST_DATABASE_URL=postgresql://admin-or-owner-url \
POSTGRES_TEST_API_DATABASE_URL=postgresql://mentioned_api-url \
POSTGRES_TEST_WORKER_DATABASE_URL=postgresql://mentioned_worker-url \
python -m pytest tests/test_postgres_dedicated_worker_rls.py
```

## 4. Run a worker

The free Render Blueprint does not include a worker. To process jobs, run the worker from a machine
or service that can stay online:

```bash
APP_ENV=production \
AUTH_MODE=supabase \
DATABASE_URL='postgresql://mentioned_api-url' \
WORKER_DATABASE_URL='postgresql://mentioned_worker-url' \
GEMINI_API_KEY='<Gemini API key>' \
mentioned-worker
```

If you later choose to run the worker on Render, create a Render background worker with the same
Dockerfile and `sh scripts/render-start-worker.sh` command, set `numInstances` to `1`, and add
`sh scripts/render-predeploy.sh` as the predeploy command.

After Render deploys, run the full job smoke test:

```bash
TOKEN='user-a-access-token' \
SECOND_TOKEN='user-b-access-token' \
SOURCE_URL='https://www.instagram.com/reel/SHORTCODE/' \
python scripts/smoke_job_flow.py --api-base-url https://mentioned-api.onrender.com
```

## 5. Mobile app configuration

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
