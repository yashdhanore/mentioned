# Production Auth + Owner Scoping Specification

Status: Resolved and implemented

Last updated: 2026-05-02

Purpose: Define the production authentication and owner-scoping contract for the Mentioned backend.
This file lives under `specs/` with the other task-specific backend specifications.

## Current Implementation Facts

- FastAPI routes for jobs, results, and mentions already depend on `CallerDep`.
- `app/auth.py` supports local dev auth and Supabase JWT auth, and production settings fail fast unless `AUTH_MODE=supabase`.
- `jobs.owner_id`, `saved_mentions.owner_id`, and result child `owner_id` fields exist in the SQLModel schema.
- Job creation, job listing, idempotency, quotas, saved mentions, and job/result fetches are already filtered by caller ownership in `JobCoordinator`.
- Cross-user job reads currently return 404 through `NotFoundError`.
- Result storage rows (`text_results`, `artifacts`, `job_stage_runs`, and `provider_calls`) carry direct `owner_id`, copied from the canonical job.
- Public result reads resolve the owned job first, then fetch child rows by both `job_id` and `owner_id`.
- The auth hardening migration enables RLS policies for every owner-scoped table using `app.current_user_id`.
- Local development allows `AUTH_MODE=dev`, including omitted `Authorization`, mapped to `DEV_USER_ID`, but production does not.

## Decision Log

1. Result-related persistence rows MUST carry `owner_id` directly.
   - Applies to `text_results`, `artifacts`, `job_stage_runs`, and `provider_calls`.
   - `jobs.owner_id` remains the canonical owner.
   - API result reads still MUST resolve through an owned job and return 404 for other users.
   - Direct `owner_id` exists for RLS, auditing, cleanup, future queries, and accidental query safety.
2. Production MUST fail fast unless `AUTH_MODE=supabase`.
   - `AUTH_MODE=dev` remains allowed for local/test only.
   - In production, every non-health endpoint MUST require a valid bearer token.
   - Missing credentials MUST NOT silently map to `DEV_USER_ID` in production.
3. Public API auth MUST accept only Supabase user access tokens.
   - Required claims/validation: valid issuer, valid audience, valid expiry, non-empty `sub`.
   - `role=authenticated` MUST be accepted when present; anon or service-role-style tokens MUST be rejected.
   - Expired tokens, unsupported algorithms, missing subjects, and tokens from other Supabase projects MUST be rejected.
4. Production MUST enforce owner scope with both application filters and Postgres RLS.
   - Application-level owner filters remain mandatory and define 404 behavior.
   - RLS MUST be enabled on every table with `owner_id`: `jobs`, `text_results`, `artifacts`, `job_stage_runs`, `provider_calls`, and `saved_mentions`.
   - The implementation MUST document and test how the verified FastAPI caller reaches RLS policies.
5. FastAPI MUST pass the verified user id into Postgres RLS with a transaction-local setting.
   - Use a setting such as `app.current_user_id`.
   - RLS policies MUST compare `owner_id` to that setting.
   - The value MUST come from the verified Supabase user `sub`, not from request body/query/header user input.
6. Workers MUST use separate internal database access under RLS.
   - Worker access may bypass user RLS only for worker responsibilities.
   - Worker responsibilities include claiming queued jobs, heartbeats, retries, failures, and writing result/mention rows.
   - Worker writes MUST copy `owner_id` from the canonical job row.
   - Worker code MUST NOT accept public user bearer tokens or invent owner ids.
7. Public API responses MUST NOT include `owner_id`.
   - `owner_id` is a persistence, authorization, RLS, audit, cleanup, and internal diagnostic field.
   - `JobResponse`, `JobResultResponse`, and `SavedMentionResponse` MUST omit `owner_id`.
8. Authenticated cross-user object access MUST return 404.
   - Applies to job, result, and saved mention detail/mutation endpoints.
   - List endpoints MUST silently exclude other users' rows.
   - Cross-user objects and nonexistent objects MUST be indistinguishable to public callers.
9. Unauthenticated or invalid production API requests MUST return 401.
   - Missing, malformed, expired, invalid, wrong-project, anon, or service-role-style public bearer tokens MUST return 401.
   - Authenticated-but-not-owner object access returns 404.
   - Health endpoints MAY remain public if they reveal no user data.
10. Auth hardening MUST use a new Alembic migration.
    - Existing migrations MUST remain intact.
    - The new migration MUST add and backfill `owner_id` on result tables.
    - The new migration MUST make those columns non-null, add useful owner indexes, enable RLS, and update policies to use `app.current_user_id`.
11. Public result child-table reads MUST filter by both `job_id` and `owner_id`.
    - `get_result` MUST first resolve an owned job.
    - Public reads of `text_results`, `artifacts`, and `job_stage_runs` MUST include `job_id = job.id` and `owner_id = caller.subject_id`.
    - Future public reads of `provider_calls` MUST follow the same rule.
12. Public Supabase auth MUST always produce user callers.
    - Supabase user tokens become `Caller(role="user")`.
    - Public Supabase tokens MUST NOT produce `Caller(role="admin")`.
    - Admin/debug access is out of scope unless later implemented through a separate internal auth path with explicit allowlisting.
13. Completion requires focused security and persistence tests.
    - Tests MUST cover production auth-mode refusal, 401 behavior, Supabase token rejection paths, cross-user 404 behavior, owner-scoped lists, result child `owner_id` persistence, owner-filtered result child reads, worker owner copying, and migration/RLS SQL using `app.current_user_id`.
14. Implementation should begin immediately after this final spec pass.
    - Keep `spec.md` untouched.
    - Implement narrowly against the resolved decisions in this file.

## Decision 1: Result Ownership Model

Question: Should every persisted result-related row carry its own `owner_id`, or is it enough that results are only reachable through an owned job?

Decision: add `owner_id` to every persisted user-data table that can contain or expose user-owned extraction data: `text_results`, `artifacts`, `job_stage_runs`, and `provider_calls`. `jobs.owner_id` remains the canonical owner. `saved_mentions.owner_id` already exists and remains required. The API should still fetch result data through an owned job and return 404 for other users.

Rationale: direct `owner_id` makes RLS, future queries, audits, cleanup, and accidental query safety clearer. It costs a little duplication, but it matches the product requirement that every job/result/mention is owner-scoped.

## Decision 2: Production Auth Mode Enforcement

Question: Should `AUTH_MODE=dev` be allowed to run when `APP_ENV=production`?

Decision: no. Production startup MUST fail fast if `APP_ENV=production` and `AUTH_MODE` is anything other than `supabase`. Local and test environments can keep `AUTH_MODE=dev`, including omitted `Authorization` mapping to `DEV_USER_ID`, but production must require a valid bearer token on every non-health endpoint.

Rationale: the current dev fallback is useful locally but dangerous in production because missing credentials silently become a real user identity.

## Decision 3: Supabase Token Acceptance

Question: Which Supabase JWTs should the API accept?

Decision: accept only Supabase user access tokens with `aud` matching `SUPABASE_JWT_AUDIENCE`, valid `iss`, valid `exp`, non-empty `sub`, and an authenticated user role claim such as `role=authenticated` when present. Reject anon tokens, service-role JWTs, expired tokens, unsupported algorithms, missing `sub`, and tokens from other projects.

Rationale: `sub` becomes `owner_id`, so the API should only accept real user sessions for public endpoints. Internal worker execution should not be exposed through public bearer auth.

## Decision 4: RLS Enforcement Strategy

Question: Should Postgres RLS be required for all owner-scoped tables in production, or should explicit application-level owner filters be the production boundary?

Decision: require both. Application-level owner filters remain mandatory and are what produce 404 semantics. Postgres RLS should be enabled as defense-in-depth on every table with `owner_id`: `jobs`, `text_results`, `artifacts`, `job_stage_runs`, `provider_calls`, and `saved_mentions`. Because FastAPI uses direct database connections, the implementation must document and test how the per-request user id reaches RLS policies. Worker paths should use a separate internal connection/role or explicit service bypass, not public user bearer auth.

Rationale: app filters are necessary for product behavior and clear errors; RLS reduces blast radius if a future query forgets an owner predicate.

## Decision 5: RLS User Context Mechanism

Question: How should FastAPI pass the verified user id into Postgres RLS?

Decision: use a transaction-local setting such as `app.current_user_id`, set after auth and before user-scoped DB work, with policies checking `owner_id = current_setting('app.current_user_id', true)::uuid`. The value must come from the verified Supabase user `sub`, not from request body/query/header user input. Health checks and internal worker code should not set a public user id.

Rationale: a custom app setting is explicit and easy to test in FastAPI direct-connection code. It avoids assuming Supabase browser-client claim plumbing exists in server-side SQLAlchemy connections.

## Decision 6: Worker Database Access

Question: How should internal workers access jobs and write result rows under RLS?

Decision: workers should use a separate internal database role/connection that can bypass user RLS only for worker responsibilities: claiming queued jobs, heartbeats, retries, failures, and writing result/mention rows using the job's canonical `owner_id`. Worker code must never accept public user bearer tokens and must never invent owner ids; it always copies ownership from the claimed job.

Rationale: workers operate across all users' queued jobs, so they cannot be scoped to one end user. A dedicated internal role keeps that power separate from public API auth.

## Decision 7: Public Exposure Of Owner IDs

Question: Should API responses include `owner_id`?

Decision: no. Store `owner_id` in the database and use it for authorization, RLS, audits, cleanup, and internal diagnostics, but omit it from public `JobResponse`, `JobResultResponse`, and `SavedMentionResponse`. The authenticated caller already knows who they are, and exposing owner ids adds little product value.

Rationale: minimizing public identifiers keeps response contracts simpler and avoids training frontend code to depend on authorization internals.

## Decision 8: Cross-User Object Semantics

Question: When an authenticated user requests another user's job, result, or saved mention by id, should the API always return 404?

Decision: yes. Cross-user access to `GET /v1/jobs/{job_id}`, `GET /v1/jobs/{job_id}/result`, `POST /v1/jobs/{job_id}/rerun`, `POST /v1/jobs/{job_id}/cancel`, `GET /v1/mentions/{mention_id}`, `PATCH /v1/mentions/{mention_id}`, `POST /v1/mentions/{mention_id}/confirm`, and `DELETE /v1/mentions/{mention_id}` must return 404 exactly like nonexistent objects. List endpoints must silently exclude other users' rows.

Rationale: 403 would reveal that the object exists. 404 is the right product/security behavior for opaque user-owned ids.

## Decision 9: Unauthenticated Request Semantics

Question: What should production return when a public API request has no bearer token or an invalid bearer token?

Decision: return 401 for missing, malformed, expired, or invalid tokens. Reserve 404 for authenticated callers trying to access objects they do not own. Health endpoints may remain public if they reveal no user data.

Rationale: clients need a clear signal to re-authenticate. 404 is only for hiding object existence after a caller is authenticated.

## Decision 10: Migration Strategy

Question: Should this work edit the existing initial migration, or add a new migration?

Decision: add a new Alembic migration and leave the existing migration intact. The new migration should add `owner_id` to `text_results`, `artifacts`, `job_stage_runs`, and `provider_calls`, backfill from `jobs.owner_id`, make those columns non-null, add owner-aware indexes where useful, enable RLS on the new owner-scoped tables, and replace/adjust RLS policies to use `app.current_user_id`.

Rationale: the user explicitly asked not to edit `spec.md`; more importantly, preserving existing migrations avoids rewriting history and is safer for any database that already applied the initial schema.

## Decision 11: Redundant Owner Filters On Result Child Tables

Question: Once result child tables have `owner_id`, should application queries filter those child rows by both `job_id` and `owner_id`?

Decision: yes. `get_result` should first resolve the owned job, then fetch `text_results`, `artifacts`, and `job_stage_runs` with both `job_id = job.id` and `owner_id = caller.subject_id`. Internal/admin paths can use explicit internal methods. `provider_calls` is not currently public, but any future reads should follow the same rule.

Rationale: duplicate filters make mistakes easier to spot, align with RLS, and protect against corrupted or manually inserted child rows with the wrong owner.

## Decision 12: Admin Role Scope

Question: Should public Supabase user tokens ever become `Caller(role="admin")` in this milestone?

Decision: no. Public Supabase tokens should always become `Caller(role="user")`. Any admin/debug access should be out of scope for this milestone or implemented later through a separate internal auth path with explicit allowlisting. Existing debug output gates that depend on `caller.role == "admin"` should remain unreachable from public Supabase auth.

Rationale: admin authorization is a separate product/security problem. Mixing it into user auth would widen the surface before it is needed.

## Decision 13: Required Test Coverage

Question: What tests must pass before this feature is considered complete?

Decision: require focused tests for: production refusing `AUTH_MODE=dev`; missing/invalid tokens returning 401; Supabase token validation rejecting anon/service/wrong-project/missing-sub tokens; cross-user job/result/mention reads and mutations returning 404; list endpoints excluding other owners; result child rows receiving `owner_id`; `get_result` filtering child rows by owner; worker result writes copying `owner_id` from the job; and migration/RLS SQL containing policies for all owner-scoped tables using `app.current_user_id`.

Rationale: this is security-sensitive plumbing. The tests should prove both the public API contract and the persistence invariants.

## Decision 14: Build Timing

Question: After this interview, should implementation begin immediately in this branch, or should the spec stop here for review first?

Decision: begin implementation immediately after the final spec pass. The decisions are now concrete enough to implement narrowly: models, coordinator writes/queries, auth startup validation, RLS context dependency, migration, and tests. Keep the existing `spec.md` untouched.

Rationale: delaying after resolving the design tree adds little value unless another stakeholder needs to review the spec first.

## Implementation Scope

The implementation MUST update:

- SQLModel persistence models for result child `owner_id` fields.
- Coordinator writes so worker-created result rows copy `owner_id` from the canonical job.
- Public result reads so child rows are filtered by both `job_id` and `owner_id`.
- Auth settings validation so production cannot run with dev auth.
- Supabase token validation so only authenticated user access tokens are accepted.
- FastAPI authenticated session dependency so Postgres receives `app.current_user_id` for RLS.
- A new Alembic migration that preserves existing migration history.
- Focused tests proving the owner-scoping, auth, migration, and RLS-context contract.
