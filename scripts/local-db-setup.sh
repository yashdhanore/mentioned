#!/usr/bin/env bash
# Prepares a running local Supabase stack for the app: the least-privilege API and worker
# database roles, the Alembic schema, and the Supabase-managed storage bucket migrations.
# Idempotent. Run after `supabase start`; used by scripts/dev-up.sh and the CI e2e job.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Ensuring local dev database roles exist..."
docker exec -i supabase_db_mentioned psql -U postgres -d postgres -v ON_ERROR_STOP=1 <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mentioned_api') THEN
    CREATE ROLE mentioned_api LOGIN PASSWORD 'local-dev-api-pw' NOSUPERUSER NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mentioned_worker') THEN
    CREATE ROLE mentioned_worker LOGIN PASSWORD 'local-dev-worker-pw' NOSUPERUSER NOBYPASSRLS;
  END IF;
END
$$;
SQL

echo "Applying backend schema migrations (alembic)..."
DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:54322/postgres" \
  .venv/bin/alembic upgrade head

echo "Applying Supabase-managed migrations (storage buckets)..."
supabase migration up --local
