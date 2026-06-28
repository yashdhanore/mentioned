# Alembic is the single source of truth for table/column schema

The repo contains three apparent schema mechanisms: Alembic migrations
(`migrations/versions/`), `SQLModel.metadata.create_all` (`src/database.py:64`),
and hand-written `supabase/migrations/*.sql`. Only **Alembic** is authoritative.
Production applies it via `alembic upgrade head` in the worker pre-deploy step
(`scripts/render-predeploy.sh`). `create_all` is dev-only — `AUTO_CREATE_TABLES=false`
in prod (`render.yaml`) makes it a no-op there. The `supabase/migrations/*.sql` files
are vestigial from an earlier approach and are not run by any deploy step.

## Consequences

- Table/column changes go in a new Alembic revision under `migrations/versions/`, not
  Supabase SQL. Use the Supabase CLI only for Supabase-managed concerns (RLS policies,
  storage buckets, auth/Supabase config).
- A future agent who edits `supabase/migrations/*.sql` to change schema will see no
  effect in prod. Those files should be treated as dead unless explicitly revived.
- The root `AGENTS.md`/`CLAUDE.md` and `supabase/AGENTS.md` previously pointed at the
  Supabase CLI for all schema work; the root guide was corrected on 2026-06-28.
