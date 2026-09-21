# Supabase Agent Guide

Use this guide for storage bucket, auth, and local Supabase stack configuration changes.

**Alembic owns everything in the `public` schema** — tables, columns, grants, and row-level
security policies alike. See [`docs/adr/0001-alembic-is-the-schema-source-of-truth.md`](../docs/adr/0001-alembic-is-the-schema-source-of-truth.md).
Schema, grant, or RLS changes go in a new Alembic revision under `migrations/versions/`, never in
`supabase/migrations/*.sql`. The Supabase CLI's real job here is storage buckets, Supabase Auth
config, and the local dev stack (`supabase/config.toml`).
`supabase/migrations/*.sql` still exists for the storage bucket migration (load-bearing) plus two
older files that duplicate Alembic-owned `public` schema; those two are rewritten as guarded
no-ops kept only because the Supabase CLI tracks applied migrations by version, not checksum — do
not add new schema logic to them, and do not delete them without checking the ADR's reasoning.

## CLI Workflow

- Use the Supabase CLI directly instead of handing migration steps back to the user.
- Check current CLI behavior with `supabase --help` and the relevant `supabase <group> --help` because commands change.
- Create migrations with `supabase migration new <descriptive_name>` and keep SQL under `supabase/migrations/`, but only for storage/auth/local-stack concerns; `public` schema changes belong in an Alembic revision instead.
- Prefer local/dev verification before touching hosted projects.
- Apply and verify locally with the appropriate command, such as `supabase migration up --local` or `supabase db reset`.
- For hosted targets, run `supabase db push --dry-run` first, then run `supabase db push` only when the intended linked remote target is clear.

## Safety

- Do not make schema changes directly in the Supabase Dashboard or remote SQL editor after migrations exist.
- Do not commit Supabase passwords, access tokens, service-role keys, `.env` files, local database URLs, or generated artifacts.
- Non-secret config such as `supabase/config.toml`, migration SQL, seed files, and `.env.example` placeholders may be committed.
- For local automation, prefer `supabase login` and `supabase link --project-ref <ref>` so credentials stay in the OS credential store when available.
- For noninteractive runs, use environment variables such as `SUPABASE_ACCESS_TOKEN` and `SUPABASE_DB_PASSWORD` from the host environment or secret manager.

## Closeout

- End Supabase work with the commands run, the target verified, and any CLI, Docker, or credential errors encountered.
- Update this guide when Supabase CLI workflow, migration policy, secret handling, or hosted-target verification changes.
