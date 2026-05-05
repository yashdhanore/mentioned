# Mentioned Backend

Validation scaffold for a backend that turns public Instagram Reel and post URLs into readable
text extracted from captions, media metadata, frames, and post images.

## Run the API

```bash
fastapi dev
```

Production schemas are managed with Alembic migrations:

```bash
alembic upgrade head
```

Local SQLite auto-creates tables only when `AUTO_CREATE_TABLES=true`; production should use
Postgres/Supabase with migrations applied before startup.

## Run the worker

```bash
python -m worker.run
```

In production, the API and worker must use separate database roles:

- `DATABASE_URL` is the FastAPI role and must be non-superuser and non-`BYPASSRLS`.
- `WORKER_DATABASE_URL` is the internal worker role and is required by `mentioned-worker` in
  production.

See [docs/beta-rls-option-b.md](docs/beta-rls-option-b.md) for the beta role setup and release
proof commands. For v1 beta, frontend clients may use Supabase Auth only; direct Supabase table
reads are forbidden.

## Run tests

```bash
python -m pytest
```

The Postgres dedicated-role RLS proof is skipped unless admin/setup, API-role, and worker-role URLs
are provided:

```bash
POSTGRES_TEST_DATABASE_URL=postgresql://admin-or-owner-url \
POSTGRES_TEST_API_DATABASE_URL=postgresql://mentioned_api-url \
POSTGRES_TEST_WORKER_DATABASE_URL=postgresql://mentioned_worker-url \
python -m pytest tests/test_postgres_dedicated_worker_rls.py
```

## Smoke test the full job flow

With the API and worker running, submit a real job, poll until terminal, fetch the result, and list
saved mentions for that job:

```bash
TOKEN='paste-supabase-access-token'
SECOND_TOKEN='paste-second-user-supabase-access-token'
SOURCE_URL='https://www.instagram.com/reel/SHORTCODE/'
python scripts/smoke_job_flow.py
```

Optional overrides:

```bash
python scripts/smoke_job_flow.py \
  --api-base-url http://127.0.0.1:8000 \
  --source-url "$SOURCE_URL" \
  --token "$TOKEN" \
  --timeout-seconds 600
```

## API

- `POST /v1/jobs` queues an extraction job for a URL.
- `GET /v1/jobs` lists the authenticated user's jobs with cursor pagination.
- `GET /v1/jobs/{job_id}` returns job status and is the required v1 polling endpoint.
- `GET /v1/jobs/{job_id}/result` returns the text-first result:
`caption_text`, `spoken_text`, `visual_text`, `image_text`, `merged_text`, and `warnings`.
Fetch results after polling observes `succeeded` or `partial`; `/result` is not the job-level
error source.
- `POST /v1/jobs/{job_id}/rerun` creates a new attempt under the same public job ID.
- `POST /v1/jobs/{job_id}/cancel` cancels queued jobs or marks running jobs for cancellation.
- `GET /v1/mentions` lists auto-saved mention evidence for the authenticated user.
- `PATCH /v1/mentions/{mention_id}`, `POST /v1/mentions/{mention_id}/confirm`, and
  `DELETE /v1/mentions/{mention_id}` support review, correction, and soft delete.

Job polling status values are stable: `queued`, `running`, `succeeded`, `partial`, `failed`,
`canceled`, and `expired`. Frontend state should branch only on `status` and public
`JobResponse.error_code`; `current_stage`, `progress`, `attempt_count`, and `error_message` are
display/advisory fields. Exact polling cadence and backoff are frontend-owned in v1.

Public job polling error codes are: `invalid_source_url`, `unsupported_source_kind`,
`no_text_extracted`, `pipeline_error`, `job_canceled`, and `job_expired`. Request validation errors
use `detail.error_code = "validation_error"`.

Public endpoints use Supabase Auth in production (`AUTH_MODE=supabase`). Local development defaults
to `AUTH_MODE=dev`; omit `Authorization` to use `DEV_USER_ID`, or pass
`Authorization: Bearer dev:<uuid>` to simulate a different user.

ASR and multimodal LLM providers are scaffolded as swappable stages. With the default local config,
audio transcription is skipped and visual reconstruction uses OCR output only.

## Optional OpenAI visual extraction

```bash
export OPENAI_API_KEY=...
export MULTIMODAL_LLM_PROVIDER=openai
export OPENAI_MULTIMODAL_MODEL=gpt-5.4-nano
export ASR_PROVIDER=openai
export OPENAI_ASR_MODEL=gpt-4o-mini-transcribe
```

The OpenAI path uses one Responses API call per job with selected frames/images, deterministic crops,
OCR text, and caption context. OCR artifacts are still retained and used as fallback.
When ASR is enabled, the extracted `audio.wav` is sent to OpenAI's audio transcriptions endpoint and
stored as a `transcript` artifact.
