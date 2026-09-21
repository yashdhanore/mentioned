#!/usr/bin/env bash
# Stops everything scripts/dev-up.sh started.
set -uo pipefail
cd "$(dirname "$0")/.."

LOG_DIR=".dev-logs"

stop_pid() {
  local name=$1 pid_file="$LOG_DIR/$1.pid"
  if [ ! -f "$pid_file" ]; then
    return
  fi
  local pid
  pid=$(cat "$pid_file")
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    # dev-up.sh backgrounds some of these inside a subshell (e.g. `(cd web && npm run
    # dev) &`), so also stop the subshell's direct children (the actual dev server
    # process), not just the subshell PID itself.
    pkill -P "$pid" 2>/dev/null
    kill "$pid" 2>/dev/null
  fi
  rm -f "$pid_file"
}

echo "Stopping backend, worker, web, and mobile..."
stop_pid backend
stop_pid worker
stop_pid web
stop_pid mobile

echo "Stopping local Supabase stack..."
supabase stop

echo "All stopped."
