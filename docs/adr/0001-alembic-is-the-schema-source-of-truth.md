# Alembic is the single source of truth for everything in the `public` schema

The repo contains three apparent schema mechanisms: Alembic migrations
(`migrations/versions/`), `SQLModel.metadata.create_all` (`src/database.py:64`),
and hand-written `supabase/migrations/*.sql`. Only **Alembic** is authoritative for
`public`: tables, columns, grants, and row-level security policies alike (RLS lives
in 8 Alembic revisions, not in Supabase SQL). Production applies it via
`alembic upgrade head` in the worker pre-deploy step (`scripts/render-predeploy.sh`).
`create_all` is dev-only — `AUTO_CREATE_TABLES=false` in prod (`render.yaml`) makes it
a no-op there.

**2026-09-22 update:** the `supabase/migrations/*.sql` files are not vestigial the way
this ADR originally claimed. `20260523223851_job_thumbnails_bucket.sql` is load-bearing
(the storage bucket lives in Supabase, not `public`) and is applied by a manual
`supabase db push` before each deploy (see `docs/deployment.md`). The other two files
(`20260606110146_add_job_source_creator_handle.sql`,
`20260608214109_create_waitlist_signups.sql`) predate this ADR and duplicated schema
that Alembic now also owns (`waitlist_signups` got an Alembic revision,
`20260922_0018_waitlist_signups.py`, since a database built from `alembic upgrade head`
alone had no table behind `POST /v1/waitlist`). Those two files are kept only because
the Supabase CLI tracks applied migrations by version, not checksum, and deleting a
version already recorded as applied in production risks `supabase db push` reporting
missing remote versions; their bodies were rewritten to be idempotent, order-independent
no-ops so they can never diverge from what Alembic does.

## Consequences

- Table/column/grant/RLS changes go in a new Alembic revision under `migrations/versions/`,
  not Supabase SQL. The Supabase CLI owns storage buckets, auth, and local stack config
  (`supabase/config.toml`) — nothing in `public`.
- A future agent who edits `supabase/migrations/*.sql` to change `public` schema, grants,
  or RLS will see no effect in prod; those files (other than the storage bucket one) are
  guarded no-ops by design. Add or change schema via a new Alembic revision instead.
- The root `AGENTS.md`/`CLAUDE.md` and `supabase/AGENTS.md` previously pointed at the
  Supabase CLI for all schema work; the root guide was corrected on 2026-06-28, and both
  were corrected again on 2026-09-22 to state that Alembic owns RLS too, not just tables.
