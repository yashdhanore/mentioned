# Beta RLS Option B Runbook

Option B is the v1 beta default: the public FastAPI service uses a database role that cannot bypass
Postgres RLS, and workers use a separate internal database role for cross-user queue work.

Run the role setup with a database admin connection, not from the application migration role.
Replace passwords before running.

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

Create these roles before running `alembic upgrade head`. Alembic manages the table grants and RLS
policies for `jobs` and `mentions`.

Production environment:

```bash
APP_ENV=production
AUTH_MODE=supabase
DATABASE_URL=postgresql://mentioned_api:...@.../postgres
WORKER_DATABASE_URL=postgresql://mentioned_worker:...@.../postgres
```

The API startup check rejects `DATABASE_URL` if the connected role is a superuser or has
`BYPASSRLS`. The worker refuses to start in production unless `WORKER_DATABASE_URL` is set and the
connected worker role is also non-superuser and non-`BYPASSRLS`.

Verify the API role with the exact connection string planned for FastAPI:

```sql
select current_user, rolsuper, rolbypassrls
from pg_roles
where rolname = current_user;
```

Expected:

```text
rolsuper = false
rolbypassrls = false
```

Verify the worker role with the exact connection string planned for `mentioned-worker`; the expected
`rolsuper` and `rolbypassrls` values are also both `false`.

Run the release proof:

```bash
POSTGRES_TEST_DATABASE_URL=postgresql://admin-or-owner-url \
POSTGRES_TEST_API_DATABASE_URL=postgresql://mentioned_api-url \
POSTGRES_TEST_WORKER_DATABASE_URL=postgresql://mentioned_worker-url \
python -m pytest tests/test_postgres_dedicated_worker_rls.py
```

Run the deployed beta smoke with two different Supabase user tokens:

```bash
TOKEN='user-a-access-token' \
SECOND_TOKEN='user-b-access-token' \
SOURCE_URL='https://www.instagram.com/reel/SHORTCODE/' \
python scripts/smoke_job_flow.py --api-base-url https://your-beta-api.example
```

For v1 beta, the frontend may use Supabase Auth only. Direct frontend or mobile reads from Supabase
tables are forbidden; all user-owned reads and writes must go through FastAPI.
