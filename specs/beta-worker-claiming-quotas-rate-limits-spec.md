# Beta Worker Claiming, Quotas, and Rate Limits Specification

Status: Draft

Last updated: 2026-05-03

Purpose: Define the remaining user-facing beta proof for two backend gate items:

- Worker claiming proven on Postgres.
- Quotas and rate limits enforced and configurable.

This spec is the implementation checklist for these two items only. It narrows and supersedes the
quota/claiming portions of the broader specs for beta readiness.

## Source Basis

This spec is based on:

- The current `JobCoordinator.claim_next_job()` Postgres branch.
- The current per-user job creation quotas in `JobCoordinator._enforce_create_quotas()`.
- The current `MAX_LLM_CALLS_PER_JOB` setting and OpenAI visual reconstruction call path.
- The current live Postgres/Supabase schema at Alembic head `20260502_0002`.
- The beta gate decision that the frontend should not start until concurrent worker claiming and
  cost/abuse controls are proven.

## Normative Language

The key words `MUST`, `MUST NOT`, `REQUIRED`, `SHOULD`, `SHOULD NOT`, `RECOMMENDED`, `MAY`, and
`OPTIONAL` in this document are to be interpreted as described in RFC 2119.

`Beta` means a user-facing deployment with real authenticated users, real persisted data, and real
provider/network cost risk.

## Current Status

### Worker Claiming

Current facts:

- The production branch uses one `UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED)
  RETURNING id` statement.
- Claiming commits before extraction runs.
- Existing fast tests use SQLite and prove only sequential behavior.
- A successful smoke job proves the vertical one-worker flow, but not concurrent worker safety.

Remaining gap:

- There is no committed real-Postgres test proving that two workers cannot claim the same queued job
  under row-lock contention.

### Quotas And Rate Limits

Current facts:

- Per-user burst job creation limit exists.
- Per-user rolling daily job creation limit exists.
- Per-user active queued/running job limit exists.
- Limits are configurable through settings/env.
- Public quota failures map to `429` with public error codes.
- `MAX_LLM_CALLS_PER_JOB` exists and the current multimodal path is structurally one OpenAI call per
  job.

Remaining gaps:

- There are no focused API tests proving quota failures produce the public `429` contract.
- There is no explicit per-IP rate-limit decision or implementation proof.
- There is no explicit beta contract for what happens when `MAX_LLM_CALLS_PER_JOB` is exhausted.
- There is no provider-call preflight that records/skips optional LLM work because of a quota
  decision.

## Required Outcome

The beta gate is satisfied when:

1. A real Postgres test proves `claim_next_job()` is safe under concurrent worker contention.
2. Per-user job quotas are covered by API tests.
3. Per-IP rate limiting is either implemented in the app or explicitly delegated to the deployment
   edge with documented configuration.
4. LLM-call limiting has a clear beta behavior and tests.

Backend code and test work for this spec MAY be completed before beta hosting is chosen. However,
the user-facing beta gate remains unsatisfied until the edge-level per-IP `POST /v1/jobs` rule is
named, documented, and verified in staging.

## 1. Worker Claiming Proven On Postgres

### Required Test

Add `tests/test_postgres_worker_claiming.py`.

The test MUST:

- Use a real Postgres database through `POSTGRES_TEST_DATABASE_URL`.
- Skip locally with an explicit reason when `POSTGRES_TEST_DATABASE_URL` is absent.
- Be required in CI before the beta gate is considered satisfied.
- Be included in normal `pytest` discovery. Local runs MAY skip it when `POSTGRES_TEST_DATABASE_URL`
  is absent, but beta CI/release validation MUST provide `POSTGRES_TEST_DATABASE_URL` and fail if
  the test does not pass.
- Exercise the actual `JobCoordinator.claim_next_job()` method.
- Use at least two eligible queued jobs.
- Hold a lock on the highest-priority queued job in one transaction.
- Call `claim_next_job("worker-b")` from a separate session while the first job is locked.
- Set a short local `statement_timeout` for the claim session so a blocking claim fails quickly.
- Prove worker B claims the second job, not the locked first job.
- Prove the locked first job remains queued while the lock is held.
- Release the setup lock and prove worker A can claim the first job.

The test MUST assert persisted state for each claimed job:

- `status = 'running'`
- `locked_by` matches the worker ID
- `locked_at is not null`
- `heartbeat_at is not null`
- `attempt_count = 1`
- `current_stage = 'claimed'`
- `progress = 0.01`

The test MUST NOT:

- Use SQLite.
- Mock `claim_next_job()`.
- Assert only that the SQL string contains `SKIP LOCKED`.
- Run against shared development, staging, or production data.

### Isolation Strategy

The first implementation SHOULD use a disposable schema created and dropped by the test run. The
test MUST set `search_path` through SQLAlchemy connection setup or migration setup and MUST avoid
leaking rows into the default `public` schema.

A disposable Postgres database dedicated to tests remains acceptable later if CI permissions and
local developer setup make it practical.

For this specific claiming proof, the test SHOULD create tables in the disposable schema with
`SQLModel.metadata.create_all()`. Alembic migration replay is covered separately by migration tests;
the purpose of this test is to prove `JobCoordinator.claim_next_job()` and Postgres row-lock
behavior under `FOR UPDATE SKIP LOCKED`.

### Documentation

README or the test module docstring MUST show:

```bash
POSTGRES_TEST_DATABASE_URL=postgresql://... pytest tests/test_postgres_worker_claiming.py
```

## 2. Per-User Job Quotas

The backend MUST enforce these per authenticated user:

- Burst create limit: default `3` jobs per minute.
- Rolling daily create limit: default `25` jobs per 24 hours.
- Active queued/running jobs limit: default `5`.

The implementation MUST keep these limits configurable:

- `MAX_JOB_CREATE_BURST_PER_MINUTE`
- `MAX_JOBS_CREATED_PER_DAY`
- `MAX_ACTIVE_JOBS_PER_USER`

Quota checks MUST run before creating a new job row.

Idempotent replay MUST be resolved before quota checks. If an authenticated user submits the same
`idempotency_key` for the same normalized URL, the API MUST return the existing job without creating
new work and without consuming an additional quota slot. If the same key is reused for a different
normalized URL, the API MUST keep returning `409 idempotency_conflict`.

Quota failures MUST:

- Return HTTP `429`.
- Use public `error_code = "rate_limited"` for burst failures.
- Use public `error_code = "quota_exceeded"` for daily and active-job quota failures.
- Return generic public messages only.
- Not reveal counts for other users, internal SQL, stack traces, or provider cost information.

Required tests:

These MUST be API-level tests through `POST /v1/jobs`. Lower-level `JobCoordinator` tests MAY be
added, but they do not substitute for the public API contract proof.

- A user exceeding burst limit receives `429 rate_limited`.
- A user exceeding daily limit receives `429 quota_exceeded`.
- A user exceeding active queued/running limit receives `429 quota_exceeded`.
- Another user is not affected by the first user's quota usage.
- Terminal jobs do not count against active-job quota.
- Idempotent replay of an existing job does not consume an additional quota slot.

### Rerun Quota Scope

For beta, `POST /v1/jobs/{job_id}/rerun` MUST be restricted by active-job quota at minimum because
reruns queue more backend work. A rerun does not need to count against the daily create quota for the
first beta. If the user already has too many queued/running jobs, rerun MUST return HTTP `429` with
public `error_code = "quota_exceeded"`. Because rerun is only allowed from terminal jobs, the
terminal job being rerun MUST NOT count against active quota before it is requeued; the check counts
the user's existing queued/running jobs first, then requeues only if there is capacity.

## 3. Per-IP Rate Limiting

The beta deployment MUST have a per-IP create-job rate limit.

Decision required before beta:

- **Option A: App-level limit.** Implement middleware or a request-aware dependency that throttles
  `POST /v1/jobs` by client IP.
- **Option B: Edge-level limit.** Enforce this at the deployment edge, such as a reverse proxy,
  hosting provider, WAF, or API gateway.

Recommended beta decision: use edge-level per-IP throttling if the deployment platform already
supports it. Keep app-level per-user quotas as the product/cost control.

Current beta decision: use edge-level per-IP throttling. The exact edge platform/rule is unresolved
until beta hosting is chosen and is therefore a beta blocker, even if backend code and tests are
otherwise complete.

If Option A is chosen, the app MUST:

- Derive client IP from a trusted proxy configuration only.
- Avoid trusting arbitrary `X-Forwarded-For` headers unless the request comes through a trusted
  proxy.
- Apply the limit to `POST /v1/jobs`.
- Return HTTP `429` with public `error_code = "rate_limited"`.
- Keep the limit configurable.

If Option B is chosen, the repo MUST document:

- Where the rate limit is configured.
- Which route/method it protects.
- The beta threshold.
- How to verify it in staging.

Minimum beta threshold:

- No more than `10` job-create requests per IP per minute.

This threshold MAY be lower if early provider cost data requires it.

## 4. LLM-Call Limit

The beta backend MUST limit optional multimodal LLM cost per job.

For beta, `MAX_LLM_CALLS_PER_JOB` applies only to multimodal visual reconstruction calls. It does
not count OpenAI audio transcription. ASR remains controlled by job creation quotas,
`MAX_ASR_AUDIO_BYTES`, provider configuration, and any future ASR-specific quota.

Required beta behavior:

- `MAX_LLM_CALLS_PER_JOB=1` is the default.
- `MAX_LLM_CALLS_PER_JOB=0` MUST mean multimodal LLM reconstruction is skipped.
- The skipped multimodal LLM stage MUST be recorded as a successful skipped stage, not as a provider
  failure. Its stage payload MUST include `skipped = true` and a safe skip reason such as
  `llm_call_limit_exhausted`.
- A quota-skipped multimodal LLM stage MUST NOT create a `provider_calls` row because no provider
  was invoked. The skip is recorded only in `job_stage_runs`, internal nonfatal gap tracking, and
  sanitized debug metadata when debug output is explicitly requested.
- Public result warnings MUST NOT mention the skipped multimodal LLM work. Regular users do not need
  provider, quota, or cost-control details for this beta behavior.
- Existing public result `stage_runs` and `artifacts` MAY remain in the response shape, but payloads,
  metadata, and error text MUST remain hidden from regular users by default. Removing these fields
  from the public response is a separate API contract decision outside this beta gate.
- Skipping multimodal reconstruction MUST NOT fail the whole job when OCR/caption/audio extraction
  can still produce useful text.
- The result MUST be `partial` if useful text exists and the skipped LLM stage is recorded as a
  nonfatal gap. The stage itself remains `success = true`; the partial status represents incomplete
  optional extraction coverage, not provider failure.
- If no useful text exists, the normal no-text failure behavior applies.

The implementation MUST NOT call OpenAI or another multimodal provider when the per-job LLM-call
limit is exhausted.

Required tests:

- With `MULTIMODAL_LLM_PROVIDER=openai` and `MAX_LLM_CALLS_PER_JOB=0`, the OpenAI visual provider is
  not invoked.
- The pipeline records a successful skipped stage payload and internal nonfatal gap indicating
  multimodal LLM work was skipped by quota.
- Useful OCR/caption output produces a `partial` text result when multimodal LLM reconstruction is
  skipped by quota.
- The public result does not expose provider internals or quota internals.
- The public result warnings do not mention the skipped multimodal LLM work.

Future per-user LLM-call quotas MAY be added after beta usage data exists. They are not required for
the first user-facing beta if per-job LLM calls are capped and job creation quotas are enforced.

## 5. Acceptance Criteria

This spec is complete when:

- `tests/test_postgres_worker_claiming.py` proves `SKIP LOCKED` behavior against real Postgres.
- The Postgres claiming test is documented and run in CI or a required beta-release checklist.
- API tests cover burst, daily, active-job, and cross-user quota behavior.
- The per-IP rate-limit decision is documented as app-level or edge-level.
- If app-level per-IP limiting is chosen, tests prove the `429 rate_limited` contract.
- If edge-level per-IP limiting is chosen, deployment docs identify the exact edge rule and staging
  verification command.
- `MAX_LLM_CALLS_PER_JOB=0` skips optional multimodal LLM calls without leaking internals or
  crashing otherwise useful extraction.
- `pytest` passes for the standard test suite.
- The Postgres-specific claiming test passes when `POSTGRES_TEST_DATABASE_URL` is provided.

## Non-Goals

- Adding Redis, Celery, SQS, Kafka, or another queue for beta.
- Building a generalized paid/free quota system before real usage data exists.
- Adding direct frontend Supabase reads.
- Adding user-facing provider-cost reporting.
- Replacing existing per-user owner filters with RLS-only authorization.
