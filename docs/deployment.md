# Deployment

This is the full runbook for deploying Mentioned to Render and Supabase.
The root [README](../README.md#deployment) links here for the short version.

## Services

The repo deploys three Render services against one Supabase project, defined in `render.yaml`:

- `mentioned-web`: static Astro build of the landing page (`web/`), Render static site.
- `mentioned-api`: public FastAPI web service (Render Starter plan), region `frankfurt`, `/health` as the health check.
- `mentioned-worker`: private background worker (Render Starter plan), region `frankfurt`, `numInstances: 1`, `alembic upgrade head` as the pre-deploy migration command (`scripts/render-predeploy.sh`).
- Supabase: Postgres (with the `pgmq` extension), Supabase Auth, and Supabase Storage for the production database and thumbnail bucket.

## Create Supabase roles

Run role setup and verification from a secure local shell with a database admin connection (not the application/migration role), keeping any role-password SQL out of the repository:

```sql
create role mentioned_api login password 'replace-with-strong-api-password' nosuperuser nobypassrls;
create role mentioned_worker login password 'replace-with-strong-worker-password' nosuperuser nobypassrls;
```

Create these roles before running `alembic upgrade head`.
Alembic manages the table grants and RLS policies for the live tables (`sources`, `source_items`, `saved_sources`, `books`, `places`, push tokens, waitlist).
Verify each role with the exact connection string planned for that service:

```sql
select current_user, rolsuper, rolbypassrls from pg_roles where rolname = current_user;
```

Both `rolsuper` and `rolbypassrls` must be `false`.
The API startup check rejects `DATABASE_URL` if the connected role is a superuser or has `BYPASSRLS` (`src/database.py`, `check_api_database_role`).
The worker refuses to start in production unless `WORKER_DATABASE_URL` is set to an equally restricted role (`check_worker_database_role`).
Use three separate connection strings:

- `DATABASE_URL`: connects as `mentioned_api` (used by the API).
- `WORKER_DATABASE_URL`: connects as `mentioned_worker` (used by `mentioned-worker`).
- `MIGRATION_DATABASE_URL`: connects as a Supabase owner/admin role, used only by the Render worker pre-deploy command to run Alembic migrations.

Use the Supabase Direct connection if your host supports IPv6, otherwise the Session Pooler; avoid the Transaction Pooler because SQLAlchemy keeps pooled connections and transaction pooling does not support all session behavior.
For pooler URLs the username usually includes the project ref suffix, e.g. `mentioned_api.<project-ref>`.

## Render Blueprint

The root `render.yaml` defines the three services above.
Render prompts for `sync: false` environment variables.
Set runtime variables on both `mentioned-api` and `mentioned-worker`, and set `MIGRATION_DATABASE_URL` plus `SUPABASE_SERVICE_ROLE_KEY` on the worker only:

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

`SUPABASE_SERVICE_ROLE_KEY` is used only by the worker to copy public Reel thumbnails into the public `job-thumbnails` Supabase Storage bucket; never set it in the mobile app or expose it to browser clients.
The bucket path still contains a literal `jobs/` segment on purpose, so already-uploaded thumbnails are not orphaned by later renames (`src/storage/thumbnails.py`).

The blueprint sets the required non-secret production flags on both API and worker (`APP_ENV=production`, `AUTH_MODE=supabase`, `AUTO_CREATE_TABLES=false`, `DOCS_ENABLED=false`, `SOURCE_REQUIRE_HTTPS=true`, `WORKER_REPLICAS=1`, `SUPABASE_JWT_AUDIENCE=authenticated`).
The worker additionally sets `RELEVANCE_GATE_MODE=active`.
For Supabase projects using JWT Signing Keys, no `SUPABASE_JWT_SECRET` is needed; the API verifies RS256/ES256 access tokens against Supabase's JWKS endpoint.
If you rename the Render API service, update `TRUSTED_HOSTS` to match the actual Render hostname.

Apply Supabase migrations (`supabase db push --dry-run` then `supabase db push`) before deploying the worker so the public thumbnail bucket exists.
Table and column schema itself is owned by Alembic, not the Supabase CLI; see [`docs/adr/0001-alembic-is-the-schema-source-of-truth.md`](adr/0001-alembic-is-the-schema-source-of-truth.md).

### Worker replica count

`render.yaml` sets `numInstances: 1` for `mentioned-worker`, and `scripts/check_release_env.py` fails the release check if `WORKER_REPLICAS` is not `1`.
The source claim itself is already an atomic `UPDATE ... WHERE status = 'pending' ... RETURNING` (`claim_source_for_processing` in `src/sources/service.py`), and the pgmq-backed queue path (`src/ingestion/queue_worker.py`) already tolerates a message being picked up twice: a second claim attempt on an already-claimed source returns `None` and the message is left unarchived.
Neither of those requires a single replica to stay correct.
The codebase does not document a technical reason the replica count must stay at one; treat it as a current beta-scope operating policy (`scripts/check_release_env.py`, `.agents/skills/render-supabase-deploy/SKILL.md`) rather than a correctness requirement, and re-check `scripts/check_release_env.py` before assuming it still applies.

## Verify release shape

```bash
python scripts/check_release_env.py --env-file .env.production --worker-replicas 1
POSTGRES_TEST_DATABASE_URL=postgresql://admin-or-owner-url \
POSTGRES_TEST_API_DATABASE_URL=postgresql://mentioned_api-url \
POSTGRES_TEST_WORKER_DATABASE_URL=postgresql://mentioned_worker-url \
python -m pytest tests/test_postgres_dedicated_worker_rls.py
```

Then, after Render deploys, run the smoke test flow below against the deployed API.
In Render, inspect deploy status, runtime logs, health checks, and recent deploy/error events to confirm both services deployed from the intended commit, the health check passed, the worker has one instance, migrations ran through the worker pre-deploy step, and worker logs show queue claim, retry/failure, and archive paths clearly.

## Mobile app configuration

Native iOS and Android apps can use this backend; CORS is a browser concern, not a native mobile HTTP concern, but the API still enforces Supabase bearer tokens in production.
Set the mobile build environment to:

```text
EXPO_PUBLIC_APP_ENV=production
EXPO_PUBLIC_API_BASE_URL=https://mentioned-api.onrender.com
EXPO_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable-or-anon-key>
```

Production mobile builds intentionally reject local or non-HTTPS API URLs.
See [`mobile/README.md`](../mobile/README.md) for the full mobile environment and sign-in setup.

## Smoke test the saved-source flow

With the API and worker running, submit a real saved source, poll until terminal, verify extracted items, and prove another user cannot read the saved source:

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
