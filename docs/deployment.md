# Deployment

Runbook for deploying Mentioned to Render and Supabase.

## Services

The repo deploys three Render services against one Supabase project, defined in `render.yaml`:

- `mentioned-web`: static Astro build of the landing page (`web/`), Render static site.
- `mentioned-api`: public FastAPI web service (Render Starter plan), region `frankfurt`, `/health` as the health check.
- `mentioned-worker`: private background worker (Render Starter plan), region `frankfurt`, `numInstances: 1`.
  Its pre-deploy command (`scripts/render-predeploy.sh`) runs `scripts/check_release_env.py` and then `alembic upgrade head` as `MIGRATION_DATABASE_URL`.
- Supabase: Postgres (with the `pgmq` extension), Supabase Auth, and Supabase Storage for the production database and thumbnail bucket.

## Create Supabase roles

Run role setup and verification from a local shell with a database admin connection, and keep role-password SQL out of the repository:

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
Render prompts for the `sync: false` environment variables.
Both `mentioned-api` and `mentioned-worker` need:

```text
DATABASE_URL=postgresql://mentioned_api.../postgres
SUPABASE_PROJECT_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
TRUSTED_HOSTS=mentioned-api.onrender.com,<your-custom-api-domain>
```

The worker also needs:

```text
WORKER_DATABASE_URL=postgresql://mentioned_worker.../postgres
MIGRATION_DATABASE_URL=postgresql://postgres.../postgres
GEMINI_API_KEY=<Gemini API key>
GOOGLE_BOOKS_API_KEY=<optional Google Books API key>
LANGFUSE_PUBLIC_KEY=<optional Langfuse project public key>
LANGFUSE_SECRET_KEY=<optional Langfuse project secret key>
```

With both Langfuse keys set, the worker sends one trace per extraction attempt to Langfuse Cloud EU (`LANGFUSE_BASE_URL`, set in the blueprint): download, relevance gate, extraction, and each book lookup, with token usage and cost, under environment `production` and the deployed commit as release.
Without them the worker runs the same and sends nothing.
The API calls no model, so it has no Langfuse keys.

`CORS_ALLOWED_ORIGINS` (both services) and `WEB_BASE_URL` (API only) are set in the blueprint to `https://mentioned-web.onrender.com`; change them there if the web app moves.
With `WEB_BASE_URL` set, `GET /privacy` and `GET /support` on the API 301-redirect to the web app, so `web/src/pages/privacy.astro` and `support.astro` own that copy.
Without it, the API serves built-in fallback pages, so neither URL 404s before the web app is deployed.

`SUPABASE_SERVICE_ROLE_KEY` is server-only: never set it in the mobile app or expose it to browser clients.
The API uses it to delete the user's Supabase login on `DELETE /v1/account`, and the worker uses it to copy public Reel thumbnails into the public `job-thumbnails` Supabase Storage bucket.
Production settings validation refuses to start either service without it, because an API without it could not remove logins on account deletion.
The bucket path still contains a literal `jobs/` segment on purpose, so already-uploaded thumbnails are not orphaned by later renames (`src/storage/thumbnails.py`).

The blueprint also sets the non-secret production flags on both services (`APP_ENV=production`, `AUTH_MODE=supabase`, `AUTO_CREATE_TABLES=false`, `DOCS_ENABLED=false`, `SOURCE_REQUIRE_HTTPS=true`, `WORKER_REPLICAS=1`, `SUPABASE_JWT_AUDIENCE=authenticated`).
The worker additionally sets `RELEVANCE_GATE_MODE=active`.
For Supabase projects using JWT Signing Keys, no `SUPABASE_JWT_SECRET` is needed; the API verifies RS256/ES256 access tokens against Supabase's JWKS endpoint.
If you rename the Render API service, update `TRUSTED_HOSTS` to match the actual Render hostname.

Apply Supabase migrations (`supabase db push --dry-run` then `supabase db push`) before deploying the worker so the public thumbnail bucket exists.
Table and column schema itself is owned by Alembic, not the Supabase CLI; see [`docs/adr/0001-alembic-is-the-schema-source-of-truth.md`](adr/0001-alembic-is-the-schema-source-of-truth.md).

### Worker replica count

`render.yaml` sets `numInstances: 1` for `mentioned-worker`, and `scripts/check_release_env.py` fails the release check if `WORKER_REPLICAS` is not `1`.
This is a beta operating policy, not a correctness requirement.
The source claim is an atomic `UPDATE ... WHERE status = 'pending' ... RETURNING` (`claim_source_for_processing` in `src/sources/service.py`), and the pgmq queue path (`src/ingestion/queue_worker.py`) tolerates a message being picked up twice: a second claim on an already-claimed source returns `None` and the message is left unarchived.

## Verify release shape

The worker pre-deploy step runs the release check on Render; run it locally first against the production values, together with the dedicated-role RLS proof:

```bash
uv run python scripts/check_release_env.py --env-file .env.production --worker-replicas 1
POSTGRES_TEST_DATABASE_URL=postgresql://admin-or-owner-url \
POSTGRES_TEST_API_DATABASE_URL=postgresql://mentioned_api-url \
POSTGRES_TEST_WORKER_DATABASE_URL=postgresql://mentioned_worker-url \
uv run pytest tests/test_postgres_dedicated_worker_rls.py
```

After Render deploys, run the smoke test below against the deployed API.
In Render, check that both services deployed from the intended commit, the API health check passed, the worker has one instance, the pre-deploy step ran migrations, and worker logs show sources being claimed, completed or failed, and archived.

## Mobile app configuration

CORS does not apply to the native app, but the API still requires a Supabase bearer token in production.
Set the mobile build environment to:

```text
EXPO_PUBLIC_APP_ENV=production
EXPO_PUBLIC_API_BASE_URL=https://mentioned-api.onrender.com
EXPO_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable-or-anon-key>
EXPO_PUBLIC_PRIVACY_POLICY_URL=https://<your-web-origin>/privacy
```

Production mobile builds refuse to start with a local or non-HTTPS API URL, a dev auth mode, or no privacy policy URL (`mobile/src/api.ts`).
See [`mobile/README.md`](../mobile/README.md) for the full mobile environment and sign-in setup.

## Smoke test the saved-source flow

`scripts/smoke_saved_source_flow.py` submits a real saved source, polls until it finishes, checks the extracted items, and, when `SECOND_TOKEN` is set, checks that a second user cannot read it.
`scripts/get_supabase_access_token.py` signs in with email and password and prints an access token for `TOKEN` and `SECOND_TOKEN`.

```bash
export API_BASE_URL='https://mentioned-api.onrender.com'
export TOKEN='paste-supabase-access-token'
export SECOND_TOKEN='paste-second-user-supabase-access-token'
export SOURCE_URL='https://www.instagram.com/reel/SHORTCODE/'
uv run python scripts/smoke_saved_source_flow.py --require-items --timeout-seconds 600
```

Each variable can also be passed as a flag (`--api-base-url`, `--token`, `--second-token`, `--source-url`); `API_BASE_URL` defaults to `http://127.0.0.1:8000`.
