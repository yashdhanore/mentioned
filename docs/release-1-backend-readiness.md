# Release 1 Backend Readiness Runbook

Use this runbook as the App Store/TestFlight backend gate for Release 1. It makes the current
FastAPI API, Render worker, Supabase Postgres/Auth, PGMQ queue, and migration path explicit before
iOS submission.

## Scope

This checklist covers backend readiness evidence only:

- Render `mentioned-api` and `mentioned-worker` deploy shape.
- Alembic and Supabase migration state.
- API and worker database role boundaries.
- Release environment guardrails for production shape and per-user job quotas.
- Real-source smoke coverage through job detail mentions and saved mentions.
- Render logs needed to diagnose queue claim, retry, failure, and archive paths.

## Non-Goals

Do not redesign provider cost controls, queue claiming, queue architecture, multi-worker support, or
mobile UI as part of this readiness pass. Do not add Alembic or Supabase migrations unless a
separate issue requires schema changes.

## Required Production Or Staging Evidence

Collect this evidence against the same commit and environment values intended for Release 1:

- Alembic head is applied through the Render worker predeploy command.
- Supabase storage migration is applied with `supabase db push --dry-run` followed by
  `supabase db push`.
- `mentioned-api` and `mentioned-worker` are deployed from the intended commit.
- The `mentioned-api` health check passes.
- `mentioned-worker` has exactly one instance.
- API and worker roles are non-superuser and non-`BYPASSRLS`.
- `scripts/check_release_env.py` passes against the same values used on Render.
- Quota guardrails are set to, or default to, burst `3/min`, daily `25/day`, active `5/user`.
- A real-source smoke test passes with `--require-mentions`.

## Local Verification

Run these before using hosted credentials:

```bash
python -m pytest
python scripts/check_release_env.py --env-file .env.production --worker-replicas 1
alembic upgrade head
```

If `.env.production` is not present locally, the release operator must run the env check from a
secure shell that has the Render-equivalent values.

## Supabase CLI Verification

Run CLI help first because Supabase CLI behavior changes:

```bash
supabase --help
supabase db --help
supabase migration list --linked
supabase db push --dry-run
supabase db push
supabase db query --linked "select current_user;"
```

Do not run `supabase db push` against a hosted project unless the linked project is the intended
Release 1 target.

## RLS Proof

Verify the dedicated API and worker database roles with the exact connection strings planned for
Render:

```bash
POSTGRES_TEST_DATABASE_URL=postgresql://admin-or-owner-url \
POSTGRES_TEST_API_DATABASE_URL=postgresql://mentioned_api-url \
POSTGRES_TEST_WORKER_DATABASE_URL=postgresql://mentioned_worker-url \
python -m pytest tests/test_postgres_dedicated_worker_rls.py
```

The expected result is that API and worker roles are non-superuser and non-`BYPASSRLS`, and the
cross-user RLS proof passes.

## Release Smoke

Use two Supabase user access tokens and a real supported source URL:

```bash
TOKEN='user-a-access-token' \
SECOND_TOKEN='user-b-access-token' \
SOURCE_URL='https://www.instagram.com/reel/SHORTCODE/' \
python scripts/smoke_job_flow.py \
  --api-base-url https://mentioned-api.onrender.com \
  --require-mentions
```

The smoke must create a job, poll it to `done`, print job-detail mentions, fetch
`GET /v1/mentions?limit=100`, verify saved mentions include the job mention IDs, and prove the
second user cannot read the first user's job.

## Render Evidence

Inspect Render deploy status, runtime logs, health checks, service configuration, and recent deploy
or error events. Capture evidence for:

- worker startup mode;
- recovered stale jobs;
- queue message read, claim, and archive logs;
- job failure warnings;
- retryable push delivery warnings;
- absence of repeated unarchived messages for the same job after the smoke test.

## Completion Checklist

Copy this into the issue or PR and check each item with the collected evidence:

- [ ] Production/staging Alembic migrations are at head.
- [ ] Supabase storage migrations are applied.
- [ ] API and worker Render services are deployed from the intended commit.
- [ ] Release env check passes with one worker replica.
- [ ] API and worker database roles are non-superuser and non-`BYPASSRLS`.
- [ ] Per-user job guardrail tests pass and production values are within Release 1 bounds.
- [ ] Worker logs show claim, failure, retry, and archive paths clearly enough for diagnosis.
- [ ] Real-source smoke passes and saved mentions are returned.
- [ ] No provider cost redesign or queue architecture redesign was introduced.
