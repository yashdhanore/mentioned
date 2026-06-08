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
create policy waitlist_signups_app_manage on public.waitlist_signups
  for all
  using (true)
  with check (true);

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'mentioned_api') then
    grant usage on schema public to mentioned_api;
    grant select, insert, update on table public.waitlist_signups to mentioned_api;
  end if;
end $$;
