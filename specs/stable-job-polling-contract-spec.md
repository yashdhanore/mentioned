# Stable Job Polling Contract Specification

Status: Interview draft

Last updated: 2026-05-02

Purpose: Define the stable public contract the frontend may rely on when creating jobs, polling job
status, deciding when to fetch results, and rendering public job errors. This file is intentionally
separate from `spec.md`.

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

## Decision Log

1. The frontend polling state machine MUST depend only on public `status` and public `error_code`.
2. The public status set MUST be exactly `queued`, `running`, `succeeded`, `partial`, `failed`,
   `canceled`, and `expired` until a new contract version is written.
3. `GET /v1/jobs/{job_id}` is the canonical polling endpoint.
4. `GET /v1/jobs` MUST use the same public status and error semantics as single-job polling.
5. `GET /v1/jobs/{job_id}/result` is a result-fetch endpoint, not the canonical polling source.
6. `current_stage`, `progress`, `attempt_count`, `error_message`, timestamps, and links are
   advisory presentation fields. The frontend MAY display them, but MUST NOT branch its job state
   machine on them.
7. `partial` is a terminal usable-result state, not a failure state.
8. Public `error_code` MUST be a low-cardinality, stable enum that is safe for frontend branching,
   analytics, localization, and support documentation.
9. Internal stage/provider/subprocess errors MUST NOT leak into public polling as new ad hoc
   `error_code` values.
10. Non-terminal jobs SHOULD expose `error_code = null`; retry-attempt diagnostics should use a
    separate internal field, stage-run debug data, or admin/debug result surfaces.
11. Public `error_message` is display fallback copy only. It is not a stable branching contract.
12. Adding response fields is backward compatible; changing status meanings, removing public error
    codes, or emitting new public status values requires an explicit contract update.

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

### `running`

The job has been claimed by a worker and extraction is in progress.

Frontend behavior:

- Show an in-progress state.
- Continue polling.
- Do not require `current_stage` or `progress` to advance correctly.
- Treat `error_code` as `null` for state-machine purposes.

Backend requirements:

- Worker claim MUST transition `queued` to `running`.
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

The job reached a terminal canceled state.

Frontend behavior:

- Stop polling.
- Show a canceled state.
- Treat `error_code = job_canceled` as the stable public reason.

Backend requirements:

- Public `error_code` MUST be `job_canceled`.
- Canceling an already terminal job MUST be idempotent and return the existing terminal state.

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

Request-level codes do not imply that a job row exists. For example, a rejected `POST /v1/jobs`
request SHOULD return an HTTP error and SHOULD NOT create a pollable failed job unless a separate
product decision changes that behavior.

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

## Polling Behavior

- The backend SHOULD make `GET /v1/jobs/{job_id}` cheap enough for normal short-interval polling.
- The frontend SHOULD poll only while status is `queued` or `running`.
- The frontend SHOULD stop polling immediately when it observes `succeeded`, `partial`, `failed`,
  `canceled`, or `expired`.
- The frontend SHOULD tolerate repeated identical responses.
- The frontend SHOULD tolerate transient network/server errors with client-side backoff, but those
  transport failures are not job statuses.
- The backend MAY add server-provided polling hints later, but polling hints MUST be optional.

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

## Implementation Gaps To Close

1. Requeued retryable jobs currently can expose a non-null `job.error_code` while their public
   status is `queued`.
   - Recommended fix: keep retry diagnostics internal or move them to a separate non-contract field.
2. Internal retryable codes are listed in `RETRYABLE_ERROR_CODES`, but not all are public polling
   codes.
   - Recommended fix: normalize any terminal internal failure to `pipeline_error` unless this spec
     explicitly promotes that code.
3. `JobResultResponse` does not include `error_code`.
   - Recommended decision: keep `GET /v1/jobs/{job_id}` as the canonical polling source. Only add
     `error_code` to result responses if the frontend has a concrete need to render terminal errors
     from the result endpoint alone.
4. Running-job cancellation currently has request semantics, but the worker path does not yet prove
   terminal `canceled` semantics.
   - Recommended fix: make cancellation either explicitly best-effort in the public contract or teach
     the worker/pipeline to observe cancellation and persist `status = canceled` with
     `error_code = job_canceled`.

## Acceptance Criteria

- Tests assert that every public job response status is one of the seven stable statuses.
- Tests assert that `queued`, `running`, and `succeeded` job responses expose `error_code = null`.
- Tests assert that `failed`, `canceled`, and `expired` job responses expose stable non-null public
  error codes.
- Tests assert that retryable internal failures do not leak stage-specific codes through
  `JobResponse.error_code` while the job is requeued.
- Tests assert that terminal internal failures map to `pipeline_error` unless they are explicitly
  listed in this spec.
- Tests assert that `partial` is terminal and treated as a usable result state.
- Tests assert that cancellation has documented semantics for both queued and running jobs.
- API documentation lists the seven statuses and the public error-code tables from this spec.

## Grill-Me Decision Pass

Question: Should the frontend branch on `current_stage` because it is more detailed than `status`?

Recommended answer: no. `current_stage` is operational detail and can change with the extraction
pipeline. The stable UI state should come from `status`.

Question: Should the frontend branch on `progress` thresholds?

Recommended answer: no. Progress is presentation-only. The backend can improve or replace progress
calculation without breaking the frontend if state transitions depend only on `status`.

Question: Should `partial` be displayed as a failure?

Recommended answer: no. `partial` is a terminal usable-result state. Missing extraction channels
should be represented as warnings or evidence gaps, not as job failure.

Question: Should stage-specific failures become public error codes?

Recommended answer: no for v1. Keep the public taxonomy small. Promote a stage-specific code only
when the frontend needs distinct user copy or action for that exact condition.

Question: Should request validation errors create failed jobs so every error can be polled?

Recommended answer: no. Invalid submissions should fail the `POST /v1/jobs` request and avoid
creating job rows. Polling begins only after a job is accepted.

Question: Should result fetching replace job polling?

Recommended answer: no. Keep job polling canonical. Fetch results after `succeeded` or `partial`.
