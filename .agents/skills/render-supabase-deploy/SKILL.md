---
name: render-supabase-deploy
description: Use when deploying, debugging, or changing Render services, Supabase Postgres/Auth, RLS, worker/API role separation, environment checks, or production release workflows.
---

# Render And Supabase Deploy

Use this skill for production deployment, hosted backend failures, Supabase schema
and RLS work, Render API/worker services, and release checks.

For Render-specific operations, prefer the Render plugin skills first and then
apply this repo's service topology and Supabase rules:

- Use `Render:render-debug` / `@render` when deployments fail, services crash,
  health checks fail, logs show errors, or production behavior differs from local.
- Use `Render:render-deploy` when creating or changing Render services,
  Blueprints, deploy configuration, or hosting setup.

This skill should cover what the Render plugin cannot know: this repo's API and
worker split, Supabase role separation, beta worker constraints, release checks,
and local migration/config files.

## First Reads

- Deployment guide and RLS role setup: `README.md` ("Deploy to Render + Supabase" section)
- Render blueprint: `render.yaml`
- Release env check: `scripts/check_release_env.py`
- Render scripts: `scripts/render-predeploy.sh`, `scripts/render-start-api.sh`,
  `scripts/render-start-worker.sh`
- Database config: `src/database.py`, `src/config.py`
- Migrations: `migrations/`, `supabase/migrations/` if present

## Hosted Failure Workflow

1. Apply `Render:render-debug` first for Render log, deploy, health, metric, and
   service evidence.
2. Use Render evidence before guessing from local code:
   - deploy status
   - runtime logs
   - health checks
   - service config
   - recent deploy/error events
3. Summarize the Render evidence used.
4. Connect production symptoms to local code, config, migration, or environment
   changes.

## Supabase Workflow

Follow `AGENTS.md` strictly:

- Use Supabase CLI for schema, migration, seed, RLS, or config changes.
- Check `supabase --help` and relevant subcommand help because CLI behavior changes.
- Prefer local/dev verification before hosted changes.
- For hosted targets, run `supabase db push --dry-run` before `supabase db push`.
- Never commit passwords, access tokens, service-role keys, `.env`, local DB URLs, or
  generated artifacts.

## Beta Role Boundary

- API role and worker role must remain separate in production.
- `DATABASE_URL` is the API role and must not be superuser or `BYPASSRLS`.
- `WORKER_DATABASE_URL` is the internal worker role and is required by the worker in
  production.
- Keep beta worker replica count aligned with the current queue-claiming guarantees.

## Validation

Use relevant checks:

```bash
python -m pytest
python scripts/check_release_env.py --env-file .env --worker-replicas 1
alembic upgrade head
```

For Supabase changes, use the exact CLI command required by the migration/config
scope and report the command plus any errors.
