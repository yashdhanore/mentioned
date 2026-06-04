# Prime: Fix pending shared-source hardening review findings

## Project Purpose

Mentioned is a FastAPI backend plus Expo React Native mobile app that lets users
save public Instagram Reel/post URLs, queue extraction jobs, and review extracted
book mentions. Release 1 is an iOS-first published proof where native share-sheet
capture is the primary save path and paste-link capture remains a fallback.

The current work focuses on making signed-out native capture trustworthy: preserve
a shared source through sign-in, avoid storing auth/callback secrets, and keep
job creation/account ownership behind the authenticated FastAPI API.

## Current Request Context

The previous review spawned Expo/mobile, Supabase, backend architecture, and
codebase-architecture reviewers. The review found that the implemented pending
shared-source feature is directionally right but not yet best-practice complete.

Findings to address:

- Pending source URLs can persist token-like query params because
  `mobile/src/utils/shared-source-url.ts` strips only `utm_*` and `igsh`.
- Cold-start deep-link handling can duplicate submissions because
  `Linking.getInitialURL()` is read in an effect that re-runs when auth state
  changes, and dedupe uses mixed raw/stored keys.
- Pending restore and submit flows can race: a stale stored source can overwrite
  a fresh share, and an older in-flight submit can clear a newer pending source.
- Signed-out UI can render duplicate sign-in copy because `authError` is used for
  expected pending-source state.
- Production Supabase mobile config accepts unsafe public key or redirect override
  values unless guarded.
- `/v1/jobs` is not idempotent for at-least-once share delivery. This is a
  backend contract hardening item and may require a schema/migration decision.

## Relevant Code Areas

Mobile source parsing and pending persistence:

- `mobile/src/utils/shared-source-url.ts`: validates supported Instagram hosts and
  `/reel/` or `/p/` paths, normalizes hashes and selected query params, and parses
  `mentioned://share?url=...` including Expo dev-client wrappers.
- `mobile/src/features/captures/pending-shared-source.ts`: AsyncStorage-backed
  helper that currently persists only `{ sourceUrl, createdAtMs }`.
- `mobile/scripts/test-share-url-extraction.ts`: pure parser/deep-link coverage.
- `mobile/scripts/test-pending-shared-source.ts`: pure pending-store coverage.

Mobile auth/deep-link coordination:

- `mobile/App.tsx`: currently coordinates Supabase session restore, auth state
  subscription, initial/event deep links, pending shared-source state, pending
  save/discard, and screen props.
- `mobile/src/screens/signed-out-screen.tsx`: signed-out auth UI and pending-source
  warning.
- `mobile/src/screens/home-screen.tsx`: signed-in capture grid and pending Save /
  Discard prompt.
- `mobile/src/supabase.ts`: Supabase client, PKCE OAuth, redirect URL handling,
  AsyncStorage session persistence, and `currentAccessToken`.

Mobile API/job submission:

- `mobile/src/features/captures/use-captures.ts`: capture state and
  `submitSharedUrl(sourceUrl)`, which delegates to `createJob(url)` and inserts an
  optimistic processing capture.
- `mobile/src/api.ts`: authenticated `fetch` wrapper and `createJob(url)`.

Backend job contract:

- `src/jobs/router.py`: `POST /v1/jobs` validates a URL, checks active/burst/daily
  quotas, and always creates a new queued job.
- `src/jobs/service.py`: `create_queued_job` inserts a new `Job` and enqueues the
  extract job.
- `src/jobs/schemas.py`: `CreateJobRequest` currently accepts only `{ url }`.
- `src/jobs/models.py`: `Job` has no client submission ID or provenance fields.
- `tests/jobs/test_router.py`: covers create, quotas, list/detail, but invalid URL
  still permits either 400 or 404 and there is no idempotency coverage.

Database/migration context:

- Repo docs say app-table production schema is managed with Alembic migrations in
  `migrations/versions/`.
- `AGENTS.md` also says Supabase schema/migration changes must use the Supabase
  CLI directly. Supabase CLI is installed (`2.98.2`, update available to `2.105.0`).
- If backend idempotency is included in the next implementation, resolve this
  workflow explicitly in the plan instead of silently choosing one.

## Current Git State

- Branch: `share-extension`.
- Recent commits: shared iOS URL handoff/job routing fixes.
- Worktree is dirty from the pending-source implementation:
  - Modified: `mobile/App.tsx`, `mobile/package.json`,
    `mobile/src/screens/home-screen.tsx`,
    `mobile/src/screens/signed-out-screen.tsx`, `mobile/src/styles.ts`,
    `tests/test_mobile_signed_out_screen.py`.
  - New: `mobile/scripts/test-pending-shared-source.ts`,
    `mobile/src/features/captures/pending-shared-source.ts`.
- There are unrelated/untracked AI-layer docs, `audits/`, `temp/`, and docs
  artifacts. Do not revert or clean these unless explicitly asked.

## External Docs Checked

- Supabase React Native quickstart confirms native auth patterns: AsyncStorage,
  `persistSession`, `autoRefreshToken`, `detectSessionInUrl: false`, and
  `processLock`.
- Supabase API key docs distinguish client-safe `sb_publishable_...` / legacy
  `anon` from server-only `sb_secret_...` / legacy `service_role`, and warn never
  to expose secret keys in public mobile/browser bundles.
- Supabase changelog markdown did not fetch cleanly through the browser tool, but
  search results surfaced the API key change/deprecation path as relevant.

## Patterns To Follow

- Keep pending-source storage non-secret. Persist only canonicalized source
  metadata, not raw deep links, OAuth callback URLs, access tokens, refresh tokens,
  provider tokens, or arbitrary token-like query params.
- Use one canonical dedupe identity for native share intake. Prefer normalized
  source URL or a stable source-derived key rather than mixing raw deep-link URLs
  and `stored:${sourceUrl}` keys.
- Read `Linking.getInitialURL()` once per app launch. Keep the event listener
  current without reprocessing the launch URL on auth state transitions.
- Coordinate restore and incoming-share writes so a stale stored source cannot
  overwrite a newer share.
- Clear pending state only if the pending record being cleared still matches the
  submitted/discarded record.
- Reserve `authError` for real auth/storage failures. Expected signed-out pending
  state should be represented by pending-source UI, not an error.
- Preserve the existing successful submission path through `submitSharedUrl` and
  `/v1/jobs`.
- If idempotency is implemented, keep `/v1/jobs` as the resource but add a stable
  client submission identity and backend reuse semantics; do not create a separate
  `/v1/shared-sources` endpoint unless backend needs raw share payloads.

## Risks Or Unknowns

- There is no React component test harness for `App.tsx`; source-level tests and
  pure scripts cannot catch the current race conditions. A small extracted intake
  module may be the practical test seam.
- Token-like query stripping needs product judgement: removing suspicious params
  from supported Instagram URLs is safer than storing/replaying them, but it may
  drop benign tracking params beyond `utm_*`.
- Backend idempotency has real value but broadens scope into schema/migration,
  quota semantics, and mobile API contract changes.
- Supabase production config hardening can be done mobile-only and should not need
  a remote Supabase change.
- Manual iOS share smoke testing still needs Supabase auth configured and a
  reachable backend.

## Recommended Next Command

Use `plan fix pending shared-source hardening`. Recommended scope order:

1. Mobile-only hardening first: canonical URL/query sanitization, stable dedupe,
   one-time initial URL handling, restore/submit race guards, duplicate-copy fix,
   Supabase mobile config guards, and tests/scripts.
2. Then decide whether to include backend idempotency in the same plan or split it
   into a follow-up migration/API-contract plan.

Validation targets should include:

- `cd mobile && npm run test:share-url`
- `cd mobile && npm run test:pending-shared-source`
- `cd mobile && npm run typecheck`
- `python -m pytest tests/test_mobile_signed_out_screen.py`
- If backend idempotency is included: focused `tests/jobs/test_router.py` and
  migration/RLS regression tests.
