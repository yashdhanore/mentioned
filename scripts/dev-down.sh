#!/usr/bin/env bash
# Stops everything scripts/dev-up.sh started.
set -uo pipefail
cd "$(dirname "$0")/.."

echo "Stopping backend, worker, web, and mobile..."
pkill -f "fastapi dev --port 8000" 2>/dev/null
pkill -f "mentioned-worker" 2>/dev/null
pkill -f "astro dev" 2>/dev/null
pkill -f "expo start --web" 2>/dev/null

echo "Stopping local Supabase stack..."
supabase stop

echo "All stopped."
