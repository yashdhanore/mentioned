-- Alembic owns public.waitlist_signups (migrations/versions/20260922_0018_initial_schema.py).
-- This file is kept only because the Supabase CLI tracks applied migrations by version, not
-- checksum, and this version is already recorded as applied in production. Its body is a no-op:
-- `supabase start` and `supabase db reset` apply it before Alembic runs, and creating the table
-- here made the initial Alembic revision fail on every fresh database with "relation
-- waitlist_signups already exists".
select 1;
