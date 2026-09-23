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
  echo ".venv not found. Run: uv sync --frozen --extra dev" >&2
  exit 1
}

# npm writes node_modules/.package-lock.json on install, so a lockfile newer than it
# means a fresh clone or dependencies that changed since the last install.
for app in web mobile; do
  if [ ! -f "$app/node_modules/.package-lock.json" ] || [ "$app/package-lock.json" -nt "$app/node_modules/.package-lock.json" ]; then
    echo "Installing $app dependencies (npm ci)..."
    (cd "$app" && npm ci) > "$LOG_DIR/$app-install.log" 2>&1 || {
      echo "npm ci in $app failed, see $LOG_DIR/$app-install.log" >&2
      exit 1
    }
  fi
done

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

# Thumbnails go to the local Supabase Storage, using the local stack's own keys.
eval "$(supabase status -o env 2>/dev/null | grep -E '^(API_URL|SERVICE_ROLE_KEY)=')"
export SUPABASE_PROJECT_URL="$API_URL"
export SUPABASE_SERVICE_ROLE_KEY="$SERVICE_ROLE_KEY"

echo "Preparing the local database (roles, alembic, storage migrations)..."
scripts/local-db-setup.sh >> "$LOG_DIR/supabase.log" 2>&1 || {
  echo "Preparing the local database failed, see $LOG_DIR/supabase.log" >&2
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
# Points the app at the local API with dev sign-in. Expo's web bundle prefers values
# from mobile/.env*, so a mobile/.env with production settings needs a mobile/.env.local
# that sets these three (the app refuses dev sign-in in a production build).
(cd mobile && EXPO_PUBLIC_APP_ENV=development EXPO_PUBLIC_AUTH_MODE=dev \
  EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npx expo start --web) > "$LOG_DIR/mobile.log" 2>&1 &
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
