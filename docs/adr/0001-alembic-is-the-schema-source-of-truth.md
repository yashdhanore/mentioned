# Alembic is the single source of truth for everything in the `public` schema

The repo contains three apparent schema mechanisms: Alembic migrations (`migrations/versions/`), `SQLModel.metadata.create_all` (`src/database.py`, `create_db_and_tables`), and hand-written `supabase/migrations/*.sql`.
Only Alembic is authoritative for `public`: tables, columns, grants, and row-level security policies alike (RLS lives in Alembic, not in Supabase SQL).
Production applies it via `alembic upgrade head` in the worker pre-deploy step (`scripts/render-predeploy.sh`).
`create_all` is dev-only; `AUTO_CREATE_TABLES=false` in prod (`render.yaml`) makes it a no-op there.

**2026-09-22 update:** the `supabase/migrations/*.sql` files are not vestigial the way this ADR originally claimed.
`20260523223851_job_thumbnails_bucket.sql` is load-bearing (the storage bucket lives in Supabase, not `public`) and is applied by a manual `supabase db push` before each deploy (see `docs/deployment.md`).
The other two files (`20260606110146_add_job_source_creator_handle.sql`, `20260608214109_create_waitlist_signups.sql`) predate this ADR and duplicated schema that Alembic now also owns (`waitlist_signups` got an Alembic revision, since a database built from `alembic upgrade head` alone had no table behind `POST /v1/waitlist`).
Those two files are kept only because the Supabase CLI tracks applied migrations by version, not checksum, and deleting a version already recorded as applied in production risks `supabase db push` reporting missing remote versions.
Their bodies were rewritten to be idempotent, order-independent no-ops so they can never diverge from what Alembic does.

**2026-09-22 squash:** the chain (17 files, `20260504_0003` through `20260922_0018`, including the hash-named `781a3572bbaf`) was squashed into one file, `migrations/versions/20260922_0018_initial_schema.py`, containing only the net live schema.
The legacy `jobs`/`mentions`/`job_events` tables and `extract_jobs` pgmq queue were created and dropped within that chain, so the squash never recreates them.
The revision id was kept as `20260922_0018`, the old chain's head, so production's `alembic_version` row needs no `alembic stamp`; `alembic upgrade head` against it is a no-op there.
A throwaway Postgres container confirmed that the squashed file produces schema, grants, RLS, and pgmq state identical to the old 17-file chain (schema-only `pg_dump`, `pg_policies`, `information_schema.role_table_grants`, and `pgmq.list_queues()`, diffed).
The next real revision continues as `20260923_0019`, with `down_revision = "20260922_0018"`.

**2026-09-23 fix:** `20260608214109_create_waitlist_signups.sql` was idempotent but not a no-op: it still created `public.waitlist_signups`.
The squashed revision creates the table with a plain `CREATE TABLE`, and `supabase start`/`supabase db reset` apply Supabase migrations before `make dev` runs Alembic, so every fresh database failed with "relation waitlist_signups already exists".
Its body is now `select 1;`, which production (where the version is already recorded as applied) never reruns.
Verified with `supabase db reset --local` followed by `make dev`: `public` is empty after the reset, Alembic builds the whole schema, and `POST /v1/waitlist` works.

## Consequences

- Table, column, grant, and RLS changes go in a new Alembic revision under `migrations/versions/`, not Supabase SQL.
  The Supabase CLI owns storage buckets, auth, and local stack config (`supabase/config.toml`), nothing in `public`.
- Editing `supabase/migrations/*.sql` to change `public` schema, grants, or RLS has no effect in prod; those files (other than the storage bucket one) are guarded no-ops by design.
- The root `AGENTS.md`/`CLAUDE.md` and `supabase/AGENTS.md` previously pointed at the Supabase CLI for all schema work; the root guide was corrected on 2026-06-28, and both were corrected again on 2026-09-22 to state that Alembic owns RLS too, not only tables.
