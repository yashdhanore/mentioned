# Stable Job Polling Contract Specification

Status: Replanned draft

Last updated: 2026-05-03

Purpose: Define the stable public contract the frontend may rely on when creating jobs, polling job
status, deciding when to fetch results, and rendering public job errors. This file is intentionally
separate from `spec.md` and lives under `specs/` with the other task-specific backend
specifications.

## Current Implementation Facts

- `app.models.JOB_STATUSES` already defines the public job statuses as `queued`, `running`,
  `succeeded`, `partial`, `failed`, `canceled`, and `expired`.
- `app.models.TERMINAL_JOB_STATUSES` treats `succeeded`, `partial`, `failed`, `canceled`, and
  `expired` as terminal.
- `JobResponse` is returned from `POST /v1/jobs`, `GET /v1/jobs`, `GET /v1/jobs/{job_id}`,
  `POST /v1/jobs/{job_id}/rerun`, and `POST /v1/jobs/{job_id}/cancel`.
- `JobResponse` includes operational fields such as `current_stage`, `progress`, `attempt_count`,
  `error_message`, and `links`, but the frontend should not need those fields to implement its
  state machine.
- `JobResultResponse` includes `status`, `current_stage`, and `progress`, but currently does not
  include `error_code`.
- V1 keeps job-level `error_code` only on `JobResponse`; `/result` is not a job-error source.
- `StageRunResponse` also has an `error_code`, but stage-run errors are result/debug evidence, not
  the frontend polling contract.
- The coordinator has public messages for `invalid_source_url`, `unsupported_source_kind`,
  `pipeline_error`, `no_text_extracted`, `job_canceled`, `job_expired`, `quota_exceeded`, and
  `rate_limited`.
- The coordinator also has internal retryable failure codes such as `source_fetch_failed`,
  `source_probe_failed`, `source_download_failed`, `media_processing_failed`, `asr_failed`,
  `ocr_failed`, and `visual_reconstruction_failed`.
- `fail_claimed_job` can currently requeue a retryable job while leaving `job.error_code` populated
  with the failed attempt's code.
- Canceling a queued job currently transitions it to `canceled`; canceling a running job records a
  cancellation request, but the inspected worker path does not yet prove an eventual `canceled`
  transition.
- `record_pipeline_result` maps unknown result statuses to `failed`, but currently accepts any value
  in `JOB_STATUSES`, including non-terminal statuses such as `queued` and `running`.
- FastAPI/Pydantic validation failures, such as unknown request fields, can return a 422 response
  that is not shaped as `detail.error_code`.
- Current tests cover owner scoping, retry/rerun behavior, result child owner filtering, auth errors,
  and source validation, but there is not yet a focused polling-contract test file.

## Decision Log

1. The frontend polling state machine MUST depend only on public `status` and public `error_code`.
   `status` decides behavior. `error_code` decides terminal error copy/action.
2. The public status set MUST be exactly `queued`, `running`, `succeeded`, `partial`, `failed`,
   `canceled`, and `expired` until a new contract version is written.
3. `GET /v1/jobs/{job_id}` is the only required frontend polling endpoint.
4. `GET /v1/jobs` MUST use the same public status and error semantics as single-job polling.
5. `GET /v1/jobs/{job_id}/result` is a heavier result-fetch endpoint. The frontend SHOULD call it
   only after `GET /v1/jobs/{job_id}` returns `succeeded` or `partial`.
   - V1 `JobResultResponse` SHOULD NOT add job-level `error_code`.
   - The frontend MUST use `JobResponse.error_code` from `GET /v1/jobs/{job_id}` for terminal
     error handling.
6. `current_stage`, `progress`, `attempt_count`, `error_message`, timestamps, and links are
   display/advisory fields. The frontend MAY display them, but MUST NOT branch its job state
   machine on them.
7. `partial` is a terminal usable-result state, not a failure state.
   - The frontend MUST stop polling and show the result for `partial`.
   - Warnings and evidence gaps belong in the result UI, not in terminal error handling.
8. Public `error_code` MUST be a low-cardinality, stable enum that is safe for frontend branching,
   analytics, localization, and support documentation.
   - Job polling error codes MUST be allowlisted.
   - Internal codes are promoted to public only when the frontend needs distinct user copy or action.
9. Internal stage/provider/subprocess errors MUST NOT leak into public polling as new ad hoc
   `error_code` values.
10. Non-terminal jobs SHOULD expose `error_code = null`; retry-attempt diagnostics should use a
    separate internal field, stage-run debug data, or admin/debug result surfaces.
    - This is a MUST for `queued` and `running`.
    - A failed retry attempt MUST NOT leave a public `error_code` on the requeued job.
11. Public `error_message` is display fallback copy only. It is not a stable branching contract.
12. Adding response fields is backward compatible; changing status meanings, removing public error
    codes, or emitting new public status values requires an explicit contract update.
13. Pipeline completion MUST only persist terminal statuses. A pipeline result MUST NOT be able to
    write `queued` or `running` as a completed job status.
    - Completion MAY write only `succeeded`, `partial`, or `failed`.
    - `queued`, `running`, or unknown final statuses MUST be coerced to `failed`.
    - Coerced failures MUST use public `pipeline_error` unless a more specific public error is
      already valid.
14. Running-job cancellation MUST have explicit semantics. The recommended target is eventual
    terminal cancellation through worker/pipeline cancellation checks.
    - `canceled` means cancellation definitely happened and is terminal.
    - `POST /v1/jobs/{job_id}/cancel` for a running job MAY return the current `running` state after
      recording `cancel_requested_at`.
    - The worker/pipeline MUST later move the job to `canceled` with `error_code = job_canceled`
      when it observes cancellation at a safe boundary.
    - Until the status becomes `canceled`, the frontend must continue polling the visible `status`.
15. Request-level validation errors MUST use the same public error-envelope shape as coordinator
    errors.
    - Generic FastAPI/Pydantic validation failures MUST return public `validation_error`.
    - Detailed validation internals MUST stay out of the public response unless field-level UI is
      intentionally specified later.
16. V1 MUST keep accepted-job asynchronous processing with polling instead of holding the original
    `POST /v1/jobs` request open until extraction finishes.
    - Accepted means the API has validated and stored the job, not that extraction is complete.
    - The create response should be `202 Accepted` with a `job_id` the frontend can use to check
      status.
    - A held request is still a long-lived synchronous client/server interaction.
    - Extraction can depend on network fetches, media download, ffmpeg, OCR, ASR, multimodal LLMs,
      retries, and stale-worker recovery.
    - Polling preserves durable job ownership, idempotency, retry/rerun, cancel, resume-after-refresh,
      and worker recovery semantics.
    - A future push transport such as SSE, WebSockets, webhooks, or mobile push MAY be added as an
      optional notification layer over the same job state machine.

## Public Status Contract

### `queued`

The job is accepted and waiting to be claimed or retried.

Frontend behavior:

- Show a pending state.
- Continue polling.
- Do not fetch the result as a required user-visible step.
- Treat `error_code` as `null` for state-machine purposes.

Backend requirements:

- A newly accepted job MUST start as `queued`.
- A rerun MUST reset the same public `job_id` to `queued`.
- A retryable failed attempt MAY move the job back to `queued`, but SHOULD NOT expose the failed
  attempt as public `job.error_code`.
- A queued job MUST expose `error_code = null`.

### `running`

The job has been claimed by a worker and extraction is in progress.

Frontend behavior:

- Show an in-progress state.
- Continue polling.
- Do not require `current_stage` or `progress` to advance correctly.
- Treat `error_code` as `null` for state-machine purposes.

Backend requirements:

- Worker claim MUST transition `queued` to `running`.
- A running job MUST expose `error_code = null`.
- `current_stage` and `progress` MAY change while running, but their values are not stable public
  states.

### `succeeded`

The job completed and produced a usable complete result.

Frontend behavior:

- Stop polling.
- Fetch or render `/v1/jobs/{job_id}/result`.
- Treat `error_code` as `null`.

Backend requirements:

- The result endpoint MUST be able to return the text-first result for an owned succeeded job.
- Public `error_code` MUST be `null`.

### `partial`

The job completed and produced a usable result with recoverable extraction gaps.

Frontend behavior:

- Stop polling.
- Fetch or render `/v1/jobs/{job_id}/result`.
- Present the result as usable, with warnings where available.
- Do not treat the job as failed.
- Do not branch on `error_code` for normal `partial` handling.

Backend requirements:

- Partial completion MUST be terminal.
- Public `error_code` SHOULD be `null` for v1. Warnings belong in the result payload.

### `failed`

The job reached a terminal failure state and no usable result is guaranteed.

Frontend behavior:

- Stop polling.
- Branch on public `error_code`.
- Show a generic failure UI when the code is unknown to the current frontend.
- MAY offer rerun when product policy allows it.

Backend requirements:

- Public `error_code` MUST be non-null.
- Internal failures MUST be mapped to a stable public code before exposure.
- `internal_error` and raw provider/subprocess output MUST NOT be exposed through public polling.

### `canceled`

The job reached a terminal canceled state. `canceled` means cancellation definitely happened; it does
not mean "cancel requested."

Frontend behavior:

- Stop polling.
- Show a canceled state.
- Treat `error_code = job_canceled` as the stable public reason.

Backend requirements:

- Public `error_code` MUST be `job_canceled`.
- Canceling an already terminal job MUST be idempotent and return the existing terminal state.
- Canceling a queued job MUST immediately transition to `canceled`.
- Canceling a running job MAY initially return `running`, but MUST persist a cancellation request for
  the worker/pipeline to observe.
- Once the worker/pipeline observes cancellation, it MUST persist `status = canceled`,
  `error_code = job_canceled`, `progress = 1.0`, and `finished_at`.

### `expired`

The job reached a terminal timeout/stale-worker exhaustion state.

Frontend behavior:

- Stop polling.
- Show an expired/retryable-later state.
- Treat `error_code = job_expired` as the stable public reason.

Backend requirements:

- Public `error_code` MUST be `job_expired`.
- Expiration MUST be terminal.

## Public Error Code Contract

There are two public error-code surfaces:

- Job polling error codes: `JobResponse.error_code`.
- Request error codes: HTTP error payloads in `detail.error_code`.

The frontend may share rendering/localization for both surfaces, but the backend MUST document which
surface can emit each code.

`JobResultResponse` is not a job-level error-code surface in v1. Result `stage_runs` may contain
stage-level `error_code` values, but those are evidence/debug details and MUST NOT drive the
frontend polling state machine.

### Job Polling Error Codes

These codes are stable for `JobResponse.error_code`:

| Code | Emitted with status | Meaning | Frontend action |
| --- | --- | --- | --- |
| `invalid_source_url` | `failed` | The queued source URL is syntactically invalid or cannot be treated as an allowed URL. | Ask for a new URL. |
| `unsupported_source_kind` | `failed` | The source is outside the supported public Instagram Reel/Post contract, including unsupported redirect targets. | Ask for a supported Instagram Reel/Post URL. |
| `no_text_extracted` | `failed` | Extraction ran but no useful text was found. | Explain that nothing useful was extracted; allow rerun only if useful. |
| `pipeline_error` | `failed` | Extraction failed for an implementation/provider/system reason that is not separately actionable. | Show a generic failure and optionally offer retry/rerun. |
| `job_canceled` | `canceled` | The job was canceled. | Show canceled state. |
| `job_expired` | `expired` | The worker did not finish before retry/staleness policy was exhausted. | Show expired state and optionally offer rerun. |

Backend requirements:

- `JobResponse.error_code` MUST be `null` for `queued`, `running`, and `succeeded`.
- `JobResponse.error_code` SHOULD be `null` for `partial` in v1.
- `JobResponse.error_code` MUST be non-null for `failed`, `canceled`, and `expired`.
- Unknown internal failures MUST map to `pipeline_error`.
- Stage-specific failures such as `asr_failed`, `ocr_failed`, or `visual_reconstruction_failed`
  MUST remain internal unless a future spec promotes them to this public table.
- A new public job polling error code MUST NOT be emitted until the frontend has distinct user copy
  or action for it and this table is updated.

### Request Error Codes

These codes are stable for HTTP `detail.error_code`:

| Code | Typical HTTP status | Meaning |
| --- | --- | --- |
| `invalid_source_url` | 422 | The submitted source URL is invalid. |
| `unsupported_source_kind` | 422 | The submitted source is not a supported public Instagram Reel/Post URL. |
| `not_found` | 404 | The object does not exist or is not owned by the authenticated caller. |
| `idempotency_conflict` | 409 | The idempotency key belongs to the same caller but a different source URL. |
| `invalid_transition` | 409 | The requested transition is not valid for the current job status. |
| `quota_exceeded` | 429 | The caller has exceeded configured job quota. |
| `rate_limited` | 429 | The caller created jobs too quickly. |
| `pipeline_error` | 400/500 class | Generic coordinator error fallback. |
| `validation_error` | 422 | The request body, path, or query parameters failed public validation. |

Request-level codes do not imply that a job row exists. For example, a rejected `POST /v1/jobs`
request SHOULD return an HTTP error and SHOULD NOT create a pollable failed job unless a separate
product decision changes that behavior.

Current implementation note: coordinator-raised errors already use `detail.error_code`, but generic
FastAPI/Pydantic validation errors are not yet normalized into this envelope. They MUST be mapped to
`validation_error` so the frontend has one predictable request-error shape.

## Frontend State Machine

The frontend state machine should be equivalent to:

```text
queued/running -> keep polling
succeeded/partial -> stop polling and fetch/render result
failed/canceled/expired -> stop polling and render terminal state using error_code
unknown status -> stop optimistic handling, show generic unsupported state, and report telemetry
unknown error_code -> show generic message for the known terminal status and report telemetry
```

The frontend MUST NOT need to parse:

- `current_stage`
- `progress`
- `attempt_count`
- `error_message`
- `stage_runs`
- artifact metadata
- provider/debug payloads

The frontend MAY display `current_stage`, `progress`, `attempt_count`, `error_message`, timestamps,
or links, but these fields MUST NOT determine whether the frontend keeps polling, fetches results,
shows a terminal error, or offers rerun/cancel actions.

## Polling Behavior

- The backend SHOULD make `GET /v1/jobs/{job_id}` cheap enough for normal short-interval polling.
- The frontend MUST use `GET /v1/jobs/{job_id}` as the required v1 polling endpoint.
- The frontend SHOULD NOT poll `GET /v1/jobs/{job_id}/result`.
- The frontend SHOULD call `GET /v1/jobs/{job_id}/result` after polling observes `succeeded` or
  `partial`.
- The frontend SHOULD poll only while status is `queued` or `running`.
- The frontend SHOULD stop polling immediately when it observes `succeeded`, `partial`, `failed`,
  `canceled`, or `expired`.
- Exact polling cadence and backoff timing are frontend-owned in v1.
- The frontend SHOULD tolerate repeated identical responses.
- The frontend SHOULD tolerate transient network/server errors with client-side backoff, but those
  transport failures are not job statuses.
- The backend MAY add server-provided polling hints later, but polling hints MUST be optional.

## Why Not Hold The Create Request Open?

`POST /v1/jobs` should accept work and return quickly with a durable `job_id`. The extraction itself
should run outside the request/response lifecycle.

Required v1 flow:

```text
1. Frontend sends POST /v1/jobs with the source URL.
2. Backend validates ownership, source URL, idempotency, and quotas.
3. Backend stores a durable job row with status = queued.
4. Backend immediately returns 202 Accepted with job_id and status = queued.
5. Worker processes the job in the background.
6. Frontend calls GET /v1/jobs/{job_id} until the status is terminal.
7. When status is succeeded or partial, frontend fetches GET /v1/jobs/{job_id}/result.
```

Holding the create request open until extraction finishes is not recommended for v1 because:

- It couples user-visible latency to slow and failure-prone external work.
- Browser, proxy, platform, and load-balancer timeouts can kill the request even if the worker keeps
  running.
- A page refresh, app backgrounding, network switch, or mobile sleep can lose the in-flight response.
- Retrying the request becomes ambiguous without durable idempotency and job lookup.
- Cancellation, rerun, stale-worker recovery, and result fetching still need persisted job state.
- Long-held API workers reduce backend capacity and make operational behavior harder to reason
  about.

The backend MAY still offer a convenience `wait=true` or bounded long-poll endpoint later, but it
MUST be optional and layered on top of the same durable job record. It MUST NOT replace the stable
job polling contract.

## Compatibility Rules

- New public status values MUST NOT be emitted without updating this spec and frontend handling.
- New public job polling error codes MUST NOT be emitted without updating this spec and frontend
  handling.
- Existing public error codes MUST NOT be renamed.
- A public error code MAY be deprecated only after the backend stops emitting it and the frontend has
  had a compatibility window.
- `error_message` copy MAY change without a contract revision.
- `current_stage` values MAY change without a contract revision.
- `progress` calculation MAY change without a contract revision.

## Replanned Implementation Plan

### Phase 1: Centralize Public Error Codes

Add an explicit public job error-code allowlist near the coordinator contract:

```text
invalid_source_url
unsupported_source_kind
no_text_extracted
pipeline_error
job_canceled
job_expired
```

Recommended implementation:

- Add `PUBLIC_JOB_ERROR_CODES`.
- Add a helper such as `public_job_error_code(error_code: str | None) -> str | None`.
- Return `None` for `None`.
- Return the input when it is in `PUBLIC_JOB_ERROR_CODES`.
- Map every other internal/unknown failure code to `pipeline_error`.
- Keep request-level codes such as `quota_exceeded`, `rate_limited`, `not_found`,
  `idempotency_conflict`, `invalid_transition`, and `validation_error` out of
  `JobResponse.error_code` unless a future spec promotes them.

Rationale: `PUBLIC_ERROR_MESSAGES` currently controls message safety, but it does not prevent an
unstable internal code from reaching `JobResponse.error_code`.

### Phase 2: Enforce Non-Terminal Error Semantics

Update status transitions so public non-terminal jobs do not carry public errors.

Required changes:

- `create_job` and `rerun_job` keep `error_code = null`.
- `claim_next_job` keeps clearing `error_code`, `error_message`, and `internal_error`.
- `fail_claimed_job` with a retryable failure and remaining attempts MUST requeue with
  `error_code = null` and `error_message = null`.
- Any internal retry diagnostic for a requeued job MUST stay in `internal_error`, stage runs,
  logs, or a future admin/debug surface.
- `recover_stale_jobs` SHOULD explicitly clear public error fields when requeueing stale jobs.

Rationale: the frontend should not see a job as both `queued` and failed.

### Phase 3: Guard Pipeline Finalization

Update `record_pipeline_result` so pipeline completion can only persist terminal statuses.

Required behavior:

- Accept `succeeded`, `partial`, and `failed` from the pipeline.
- Treat any non-terminal final status such as `queued` or `running` as `failed`.
- Treat any unknown final status as `failed`.
- Map a non-terminal or unknown final-status failure to `pipeline_error` unless a more specific
  public code is already valid.
- Keep `no_text` -> `no_text_extracted`.

Rationale: `queued` and `running` are active polling states. Persisting them from a completed
pipeline would make the frontend poll indefinitely or render contradictory completion metadata.

### Phase 4: Implement Running Cancellation

The decided target is strong eventual cancellation:

- `POST /v1/jobs/{job_id}/cancel` for a queued job immediately returns `canceled` with
  `error_code = job_canceled`.
- `POST /v1/jobs/{job_id}/cancel` for a running job records cancellation and may return the current
  `running` response.
- The worker/pipeline checks cancellation at safe boundaries.
- Once observed, the job transitions to `canceled` with `error_code = job_canceled`,
  `progress = 1.0`, and `finished_at` set.

Alternative: document running cancellation as best-effort and allow a requested running job to still
finish as `succeeded`, `partial`, or `failed`. This is simpler, but weaker for frontend UX.

Decision: implement strong eventual cancellation before treating `canceled` as fully proved for
running jobs.

### Phase 5: Normalize Request Validation Errors

Add a FastAPI validation exception handler that maps generic validation errors to:

```json
{"detail": {"error_code": "validation_error", "message": "The request is not valid."}}
```

Keep detailed field validation data internal unless there is a product need for safe field-level
errors.

Rationale: coordinator errors already have a stable envelope, but framework validation errors do
not.

### Phase 6: Add Focused Contract Tests

Add `tests/test_job_polling_contract.py` for the public polling contract. Keep it mostly coordinator
level for deterministic state setup, with a few API tests for response envelopes.

Minimum tests:

- The model status tuple equals the seven public statuses in this spec.
- Created jobs return `queued` with `error_code = null`.
- Claimed jobs return `running` with `error_code = null`.
- Retried jobs return `queued` with `error_code = null`.
- Rerun resets terminal jobs to `queued` with `error_code = null`.
- Successful results return `succeeded` with `error_code = null`.
- Partial results return `partial`, are terminal, and have `error_code = null`.
- No-text results return `failed` with `error_code = no_text_extracted`.
- Unknown/internal terminal failures return `failed` with `error_code = pipeline_error`.
- Pipeline final statuses `queued` and `running` are coerced to `failed`.
- Queued cancellation returns `canceled` with `error_code = job_canceled`.
- Running cancellation behavior is tested according to the final decision in Phase 4.
- Stale jobs with exhausted attempts return `expired` with `error_code = job_expired`.
- Unknown request fields return the chosen request-level error envelope if Phase 5 is implemented.
- Unknown request fields return `detail.error_code = validation_error`.

### Phase 7: Update Public Docs

Update README/API docs after implementation:

- List the seven statuses.
- List public `JobResponse.error_code` values.
- State that `GET /v1/jobs/{job_id}` is the canonical polling endpoint.
- State that `JobResponse.error_code`, not `JobResultResponse`, is the v1 job-error source.
- State that exact polling cadence is frontend-owned in v1.
- State that `current_stage`, `progress`, and result `stage_runs` are not frontend state-machine
  inputs.

## Acceptance Criteria

- Tests assert that every public job response status is one of the seven stable statuses.
- Tests assert that `queued`, `running`, and `succeeded` job responses expose `error_code = null`.
- Tests assert that retried/requeued jobs expose `error_code = null`.
- Tests assert that `failed`, `canceled`, and `expired` job responses expose stable non-null public
  error codes.
- Tests assert that retryable internal failures do not leak stage-specific codes through
  `JobResponse.error_code` while the job is requeued.
- Tests assert that terminal internal failures map to `pipeline_error` unless they are explicitly
  listed in this spec.
- Tests assert that pipeline completion cannot persist `queued` or `running`.
- Tests assert that `partial` is terminal and treated as a usable result state.
- Tests assert that cancellation has documented semantics for both queued and running jobs.
- Tests assert that request validation errors use `detail.error_code = validation_error`.
- API documentation lists the seven statuses and the public error-code tables from this spec.

## Grill-Me Decision Pass

Question: Should the frontend branch on `current_stage` because it is more detailed than `status`?

Decision: no. `current_stage` is operational detail and can change with the extraction
pipeline. The stable UI state should come from `status`.

Question: Should the frontend branch on `progress` thresholds?

Decision: no. Progress is presentation-only. The backend can improve or replace progress
calculation without breaking the frontend if state transitions depend only on `status`.

Question: Should `partial` be displayed as a failure?

Decision: no. `partial` is a terminal usable-result state. Missing extraction channels
should be represented as warnings or evidence gaps, not as job failure.

Question: Should stage-specific failures become public error codes?

Decision: no for v1. Keep the public taxonomy small. Promote a stage-specific code only
when the frontend needs distinct user copy or action for that exact condition.

Question: Should request validation errors create failed jobs so every error can be polled?

Recommended answer: no. Invalid submissions should fail the `POST /v1/jobs` request and avoid
creating job rows. Polling begins only after a job is accepted.

Question: Should result fetching replace job polling?

Decision: no. Keep `GET /v1/jobs/{job_id}` as the required polling endpoint. Fetch results only
after `succeeded` or `partial`.

Question: Should `/v1/jobs/{job_id}/result` include job-level `error_code`?

Decision: no for v1. Keep job-level `error_code` only on `JobResponse`. The frontend polls
`GET /v1/jobs/{job_id}` for status/error and fetches `/result` only for `succeeded` or `partial`,
where job-level `error_code` should be `null` anyway.

Question: Should the spec define exact polling cadence and backoff timing?

Decision: no for v1. Exact cadence is frontend-owned. The backend contract defines only the behavior
boundaries: poll only while `queued` or `running`, stop on terminal statuses, tolerate repeated
responses, use client-side backoff on transport errors, and treat any future server-provided polling
hints as optional.

Question: Why not make `POST /v1/jobs` async and return the final response when extraction is done?

Decision: do not hold the create request open for v1. Return `202 Accepted` with a durable
`job_id`, then let the frontend poll. A long-held request would still be synchronous from the
client's point of view, and it is brittle across media download, OCR/ASR/LLM latency, retries,
browser refresh, mobile backgrounding, proxy timeouts, and worker recovery. A bounded long-poll or
push notification layer can be added later without changing the durable job state machine.

Question: Should `record_pipeline_result` accept every value in `JOB_STATUSES`?

Decision: no. Pipeline completion should only write terminal statuses. `queued` and `running` are
active polling states and should never be persisted by a completed pipeline result. `queued`,
`running`, or unknown final statuses should be coerced to `failed` with public `pipeline_error`
unless a more specific public error is already valid.

Question: Should retry-attempt failures be exposed as `JobResponse.error_code` while the job is
requeued?

Decision: no. A requeued job is still active work. Keep retry diagnostics internal and
reserve public `error_code` for terminal or rejected-request states.

Question: Should running-job cancellation be best-effort or eventually terminal?

Decision: eventually terminal. `canceled` means cancellation definitely happened. Returning
`running` immediately after a cancel request is acceptable, but the worker/pipeline must observe
cancellation and persist `canceled` with `job_canceled` when it reaches a safe boundary.

Question: Should generic FastAPI validation failures get a stable request-level `error_code`?

Decision: yes. Use `validation_error` so the frontend has one predictable request-error shape. Keep
detailed validation internals out of the public contract unless field-level product copy is needed
later.
