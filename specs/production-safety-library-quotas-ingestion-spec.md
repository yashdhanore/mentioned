# Production Safety, Library, Quota, and Source Hardening Specification

Status: Interview draft

Last updated: 2026-05-02

Purpose: Define the production contract for safe public result exposure, saved mention library
behavior, quota enforcement, and source ingestion hardening for the Mentioned backend.
This file lives under `specs/` with the other task-specific backend specifications.

## Source Basis

This spec is based on:

- The current FastAPI, SQLModel, worker, artifact, and extraction pipeline implementation.
- The current production auth and owner-scoping spec.
- The requested product/security guarantees:
  - Normal users must not receive local paths, raw provider responses, headers, tracebacks, or debug
    payloads.
  - Successful jobs auto-save mentions. Users can list, edit, confirm, and soft-delete their own
    mentions.
  - Per-user burst, daily, active-job, and LLM-call limits are enforced and configurable.
  - Source ingestion is Instagram-only, HTTPS in production, redirect-revalidated, private-IP
    blocked, and uses safe subprocess calls.
- The `grill-me` decision flow: open decisions should be resolved one branch at a time.

## Normative Language

The key words `MUST`, `MUST NOT`, `REQUIRED`, `SHOULD`, `SHOULD NOT`, `RECOMMENDED`, `MAY`, and
`OPTIONAL` in this document are to be interpreted as described in RFC 2119.

`Normal user` means an authenticated public application user. It excludes workers and any future
internal/admin diagnostic role.

`Debug payload` means any payload whose primary purpose is operational diagnosis rather than product
UX, including stage payloads, internal error text, traceback text, provider metadata, raw provider
JSON, HTTP request/response headers, storage keys, or filesystem-derived values.

## Current Implementation Facts

- Public job, result, and saved mention routes already depend on authenticated caller context.
- Jobs and saved mentions are owner-scoped. Cross-user reads and mutations return 404.
- Successful and partial pipeline results call `_auto_save_mentions`, creating owner-scoped saved
  mention rows from schema-valid candidate mentions.
- Saved mention APIs exist for list, detail, update, confirm, and delete.
- Saved mention delete is a soft delete through `save_state = 'deleted'`.
- Saved mention edit and confirm mark `review_status = 'reviewed'`.
- Saved mention list defaults to `save_state = 'active'` and supports category, review status,
  source creator, simple search, sort, limit, and cursor parameters.
- Job creation currently enforces configurable per-user burst, daily-job, and active-job limits.
- LLM input volume is configurable per job through selected frame/image, crop, and call-count
  settings. A per-user LLM-call quota is not yet fully specified in the public contract.
- Normal result reads omit `TextResult.debug`, `StageRun.payload`, `StageRun.error_text`, and
  `Artifact.metadata` because `include_debug` is only enabled for admin callers.
- The result schema still exposes normal-user `stage_runs` and `artifacts` arrays, and artifact
  responses include `storage_backend`. This shape is not yet a final safe public artifact contract.
- Persisted stage payloads, artifact metadata, text debug, provider-call metadata, and artifact
  files may contain local paths, raw provider responses, provider usage, headers, or exception text.
- Public job errors use allowlisted public messages through `PUBLIC_ERROR_MESSAGES`; internal error
  details are stored separately.
- Source URL creation accepts Instagram hosts and Reel/Post paths only. Production defaults to
  requiring HTTPS through `SOURCE_REQUIRE_HTTPS`.
- HTML fetch validates HTTPS, allowed Instagram hosts, blocked private networks, and redirect targets
  before every request.
- Subprocess wrappers use argument lists rather than shell strings.
- Media download currently invokes `yt-dlp` only after URL normalization, but the final downloaded
  paths and any downloader-level redirects are not yet expressed as a formal production contract.

## Required Guarantees

### 1. Safe Result And Artifact Exposure

Normal-user responses MUST be purpose-built product responses. They MUST NOT expose:

- Local filesystem paths or path-like storage keys.
- Raw provider responses.
- HTTP request or response headers.
- Tracebacks, exception class names, stderr dumps, or command output.
- Internal job errors.
- Debug payloads, stage payloads, provider-call metadata, or persisted artifact metadata.
- API keys, bearer tokens, authorization headers, cookies, or credential-shaped values.

Normal users MAY receive extracted text, public job status, public error codes, public error
messages, saved mention evidence, confidence, timestamps, and public object IDs.

Public error messages MUST be allowlisted by error code. A normal user MUST NOT receive `str(exc)`
from arbitrary provider, network, subprocess, parser, database, or filesystem failures.

Internal diagnostic data MAY be retained in persistence and local artifacts, but public API schemas
MUST not depend on it. Any future admin/debug exposure MUST be separately authenticated and MUST
still redact secrets, local paths, raw headers, and raw provider responses unless an explicit
operator-only download/export workflow is specified.

### 2. Auto-Save Library Flow

Successful and partial extraction jobs MUST auto-save every schema-valid candidate mention for the
job owner.

Auto-saved mentions MUST:

- Be owner-scoped to the job owner.
- Start with `save_state = 'active'`.
- Start with `review_status = 'unreviewed'`.
- Preserve extracted fields separately from user-editable display fields.
- Store source job ID, source URL, source platform, optional source creator, optional source context
  snippet, evidence text, structured evidence, confidence, and category.
- Deduplicate only within the same source job and candidate fingerprint.

Users MUST be able to:

- List only their own saved mentions.
- Fetch only their own saved mention details.
- Edit display fields and category for their own saved mentions.
- Confirm their own saved mentions without editing display fields.
- Soft-delete their own saved mentions.

Editing a saved mention MUST mark it `reviewed`. Confirming a saved mention MUST mark it `reviewed`.
Deleting a saved mention MUST set `save_state = 'deleted'`; it MUST NOT hard-delete the row in v1.

The default saved mention list MUST return active mentions only. Deleted mentions MAY be listed only
when the caller explicitly requests `save_state = 'deleted'`.

Cross-user saved mention reads and mutations MUST return 404 and MUST be indistinguishable from
nonexistent mention IDs.

### 3. Quotas And Rate Limits

All user-cost and abuse-control limits MUST be configurable from settings and environment variables.

The backend MUST enforce, per user:

- Burst job creation limit.
- Daily job creation limit.
- Active queued/running job limit.
- LLM-call limit.

Job-creation quota failures MUST return 429 with a safe public error code and message. The response
MUST NOT reveal other users' activity, internal quota tables, provider costs, tracebacks, or exact
database queries.

Quota checks MUST be owner-scoped and MUST count only the authenticated caller's usage.

The active-job quota MUST count queued and running jobs. Terminal jobs MUST NOT count against active
job quota.

The daily job quota SHOULD use a rolling 24-hour window unless a later decision explicitly chooses a
calendar-day boundary.

The LLM-call quota MUST be enforced before making a provider call. The implementation MUST define
which provider stages count as LLM calls, where the usage is recorded, and what fallback behavior is
used when quota is exhausted.

Recommended default behavior for exhausted LLM quota: skip optional multimodal reconstruction, keep
OCR/caption/audio extraction running, return a partial result when useful text exists, and record a
safe warning. This preserves the text-first product while protecting cost.

### 4. Source Ingestion Hardening

The public source ingestion contract MUST remain Instagram-only for v1.

Job creation MUST accept only:

- `https://instagram.com/reel/...`
- `https://www.instagram.com/reel/...`
- `https://instagram.com/p/...`
- `https://www.instagram.com/p/...`

Local development MAY allow `http://` only when production HTTPS enforcement is disabled. Production
MUST reject non-HTTPS source URLs before fetching, probing, or downloading.

All network fetches controlled by application code MUST:

- Disable automatic redirects or otherwise inspect every redirect hop.
- Revalidate each redirect target against the allowed source-host and scheme policy.
- Resolve target hostnames before fetch and reject private, loopback, link-local, multicast,
  unspecified, and otherwise blocked internal networks.
- Limit redirect hops.
- Use bounded timeouts.
- Return safe public errors on failure.

External downloader/prober tools MUST only receive normalized, policy-validated Instagram URLs.

Subprocess calls MUST:

- Use argv lists and `shell=False` behavior.
- Never interpolate user input into shell strings.
- Use bounded working directories under the job artifact directory when possible.
- Capture stdout/stderr for internal diagnostics only.
- Avoid exposing command output, local paths, tracebacks, or stderr to normal users.
- Validate that returned output paths resolve under the job artifact directory before storing or
  processing them.

Downloaded media and generated artifacts MUST remain server-side. Normal users MUST NOT receive
local artifact paths or direct local file URLs.

## Open Decision 1: Normal Result Artifact Shape

Question: Should normal users receive sanitized `stage_runs` and `artifacts` arrays at all, or
should the public result contract remove them and expose only product-level text plus saved mention
evidence?

Recommended answer: remove `stage_runs` and `artifacts` from the normal-user result contract. Keep
them internal/admin-only. Normal users should receive job status, text result fields, warnings,
public error fields, and saved mention evidence through `/v1/mentions`. If the frontend later needs
visual proof, add a purpose-built evidence preview API that returns safe derived data, not artifact
records.

Rationale: a sanitized artifact record is still easy to accidentally expand back into storage
details, provider metadata, or paths. The product object is the saved mention and its evidence, not
the extraction artifact inventory.

## Dependent Decisions To Resolve Later

These depend on the normal result artifact shape decision:

- Whether `GET /v1/jobs/{job_id}/result` should have separate public and internal response schemas.
- Whether `debug=true` should be ignored for normal users, rejected with 403, or removed from the
  public route.
- Whether LLM-call quota should count multimodal reconstruction only, or both ASR and multimodal
  provider calls.
- Whether exhausted LLM quota should skip optional LLM stages or fail the job immediately.
- Whether public mention evidence may include cropped image references later, and if so whether that
  requires signed URLs, derived thumbnails, or no image exposure in v1.

## Acceptance Criteria

- Normal-user API tests prove that result responses contain no local paths, storage keys, raw
  provider responses, headers, tracebacks, stage payloads, artifact metadata, debug payloads, or
  internal errors.
- Saved mention tests prove auto-save on successful and partial jobs, owner-scoped list/detail/edit/
  confirm/delete behavior, edit/confirm review transitions, and soft-delete filtering.
- Quota tests prove burst, daily, active-job, and LLM-call limits are configurable and enforced per
  user.
- Source security tests prove unsupported hosts, spoofed hosts, non-HTTP(S) schemes, non-HTTPS
  production URLs, unsafe redirects, and private-IP resolutions are rejected.
- Subprocess tests or focused unit tests prove user input is passed only as argv entries and returned
  paths are constrained under the job artifact directory.
- Public error tests prove provider, subprocess, filesystem, and unexpected exceptions map to safe
  public error codes/messages without leaking exception details.
