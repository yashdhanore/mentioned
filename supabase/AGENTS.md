# Supabase Agent Guide

Use this guide for Supabase schema, migration, seed, RLS, storage bucket, and Supabase configuration changes.

## CLI Workflow

- Use the Supabase CLI directly instead of handing migration steps back to the user.
- Check current CLI behavior with `supabase --help` and the relevant `supabase <group> --help` because commands change.
- Create migrations with `supabase migration new <descriptive_name>` and keep SQL under `supabase/migrations/`.
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
