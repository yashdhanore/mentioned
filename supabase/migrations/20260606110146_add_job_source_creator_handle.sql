-- Alembic owns public.sources.creator_handle now (migrations 0011/0014/0017). This file is
-- kept only because the Supabase CLI tracks applied migrations by version, not checksum, and
-- this version is already recorded as applied in production; its body is now a no-op guarded
-- against public.jobs (dropped by Alembic revision 20260921_0017) not existing.
do $$
begin
  if to_regclass('public.jobs') is not null then
    alter table public.jobs
    add column if not exists source_creator_handle text;
  end if;
end
$$;
