-- Alembic owns public.waitlist_signups now (migrations/versions/20260922_0018_waitlist_signups.py).
-- Kept only because the Supabase CLI tracks applied migrations by version, not checksum, and this
-- version is already recorded as applied in production; body stays idempotent and order-independent
-- with that Alembic revision so either one can run first without weakening the other's RLS policy.
create extension if not exists pgcrypto;

create table if not exists public.waitlist_signups (
    id uuid primary key default gen_random_uuid(),
    email text not null,
    source text,
    user_agent text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint waitlist_signups_email_normalized check (email = lower(trim(email))),
    constraint waitlist_signups_email_not_blank check (length(email) > 3),
    constraint waitlist_signups_source_length check (source is null or length(source) <= 120)
);

create unique index if not exists waitlist_signups_email_lower_idx
on public.waitlist_signups (lower(email));

alter table public.waitlist_signups enable row level security;

revoke all on table public.waitlist_signups from anon, authenticated;

drop policy if exists waitlist_signups_app_manage on public.waitlist_signups;
drop policy if exists waitlist_signups_api_manage on public.waitlist_signups;

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'mentioned_api') then
    grant usage on schema public to mentioned_api;
    grant select, insert, update on table public.waitlist_signups to mentioned_api;
    create policy waitlist_signups_api_manage on public.waitlist_signups
      for all
      to mentioned_api
      using (true)
      with check (true);
  end if;
end $$;
