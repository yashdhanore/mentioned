#!/usr/bin/env bash
# Starts the full local dev stack: Supabase (Postgres/Storage), backend API,
# worker, web app, and mobile app (Expo web). Logs go to .dev-logs/, PIDs to .dev-logs/*.pid.
set -uo pipefail
cd "$(dirname "$0")/.."

LOG_DIR=".dev-logs"
mkdir -p "$LOG_DIR"

command -v supabase >/dev/null 2>&1 || {
  echo "supabase CLI not found. Install with: brew install supabase/tap/supabase" >&2
  exit 1
}
docker info >/dev/null 2>&1 || {
  echo "Docker isn't running. Start Docker (or OrbStack) first." >&2
  exit 1
}
[ -x .venv/bin/fastapi ] || {
  echo ".venv not found. Run: python -m venv .venv && source .venv/bin/activate && pip install -e \".[dev]\"" >&2
  exit 1
}

wait_for() {
  local url=$1 name=$2 tries=30
  until curl -s -o /dev/null "$url"; do
    tries=$((tries - 1))
    if [ "$tries" -le 0 ]; then
      echo "  ✗ $name did not come up (see $LOG_DIR/$(echo "$name" | tr '[:upper:] ' '[:lower:]-').log)"
      return 1
    fi
    sleep 1
  done
  echo "  ✓ $name"
}

echo "Starting local Supabase (Postgres, Storage, Auth)..."
supabase start > "$LOG_DIR/supabase.log" 2>&1 || {
  echo "supabase start failed, see $LOG_DIR/supabase.log" >&2
  exit 1
}

# DATABASE_URL/WORKER_DATABASE_URL: the same local Postgres roles/URLs documented in
# README.md, exported so the API and worker processes below use Postgres (queue-backed
# worker, real RLS) without requiring a manual .env edit. python-dotenv's load_dotenv
# does not override already-set env vars, so this takes precedence over any .env value.
export DATABASE_URL="postgresql://mentioned_api:local-dev-api-pw@127.0.0.1:54322/postgres"
export WORKER_DATABASE_URL="postgresql://mentioned_worker:local-dev-worker-pw@127.0.0.1:54322/postgres"

echo "Ensuring local dev database roles exist..."
docker exec -i supabase_db_mentioned psql -U postgres -d postgres -v ON_ERROR_STOP=1 >> "$LOG_DIR/supabase.log" 2>&1 <<'SQL'
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
if [ $? -ne 0 ]; then
  echo "Creating local dev database roles failed, see $LOG_DIR/supabase.log" >&2
  exit 1
fi

echo "Applying backend schema migrations (alembic)..."
DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:54322/postgres" \
  .venv/bin/alembic upgrade head >> "$LOG_DIR/supabase.log" 2>&1
if [ $? -ne 0 ]; then
  echo "alembic upgrade head failed, see $LOG_DIR/supabase.log" >&2
  exit 1
fi

echo "Applying Supabase-managed migrations (storage buckets, RLS)..."
supabase migration up --local >> "$LOG_DIR/supabase.log" 2>&1 || {
  echo "supabase migration up --local failed, see $LOG_DIR/supabase.log" >&2
  exit 1
}

# The worker shells out to yt-dlp (found with shutil.which), which uv installs into
# .venv/bin; without this, downloads fail with "yt-dlp is not installed".
export PATH="$PWD/.venv/bin:$PATH"

echo "Starting backend API..."
.venv/bin/fastapi dev --port 8000 > "$LOG_DIR/backend.log" 2>&1 &
echo $! > "$LOG_DIR/backend.pid"
disown

echo "Starting worker..."
.venv/bin/mentioned-worker > "$LOG_DIR/worker.log" 2>&1 &
echo $! > "$LOG_DIR/worker.pid"
disown

echo "Starting web app..."
(cd web && npm run dev) > "$LOG_DIR/web.log" 2>&1 &
echo $! > "$LOG_DIR/web.pid"
disown

echo "Starting mobile app (Expo web)..."
(cd mobile && npx expo start --web) > "$LOG_DIR/mobile.log" 2>&1 &
echo $! > "$LOG_DIR/mobile.pid"
disown

echo ""
echo "Waiting for services to come up..."
wait_for "http://127.0.0.1:8000/docs" "Backend API"
wait_for "http://127.0.0.1:4321/" "Web app"
wait_for "http://localhost:8081/" "Mobile app"

cat <<EOF

Ready:
  Backend API      http://127.0.0.1:8000/docs
  Web app          http://127.0.0.1:4321
  Mobile app       http://localhost:8081
  Supabase Studio  http://127.0.0.1:54323

Logs: $LOG_DIR/
Stop everything with: scripts/dev-down.sh
EOF
