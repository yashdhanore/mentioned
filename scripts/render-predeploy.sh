#!/usr/bin/env sh
set -eu

python scripts/check_release_env.py --worker-replicas "${WORKER_REPLICAS:-1}"
if [ -z "${MIGRATION_DATABASE_URL:-}" ]; then
  echo "MIGRATION_DATABASE_URL is required for Render predeploy migrations" >&2
  exit 1
fi

DATABASE_URL="$MIGRATION_DATABASE_URL" alembic upgrade head
