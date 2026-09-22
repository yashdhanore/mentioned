# Technical Decisions And Ideation

Last updated: 2026-09-22

This is the canonical home for Mentioned technical decisions, architecture status, technical
ideation, and rejected approaches. Technical decisions must start from the product direction in
`docs/strategy/product.md`; infrastructure work is only valuable when it protects or improves the
save -> extract -> revisit loop.

## How To Use This File

- Keep technical decisions and architecture ideas here, not scattered across product notes or plans.
- Record rejected approaches with the reason they were rejected so agents do not resurrect them.
- Before adding a technical idea, check whether it changes the product contract, v1 app behavior,
  user trust, cost, privacy, or product vocabulary.
- Before treating an architecture or implementation approach as new, search this file and
  `docs/strategy/product.md` for prior notes, rejected approaches, or product constraints.
- After meaningful technical research, architecture discussion, approach comparison, or implementation
  decision, add a dated note or update the relevant decision here. Include the product constraint or
  user-facing goal the technical choice supports.
- When a technical idea becomes actionable, promote it into a PRD, implementation plan, migration,
  or issue and leave a link back here.

## Product Constraints For Technical Decisions

- Protect the core loop: save a social source, extract useful mentioned items, let users correct or
  keep what matters, and make saved sources/items easy to revisit.
- Preserve the book-first wedge while keeping the data model and architecture ready for generic
  saved items and future mention types.
- Do not change the published v1 HTTP contract or user-visible semantics unless the product decision
  explicitly accepts the app-release cost.
- Avoid technical choices that increase extraction cost, privacy risk, account deletion complexity,
  or support burden without a clear product payoff.
- Prefer technical paths that let product learn from the smallest reliable test before committing to
  broad platform, category, or pricing expansion.

## Architecture Status: v1 (shipped) vs v2 (in progress)

> **SUPERSEDED as of 2026-09-21.** Everything below this box describes the old `/v1/jobs` /
> `/v1/mentions` era. That compatibility surface has been deleted from the codebase (see the
> 2026-09-21 note under "Ideas To Preserve"). It is kept here only as historical record of why the
> `sources` / `source_items` / `saved_sources` model exists and what it replaced. Do not resurrect
> `src/jobs` or `src/mentions`; do not treat the "frozen v1 contract" language below as still binding.

> **Read this first if you are an agent working on the backend.** As of 2026-06-13 the app is submitted to the App Store. The shipped mobile binary is frozen against the **v1 HTTP contract**, so v1 **user-visible behavior and HTTP contract must not change** - but internal worker/ingestion behavior *can* (see "Frozen = contract, not internals" below). v2 is being built *alongside* v1 in the same repo and same Supabase project - not as a replacement edit.

> **2026-06-22 update:** The saved-source cutover supersedes the old `/v1/jobs` and
> `/v1/mentions` surface before public release. Treat the job/mention contract and `/v2`
> sequencing notes below as historical compatibility context unless an already-shipped binary still
> calls them. Active app/backend work should target `/v1/saved-sources`, `sources`,
> `source_items`, and `saved_sources`.

**v1 - live. Frozen CONTRACT, not frozen internals:**
- What is frozen: the **entire `/v1` HTTP contract and user-visible semantics** the submitted app calls (verified against `mobile/src/api.ts`). These are a promise to the published app and must not change:
  - `/v1/jobs` (POST create, GET list) + `/v1/jobs/{id}` (GET, DELETE) - `src/jobs/router.py`
  - `/v1/mentions/{id}` (DELETE) - mentions router
  - `/v1/account` (DELETE) - `src/account/router.py`
  - `/v1/push-tokens` (POST) and `/v1/push-tokens/disable` (POST) - push router
  - Plus the Supabase **realtime subscription to `public.job_events`** the app relies on for completion refresh (`mobile/src/features/captures/use-captures.ts`). Changing the event shape or table is also a contract break.
- What is NOT frozen: **internal worker/ingestion behavior is allowed and desired to change in place.** Hardening `public.jobs` claiming, timeouts, idempotency, and concurrency does not alter the contract, so it ships safely to v1 users now (see Axis A).
- Data: `public.jobs`, `public.mentions` (`src/jobs/models.py`, `src/mentions/models.py`).
- Ingestion: `extract_jobs` pgmq queue → single `mentioned-worker` Render service (`src/worker.py`).
- Known brittleness (the thing Axis A fixes): single-worker SPOF, serial processing, no per-job timeout, unbounded per-job Gemini calls, non-idempotent mention writes.

**v2 - in progress. Two decoupled axes, SHARED `public` data (no separate schema):**

> A separate `v2` Postgres schema was considered and **rejected** after code review (2026-06-13). It caused split-brain data, a worker that couldn't write across schemas (FK to `public.jobs`), a dropped realtime `job_events` path, account-deletion leakage, quota bypass, and RLS/grant duplication - all for isolation the real goal never needed. The rejected plan's detailed writeup was removed in a later repo cleanup; this paragraph is the
record. **Do not resurrect the schema-split approach.**

The work splits along two independent axes:

- **Axis A - Production ingestion hardening (invisible to the app, do FIRST - and note this is v1-compatible, NOT gated on `/v2`):** fix the brittle claim path **in place on `public.jobs`** - `FOR UPDATE SKIP LOCKED` claiming, per-job timeout, idempotent mention writes (unique constraint or upsert), bounded Gemini concurrency. Because the "10–15 users / high expense" concern is half reliability and half *cost*, this pass also includes the cost-control track: provider budget caps, per-user cost/retry ceilings, and per-extraction cost/latency instrumentation (see "Ingestion And Cost Control" below). All of it lives *behind* the HTTP contract, so it ships safely to v1 users now, no app release required.
- **Axis B - `/v2` contract (visible to the app, do AFTER A is stable):** mount polished `/v2/*` endpoints in the same FastAPI app that **read/write the existing `public` tables**. Same auth, same data, same `job_events` realtime path, same RLS, same quotas - so none of the coexistence-tax bugs apply. The `/v2` prefix gates rollout: published app stays on `/v1`, new app build calls `/v2`. No data copy, no split-brain, because both contracts sit on one set of tables.

- **Guardrail:** Axis B builds `/v2` handlers in parallel modules; do NOT refactor the shared v1 code in `src/jobs/*` that the published app depends on. Axis A *does* modify shared worker/service code in place - that's intended, and it must keep v1 endpoints behaviorally identical (regression-test the v1 contract).

**Plans (sequenced):**
1. *production-ingestion-hardening* (to be written) - Axis A, in place on `public.jobs`. v1-compatible, NOT gated on `/v2`. Covers claim safety + timeouts + idempotency + concurrency AND the cost-control track (budget caps, per-user ceilings, retry budgets, cost/latency instrumentation). **Start here; serves the actual goal.**
2. *v2-contract* (to be written, needs an API design pass) - Axis B on shared `public` tables: improved request/response shapes, pagination, idempotency keys, error envelope.
3. *mobile-v2-cutover* (to be written) - point new app build at `/v2`, submit, retire `/v1` routes once old-app traffic hits zero.
- ⛔ v2-coexistence-foundation plan - SUPERSEDED/rejected (schema-split); writeup removed in cleanup, see the rejection note above. Do NOT execute or treat as active.

## Ideas To Preserve

### 2026-09-21 - Jobs/Mentions Compatibility Surface Removed

- Status: Accepted and implemented. Completes the 2026-06-22 saved-source cutover decision below.
- Product constraint: Protects the save -> extract -> revisit loop and user trust by making the
  code that actually runs match the live `/v1/saved-sources` contract, and closes a real account
  deletion privacy gap (see next bullet).
- Notes: `src/jobs/`, `src/mentions/`, the legacy per-job ingestion processor, and the legacy
  `public.jobs`/`public.mentions`/`public.job_events` tables and `extract_jobs` pgmq queue are gone.
  Alembic revision `20260921_0017` drops those tables, their RLS policies/grants, and the
  `extract_jobs` queue; it leaves the pgmq schema/function grants and sequence grants alone because
  `extract_sources` and `push_notifications` still use them. `migrations/env.py` now registers every
  live SQLModel table (books, places, push tokens, sources/source_items/saved_sources, waitlist)
  instead of the stale `Book`/`Job`/`Mention` trio. The three duplicate error hierarchies
  (`JobError`/`MentionError`/`SourceError`) collapsed into one `src.errors.AppError` base with one
  FastAPI exception handler in `src/main.py`, keeping the `{"error_code", "message"}` response shape
  unchanged. Book enrichment (`src/books/enrichment.py`) now writes directly onto `SourceItem`
  instead of building a throwaway `Mention(owner_id=source.id, job_id=source.id, ...)` object, matching
  how place enrichment already worked. The Supabase Storage thumbnail helper is source-keyed
  (`store_source_thumbnail(..., source_id=...)`); the storage path still contains a literal `jobs/`
  segment on purpose, so already-uploaded thumbnails are not orphaned.
- Bug fix: account deletion (`src/account/service.py`) deleted `JobEvent`/`Mention`/`Job` rows and
  never touched `SavedSource`, so a deleted user's saved sources silently survived. Deletion now
  removes the user's `SavedSource` and `PushToken` rows. The shared `sources`/`source_items` cache
  rows are left alone on purpose - they carry no owner id, and another user may still have their own
  `saved_sources` row pointing at the same canonical source (matches the 2026-06-21 shared-cache
  decision below: account deletion removes user-owned rows and can GC unreferenced cache rows later
  under a retention policy, which this change does not add).
- Push notifications are re-keyed onto `sources`: `complete_source_processing`/
  `fail_source_processing` (`src/sources/service.py`) call `enqueue_push_notification` in the same
  transaction as the status-changing `UPDATE`, mirroring the existing `enqueue_source_extraction`
  outbox pattern. The push worker fans a single source completion/failure out to every owner in
  `saved_sources` for that source who has an active push token (`list_push_targets_for_source` in
  `src/push/service.py`), because a shared source can have several savers. The Expo payload's `data`
  key changed from `job_id` to `saved_source_id`, matching what `mobile/src/notifications.ts` already
  reads (the mobile app was ahead of the backend here). The Android notification channel id is left
  as the literal string `"job-status"` because `mobile/src/notifications.ts` creates the channel with
  that exact id and mobile is out of scope for this change.
- SQLite/dev mode: the polling worker (`src/worker.py`) now claims pending `Source` rows via the
  existing atomic `claim_source_for_processing`, instead of only claiming legacy `Job` rows (which
  meant a saved source never processed at all under the default `DATABASE_URL=sqlite:///app.db`).
- Rejected/deferred in this change: renaming `MAX_JOB_CREATE_BURST_PER_MINUTE` /
  `MAX_JOBS_CREATED_PER_DAY` / `MAX_ACTIVE_JOBS_PER_USER` to source-flavored names. `scripts/`
  (`check_release_env.py`) and `.env.example` reference these exact env var names and are owned by
  another workstream in this change, so the names stay as-is.

### 2026-06-24 - Website Footer Animation Implementation

- Status: Accepted for the landing page footer
- Product constraint: Supports the website as a vision and waitlist surface while keeping the
  book-first save -> extract -> revisit loop concrete.
- Notes: Build footer animation as native Astro markup, CSS, optimized generated image assets, and
  a HyperFrames-style GSAP/ScrollTrigger motion layer where HTML remains the source of truth. Use a
  short generated row-strip frame sequence so the swipe reads as fingers changing position inside
  the image itself, not as DOM overlays or moving phone-screen content. Use the hatch-pet-style
  discipline of rejecting drifted candidates, accepting one consistent frame strip, and only using
  deterministic cropping/resizing after the visual frames exist. Reserve rendered Remotion or
  HyperFrames video assets for cases where the website truly needs a baked transparent WebM overlay.
  Keep reduced-motion behavior static and animate only opacity/transform.

### Job And Worker Architecture

> Now being actioned - see "Architecture Status" above. Hardening specifics live in the planned *production-ingestion-hardening* plan (Axis A, in place on `public.jobs`). NOTE: the old `2026-06-13-v2-coexistence-foundation.md` is a REJECTED record - do not follow it.

- Revisit the current always-running worker model.
- Explore event-driven processing so extraction work starts when a job/event arrives.
- Learn queues through a practical implementation, possibly RabbitMQ, Redis Queue, Celery, Dramatiq, or a managed cloud queue.
- Decide whether database-backed jobs are enough for the current scale or whether a queue should own job delivery.

### Ingestion And Cost Control

- Reduce dependence on sending every downloaded reel directly to Gemini.
- Add cheaper extraction passes before multimodal LLM calls, such as URL parsing, captions, metadata, OCR, transcripts, and frame sampling.
- Use LLM calls as a fallback or confidence booster rather than the default for every input.
- Track provider cost, latency, and confidence per extraction.

### 2026-06-24 - Cheap Relevance Gate Before Video Extraction

- Status: Accepted and implemented (first concrete step of the Ingestion And Cost Control
  direction above). 2026-06-24 update: launched directly in `active` mode (skips confident
  `irrelevant`) rather than shadow - the user accepted the false-skip risk for immediate cost
  savings, relying on the conservative fail-open criteria. `shadow` remains available via
  `RELEVANCE_GATE_MODE` as the rollback/measurement lane if false-skips show up.
- Skip visibility: a gated skip persists `sources.skip_reason` (Alembic
  `781a3572bbaf`), surfaced additively as `SavedSourceResponse.skip_reason` and rendered in the
  *next* mobile build as a distinct "Nothing to extract from this post" empty state. The frozen v1
  app ignores the new field. A normal empty extraction leaves `skip_reason` null so the UI can tell
  "gated out" from "looked and found nothing".
- Product constraint: Supports cost control for the save -> extract -> revisit loop without changing
  the frozen v1 HTTP contract. Stops spending full video+audio Gemini tokens on saved sources that
  plausibly contain no book/product/place, while protecting recall so users are never wrongly told
  "nothing found" on a real book reel.
- Decision: Before the expensive multimodal extraction, run one cheap multimodal call on signals we
  already fetch for free in the yt-dlp preflight - the caption (`description`/`title`) plus the post
  thumbnail. The gate returns a three-way enum verdict (`relevant`/`irrelevant`/`uncertain`) via
  Gemini structured output, on a cheaper model (`GEMINI_GATE_MODEL`, default `gemini-2.5-flash-lite`).
  Lives in `src/extraction/relevance.py`, called from `src/extraction/pipeline.py` after download.
- Fail open: the pipeline skips the expensive call ONLY on a confident `irrelevant`; `relevant` and
  `uncertain` both escalate to full extraction. Any gate error, empty, unparseable, or unknown
  verdict resolves to `uncertain` (proceed). Rationale: a wasted video call is far cheaper than a
  silent false "nothing found".
- Rollout: `RELEVANCE_GATE_MODE` = `off` | `shadow` | `active`, default `shadow`. Shadow logs the
  verdict on every reel but always extracts, so the false-skip rate can be measured on real traffic
  before any token-saving skip happens. Flip to `active` only after shadow data shows skips are safe.
- Research basis (2026-06-24): matches Anthropic routing/gate workflow and the FrugalGPT/RouteLLM
  cascade pattern. Deliberately avoids brittle caption keyword/regex matching (no semantic intent)
  and avoids trusting an LLM self-reported float confidence (poorly calibrated/overconfident) in
  favour of a 3-way enum with `uncertain` as a first-class abstention. Caption is treated as
  untrusted input; the thumbnail image is an independent signal so caption text alone cannot force a
  skip.
- Known limitation to watch: a book shown only mid-video or named only in speech may be absent from
  both caption and thumbnail, so an `active` gate could false-skip it. This is the main reason for
  shadow-first rollout and the fail-open bias. Revisit frame sampling/OCR/ASR as a richer gate only
  if shadow data shows caption+thumbnail recall is insufficient (see the 2026-06-21 frame-sampling
  note).
- Open contribution: the gate's verdict criteria prompt (`GATE_CRITERIA` in `relevance.py`) is the
  real skip bar and is owner-tuned; the schema/IO/fail-open wrapper are fixed.

### 2026-06-25 - Place Enrichment Via Google Places (First Non-Book Enrichment)

- Status: Accepted, pre-implementation. Spec doc removed in a later repo cleanup; this note is the
  record. Follows the 2026-06-25 surfacing phase that made the mobile client type-neutral.
- Product constraint: Improves the save -> extract -> revisit loop by making a saved place worth
  revisiting (address + map), while preserving the book-first wedge, frozen v1 contract safety,
  the canonical shared-source cache model, and cost control.
- Decision: Enrich `place` mentions inline in the worker, mirroring the Google Books template.
  New `src/places/` package (`Place` model + `upsert_google_place` + `enrich_extracted_place_item`)
  deduped by Google `place_id`; new `places` table; additive `place_id`/`formatted_address`/
  `latitude`/`longitude` columns on `source_items` (denormalized for the read path, no join);
  additive optional API fields; mobile place row shows the address and deep-links to Google Maps.
  Provider lives in `src/extraction/google_places.py` (Text Search New, `places:searchText`).
- Matching: Gemini emits an optional transient `location_hint` (city/neighborhood, "do not guess")
  that biases the Places query. Save only high-confidence matches (hint present, or single
  candidate); otherwise FAIL OPEN to a bare title - same philosophy as the relevance gate. Dropping
  unmatched places was rejected (hides real mentions).
- Storage rationale: dedicated typed table + FK chosen over loose `source_items` columns or a JSON
  blob, to keep one enrichment pattern across types (consistency with `books`, AI-navigable). Sits
  on the canonical shared cache per the 2026-06-21/2026-06-22 source-cache decisions, never per-user.
  The frozen v1 `Mention` table is left untouched; place enrichment writes only `SourceItem`.
- Cost: address + map pin requires `formattedAddress`/`displayName`/`location`, all *Text Search
  Pro* SKU (only `places.id` is the cheaper Essentials/IDs-Only SKU), and Places bills at the
  highest requested SKU - so this is unavoidably Pro tier (accepted). Field mask is deliberately
  minimal; widening it to rating/hours/photos jumps to Atmosphere/Enterprise SKUs. Do not widen
  without re-pricing. New `GOOGLE_PLACES_API_KEY` setting; unset key degrades to no enrichment.
- Rejected alternatives: async enrichment queue and enrich-on-read (premature for one cheap call at
  current volume; enrich-on-read also breaks the canonical-cache model). OpenStreetMap/Nominatim and
  Gemini-only enrichment were considered for the provider but rejected in favor of Google Places for
  match quality + a stable dedup id.
- Follow-ups: product enrichment is the next phase (uses `places` as the template); revisit the
  per-type confidence floor and add per-extraction provider cost instrumentation once real data
  exists.

### 2026-06-28 - Place Enrichment Grilling Confirmations

- Re-grilled the 2026-06-25 place spec before implementation; the spec stands. Confirmations:
- Scope: the iOS published proof has shipped, so the `CONTEXT.md` "non-book categories" Release 1
  exclusion is now being lifted deliberately, places first. Products are confirmed DEFERRED again
  this round (no clean single-call provider analog to Google Books/Places; revisit after real
  place data). Book is now framed as one mention category, not the product.
- Terminology: "Mention" is the canonical glossary term for an extracted candidate item (carries a
  `category`); "extracted item" demoted to `_Avoid_`.
- Matching: keep the spec's fail-open high-confidence bar; add match-outcome logging (hint present?
  candidate count? matched vs failed-open?) to gather tuning data before adjusting the bar.
- Schema mechanism: **Alembic is the single source of truth** (see ADR 0001). `create_all` is
  dev-only (`AUTO_CREATE_TABLES=false` in prod) and the `supabase/migrations/*.sql` files are dead
  (not in the deploy pipeline). The place migration is one additive Alembic revision. Root + Supabase
  agent guides corrected to point at Alembic for table/column changes.

### 2026-06-28 - Place Walking Skeleton: maps_url Denormalized As 5th Field

- Built the place-enrichment walking skeleton (faked provider, injected `place_finder`) per the
  2026-06-25 spec. Migration `20260628_0015` adds the `places` table and denormalized columns on
  `source_items`.
- Decision: the spec's §6 calls for the mobile place row to deep-link to the provider `maps_url`,
  but the canonical link could not be reconstructed client-side - the API exposes our internal
  `places.id` UUID, not Google's `provider_place_id`, and the minimal Pro-tier field mask omits
  `googleMapsUri`. So `maps_url` is denormalized onto `source_items` and serialized as a **5th**
  additive API field (beyond the four the slice's issue enumerated), mirroring how
  `cover_image_url` rides the item for books. Mobile prefers `maps_url`, falling back to a
  `maps/search/?api=1&query=<lat>,<lng>` link; a bare/coordless place stays non-tappable.
  **Why:** honors the spec's revisit-value intent (a named Google place card beats a raw pin)
  without widening the billed field mask. **How to apply:** when the real provider lands (issue
  #46), keep building `maps_url` deterministically as
  `https://www.google.com/maps/place/?q=place_id:<provider_place_id>`; do not add `googleMapsUri`
  to the field mask (it would re-price the SKU). The read path still needs no join - display
  fields live on `source_items`.

### 2026-06-21 - Behavior-Preserving Ingestion Module Seam

- Status: Accepted as the first architecture step before production ingestion hardening.
- Product constraint: Protects the save -> extract -> revisit loop and frozen v1 HTTP contract while
  making worker internals easier to harden in place.
- Notes: Saved source processing now belongs behind `src.ingestion.processor`, extract queue message
  handling behind `src.ingestion.queue_worker`, and push queue message handling behind
  `src.push.worker`. This does not add Axis A hardening yet; claim safety, timeouts, idempotency,
  concurrency, retry budgets, and cost instrumentation remain in the future
  *production-ingestion-hardening* plan.

### 2026-06-21 - Shared Source Cache And User-Owned Saved State

- Status: Accepted as the implementation direction for reel/post caching.
- Product constraint: Supports cost control and the save -> extract -> revisit loop while protecting
  privacy, account deletion, and frozen `/v1` contract safety.
- Notes: Do not make `public.jobs` or `public.mentions` the canonical shared cache. They are
  user-owned saved-source and correction state in the current `/v1` contract. Add a separate
  canonical source cache keyed by normalized platform/source identity plus cache version, storing
  extractor output, source metadata, and thumbnail source data without an owner id. A user saving a
  cached source should create or reuse only that user's saved-source row and user-owned mention rows
  or link rows. Deleting a saved post should unlink/delete the user's saved-source relationship,
  job events, and per-user rows only; it must not delete the canonical cache when other users may
  depend on it. Account deletion should remove all user-owned rows and can garbage-collect
  unreferenced cache rows according to the eventual retention policy. Individual book removal should
  never mutate canonical extraction output; either remove that UI capability in the next app version
  or represent it as a user-level hidden/incorrect override while keeping `/v1/mentions/{id}` DELETE
  backward-compatible as a soft-hide operation until the old app contract is retired.

### 2026-06-22 - Minimal Saved Source Cache Model

- Status: Accepted and implemented for the pre-release saved-source cutover.
- Product constraint: Protects the save -> extract -> revisit loop, keeps the book-first wedge
  simple, preserves v1 contract safety during the cutover, controls extraction cost through
  canonical source reuse, preserves user privacy and account deletion boundaries, and leaves room
  for future generic saved items without adding a reading-list product in this change.
- Decision: The accepted model is `sources + source_items + saved_sources`. `sources` is the
  canonical social-source cache keyed by deterministic source identity. `source_items` stores stable
  extracted item rows for books/products/places and future references. `saved_sources` is the
  user-owned link that makes a canonical source visible in one user's archive.
- Rejected in this change: do not add `source_extractions`, versioned extraction history, per-user
  item override tables, or reading-list tables. Those add product and migration complexity before
  the save -> extract -> revisit loop has proven that users need corrections, historical extractor
  comparisons, or curated lists.
- Notes: `/v1/saved-sources` replaces the old job/mention endpoint surface for the app cutover.
  Legacy `src/jobs/*` and `src/mentions/*` modules remain only as internal compatibility surfaces
  while worker, push, account deletion, and enrichment code still reference them.

### 2026-06-24 - Source Processing Attempt Guard

- Status: Accepted and implemented for saved-source ingestion robustness.
- Product constraint: Protects the save -> extract -> revisit loop when several users save the same
  source or when queue visibility/stale recovery causes duplicate delivery.
- Notes: Source completion and failure now only finalize the row when the source is still in the same
  `processing_started_at` attempt that the worker claimed. A stale worker cannot overwrite a newer
  attempt or archive the source queue message when its result was rejected. Completion also replaces
  existing source items for the accepted attempt so retries remain deterministic.

### 2026-06-21 - Worker Scale Audit For 1,000-Job Backlogs

- Status: Reviewed; current beta worker can hold and drain a 1,000-job backlog, but should be treated
  as serial beta infrastructure rather than scale-hardened ingestion.
- Product constraint: Protects the save -> extract -> revisit loop, frozen v1 contract safety, cost
  control, and user trust in processing states.
- Notes: A synthetic 1,000-job lifecycle pass with fake extraction completed locally, which suggests
  the SQLModel job state machine is not the main bottleneck. Real throughput is dominated by
  `yt-dlp`, optional `ffmpeg`, Gemini, Google Books enrichment, provider quotas, and the current
  single-worker loop. Before relying on large backlogs, finish Axis A hardening: per-job timeout,
  idempotent mention/job-event writes, bounded provider concurrency, retry/dead-letter budgets, and
  cost/latency instrumentation. The pgmq queue path uses atomic `claim_job_by_id`, but the non-queue
  polling fallback remains select-then-update and should not be used as the scale path.

### 2026-06-21 - AI-Navigable Architecture Review

- Status: Reviewed; codebase partially follows deep-module practice, with backend ingestion as the
  strongest current seam and mobile app orchestration as the largest shallow surface.
- Product constraint: Supports the save -> extract -> revisit loop, book-first wedge, frozen v1
  contract safety, and future production ingestion hardening.
- Notes: Keep deepening in this order: first finish the saved-source ingestion seam so Axis A
  hardening has one module to change and test; next separate job lifecycle writes from job read
  models so `/v1` and future `/v2` contract mapping stop leaking SQLModel rows into routers; then
  split the mobile app shell into focused auth session, shared-source intake, notification routing,
  and capture-state modules. Book enrichment is also worth deepening because Google Books provider
  shape currently leaks through extraction schemas into books persistence and ingestion. The web
  landing surface has good validation and lower urgency; split its global stylesheet only when
  another substantial web section lands.

### 2026-06-21 - Affordable Production-Safe Development Workflow

- Status: Accepted as the default operating model once the store app has production users.
- Product constraint: Protects the save -> extract -> revisit loop, frozen v1 contract safety, user
  trust, privacy, and cost control while allowing post-publication iteration.
- Notes: Do not create a full always-on cloud stack per feature branch. Default to local-first
  development with local Supabase/Postgres, fake seeded users, fake or budget-capped extraction
  providers, Expo dev builds, tests, and contract checks. Keep production on one protected backend
  and one production Supabase project. Use one shared staging lane only for work that cannot be
  validated locally: a separate Supabase project with fake data, a staging API, and a worker that is
  run manually or cheaply during testing rather than kept fully scaled at all times. Production
  safety comes from never breaking `/v1`, adding visible app changes behind feature flags or a new
  `/v2` contract, using backward-compatible expand/contract migrations, testing TestFlight/internal
  builds against staging, and rolling out flags gradually before making features generally
  available.

### 2026-06-21 - Cloudflare Workers, D1, And R2 Cost Exploration

- Status: Explored; do not replace Supabase/Postgres for the active v1/v2 backend yet. Keep R2 as a
  candidate for future media/artifact storage if Supabase Storage egress or storage cost becomes a
  real constraint.
- Product constraint: Supports cost control and media retention decisions for the save -> extract ->
  revisit loop without breaking the frozen v1 HTTP contract, Supabase Auth, or `job_events`
  realtime refresh path.
- Notes: Cloudflare Workers Paid is attractive for small API surfaces at a $5/month base, and D1
  has generous included row-read/row-write allowances. But D1 is SQLite-based with a 10 GB hard
  limit per database and single-threaded per-database query execution, while this app currently
  depends on Supabase Auth, Postgres RLS, pgmq queues, Realtime on `public.job_events`, SQLModel over
  Postgres, and Supabase Storage thumbnails. A full migration would replace several working
  primitives at once and risks contract, privacy, account-deletion, and operational regressions for
  cost savings that are not yet the main bill driver. If Cloudflare is introduced near-term, the
  lowest-risk wedge is object storage: use R2 for thumbnails or retained derived artifacts behind
  the existing FastAPI worker, while keeping Supabase as the source of truth. Revisit a larger
  Workers/D1 architecture only after v1 ingestion hardening and cost instrumentation show database,
  storage, or Render worker cost is the bottleneck rather than Gemini/extraction cost.

### 2026-06-21 - Supabase Plus Cloudflare Worker For Background Extraction

- Status: Possible only with Cloudflare Containers or an external extraction service; do not replace
  the Render worker with a standard Worker runtime.
- Product constraint: Preserves Supabase Auth, Postgres/RLS, and `job_events` realtime for the save
  -> extract -> revisit loop while exploring lower idle compute cost.
- Notes: A standard Cloudflare Worker can connect to Supabase/Postgres and is a good fit for
  lightweight orchestration, queue dispatch, push notification HTTP calls, and R2 storage writes.
  It is not a good fit for the current extractor because `src.extraction.download` shells out to
  `yt-dlp` and `ffmpeg`, handles tens of MB of media, and needs a Linux-like filesystem/process
  environment. The realistic Cloudflare replacement is a Worker/Queue/Container architecture:
  enqueue jobs from the API, let a Worker consume or schedule work, and run the existing Python
  extraction code inside a Cloudflare Container that writes back to the same Supabase `public.jobs`,
  `public.mentions`, and `public.job_events` path. Treat this as a post-hardening spike, not an
  immediate migration, because it changes queue ownership, deploy tooling, secrets, observability,
  retry behavior, and cost shape. First refactor the worker into an idempotent process-one-job entry
  point with explicit timeouts, retry budgets, and cost metrics; then compare Container cost and
  reliability against the current always-on Render worker.

### 2026-06-21 - LLaVA-Video 72B As Gemini Replacement

- Status: Rejected as the default provider for the current book-first extraction loop; keep as an
  evaluation candidate for a future visual-only or privacy-sensitive provider.
- Product constraint: Supports cost control and extraction reliability for the save -> extract ->
  revisit loop without changing the frozen v1 HTTP contract.
- Notes: `lmms-lab/LLaVA-Video-72B-Qwen2` is an Apache-2.0 73B BF16 video model with a 64-frame
  input cap and no hosted Hugging Face Inference Provider as of this review, so production use would
  require self-hosted multi-GPU inference plus our own audio transcription, frame sampling, JSON
  validation, retries, monitoring, and queue controls. Gemini remains a better default while usage is
  low because it handles video/audio inputs behind a managed API and current per-extraction API costs
  are lower than keeping a 72B endpoint warm. Revisit only after provider instrumentation exists and
  a saved-source eval set shows LLaVA plus ASR/OCR matches or beats Gemini on real Reels.

### 2026-06-21 - Video-MME Provider Shortlist

- Status: Use Video-MME as a directional benchmark, not the deciding eval for Mentioned.
- Product constraint: Improves cost control and useful-but-imperfect extraction without changing the
  save -> extract -> revisit loop or the frozen v1 HTTP contract.
- Notes: Video-MME shows strong commercial-model performance and meaningful gains from subtitles or
  audio, which aligns with book Reels where titles often appear in speech, captions, overlays, or
  covers. `gemini-1.5-flash` was evaluated on Video-MME but is no longer a current production target;
  prefer testing current Flash/Lite Gemini models behind the existing `GEMINI_MODEL` setting. The
  near-term candidate is a provider A/B between the current default `gemini-2.5-flash` and a cheaper
  Flash-Lite tier, measured on real saved-source artifacts for mention precision, recall, latency,
  retry rate, and cost. Open models from the leaderboard, such as Qwen2-VL/Qwen2.5-VL, LLaVA-Video,
  InternVL, and video-SALMONN, should stay research candidates until they have managed API support,
  audio/transcript handling, structured-output reliability, and lower total cost than Gemini.

### 2026-06-21 - Frame And Scene Sampling For Video Extraction

- Status: Explore as an eval variant and fallback, not as the default replacement for direct Gemini
  video input.
- Product constraint: Supports cost control and useful-but-imperfect book extraction while preserving
  the save -> extract -> revisit loop, the frozen v1 HTTP contract, and future source recall.
- Notes: The current 20-Reel Gemini comparison already shows the main tradeoff: `gemini-2.5-flash`
  found more mentions than Flash-Lite on dense book-list sources, while Lite was much cheaper and
  faster. A Capstone-style scene segmentation, transcript, frame, and multi-vector index is valuable
  for future semantic source recall across many saved videos, but it is heavier than the current
  single-Reel extraction problem. For near-term extraction quality, prefer a staged test: keep full
  video plus audio as the baseline, try Gemini video controls such as custom FPS or media resolution
  on text-heavy Reels, and separately test selected frames plus OCR/transcript as a fallback when the
  model returns zero, unusually few, or suspiciously incomplete books. Do not switch to frame-only
  extraction unless a labeled Reel eval shows higher book precision/recall after accounting for lost
  audio context, extra OCR/ASR work, latency, storage, privacy, and provider cost. Do not add
  production Lite-vs-Flash routing until labeled evals prove the routing rule; if production must
  choose one Gemini model today, prefer Flash for recall and use Lite only in offline comparison or
  a deliberately lower-quality/cost mode.

### 2026-09-22 - Labeled Reel Evals Replace The Visual Manifest

- Status: Accepted and implemented; labels are being filled in by hand.
- Product constraint: Gives the useful-but-imperfect extraction bar a number, and gates the
  Flash-vs-Lite, fps/media-resolution, evidence-grounding, and verify-pass decisions above on
  labeled precision/recall instead of mention counts.
- Notes: `evals/reel-labels.json` holds ground truth for the 24 Reels in `evals/reel-lists/`;
  `scripts/score_extraction_eval.py` scores `compare_gemini_video_models.py` output with fuzzy
  title/alias matching, reporting precision/recall with Wilson intervals, author accuracy, false
  positives on Reels with nothing to find, confidence of correct vs wrong mentions, and cost per
  correct mention. The old `visual_regression_manifest.json` evaluator was removed because it scored
  OCR text artifacts that only the pre-Gemini pipeline produced; its one Reel became a label. The
  harness pattern (golden set, confidence intervals, hallucination reported separately) follows
  `ai-engineering-from-scratch` phase 11 lesson 10 and the phase 19 video capstone.

### 2026-09-22 - Worker Poison-Message And Shutdown Policy

- Status: Accepted and implemented.
- Product constraint: Protects the save -> extract -> revisit loop's reliability - a single
  malformed queue message or one unhandled exception must not crash-loop the single worker instance
  and silently stop all extraction for every user.
- Notes: `src/sources/queue.py` and `src/push/queue.py` now archive malformed or unknown-version
  pgmq messages instead of raising, so a bad message cannot repeat forever. A message whose
  `read_ct` exceeds the new `WORKER_QUEUE_MAX_DELIVERIES` setting (default 5) is treated as poison:
  the source is force-failed with a stable message and the queue message is archived, rather than
  redelivered indefinitely. `src/worker.py`'s polling and queue loops now catch unexpected exceptions
  per iteration (log with traceback, back off, continue; `KeyboardInterrupt`/`SystemExit` still
  propagate) and handle SIGTERM/SIGINT with a plain flag checked between iterations so Render's
  `maxShutdownDelaySeconds: 300` gives the worker time to finish an in-flight source before exiting.
  `sources.error_message` is API-visible to every user who saved that URL, so it is now always one of
  a small set of stable messages (`src/sources/failure.py`); raw exception/provider detail is logged
  server-side only, never stored on the row.

### 2026-09-22 - Alembic Owns All Of `public`, Including Grants And RLS

- Status: Accepted and implemented; extends ADR 0001.
- Product constraint: Contract safety and operational trust for the save -> extract -> revisit loop
  - a database built from `alembic upgrade head` alone must have the same schema, grants, and RLS
  as production, or a fresh environment silently diverges from what the API/worker expect.
- Notes: `waitlist_signups` existed only via a hand-written Supabase migration, so `POST /v1/waitlist`
  had no backing table on a database built purely from Alembic; added
  `migrations/versions/20260922_0018_waitlist_signups.py` (idempotent, safe on both a fresh database
  and production, which already has the table). Its RLS policy is scoped `to mentioned_api`,
  replacing the old policy that had no `to <role>` clause and so applied to every role. The two
  now-redundant Supabase SQL files were not deleted (the Supabase CLI tracks applied migrations by
  version, not checksum, so deleting a recorded-applied version risks `supabase db push` reporting
  missing remote versions) but rewritten as idempotent, order-independent no-ops with a header
  comment pointing at the Alembic revision that owns the object. `scripts/dev-up.sh` no longer needs
  to move `supabase/migrations/*.sql` out of the repo before first-time `supabase start`, because the
  one file that referenced an Alembic-owned table (`jobs`) is now guarded against that table not
  existing. Root `AGENTS.md` and `supabase/AGENTS.md` were corrected to say Alembic owns grants and
  RLS too, not just tables/columns - the Supabase CLI's real job is storage buckets, auth, and local
  stack config.

### 2026-09-22 - uv Lockfile And A Stable yt-dlp Pin

- Status: Accepted and implemented.
- Product constraint: Cost control and operational trust for the save -> extract -> revisit loop -
  a production-risk incident already happened from this gap (sqlmodel 0.0.45 broke every insert on a
  fresh install because dependencies were lower-bound only, with no lockfile).
- Notes: Adopted `uv` with a committed, hash-pinned `uv.lock`; `uv sync --frozen` resolves to the
  exact same versions in dev, CI, and the Docker build. Re-pinned `yt-dlp[curl-cffi]` to `>=2026.8.19`
  (a real stable release) instead of the upstream `master` tarball: the Instagram browser
  impersonation fix (yt-dlp #17074) shipped in the 2026.07.04 stable release (PR #17113), so a moving,
  unhashable `master` tarball is no longer needed. The Docker image now installs only the dependency
  layer via `uv sync --frozen --no-dev --no-install-project` before copying source, so code-only
  changes do not reinstall every dependency, and the image has exactly one copy of `src` (the API runs
  `fastapi run src/main.py`, the worker runs `python -m src.worker`, neither depends on this package
  being pip-installed). `requires-python`/ruff `target-version` moved to 3.12 to match what CI and the
  Docker base image (`python:3.12.14-slim`) actually run; no code currently depends on 3.11.

### 2026-09-22 - Timezone-Aware Datetimes

- Status: Accepted and implemented.
- Product constraint: Contract safety and operational trust for the save -> extract -> revisit loop -
  `sqlmodel<0.0.45` was already a stopgap (0.0.45 rejects naive datetime writes), and the app-level
  naive-vs-aware mismatch was live-bug-adjacent (see the wire-format finding below).
- Notes: Every live datetime column in this schema was already `timestamptz` from the very first
  migration (0003) onward - there was no `timestamp without time zone` column to convert, so the
  planned "convert remaining naive columns" Alembic revision turned out to be unnecessary and was not
  added. The actual gap was purely application-side: `src/timeutils.py`'s `utc_now()` stripped tzinfo
  before returning, `src/sources/service.py` carried a hack to re-strip tzinfo off values read back
  from Postgres (which already came back aware), and `sqlmodel<0.0.45` was capped to tolerate the
  mismatch. Made `utc_now()` return aware UTC, removed the strip-tzinfo hack, required
  `sqlmodel>=0.0.45` (which maps `datetime` fields to its `UTCDateTime` type: aware UTC in, aware UTC
  out, on SQLite too), and enabled ruff's `DTZ` rule family - zero findings, since the codebase already
  funneled every "now" through `utc_now()`.
  **Wire format finding:** aware UTC datetimes serialize with a trailing `Z`
  (`"2026-01-01T10:00:00Z"`) instead of the old bare `"2026-01-01T10:00:00"` with no offset. Checked
  `mobile/src/screens/reel-detail-screen.tsx`'s `savedAtLabel()`, the only place the app parses
  `created_at` (`Date.parse(createdAt)`): a JS date-time string with no offset parses as **local**
  time per the ECMAScript spec, so the old wire format was a latent bug for any device not in UTC+0
  (verified: a device in UTC+5:30 would show "Saved 5h ago" for a source saved seconds ago; a
  negative-offset device would show "Saved just now" forever). The explicit `Z` fixes this rather than
  breaking it, so the wire format was allowed to change; pinned with a test asserting `created_at`
  ends in `"Z"` on both `/v1/saved-sources` and `/v1/waitlist` responses.
  **Verified against real Postgres** (throwaway `supabase/postgres:17.6.1.167` container, removed
  after): `alembic upgrade head` through 20260922_0018, `downgrade -1`/`-2` and back up for both new
  revisions (0017, 0018), and a direct insert/read/compare round trip with the actual `Source` model
  confirmed `tzinfo=UTC` on every value read back. Also ran `tests/test_postgres_dedicated_worker_rls.py`
  with its three role connection strings against the same container - all 4 pass; fixed an unrelated
  pre-existing bug in that file where the same bind parameter name was reused for a `uuid` column and
  a `text` column in one INSERT, which a real Postgres/psycopg3 rejects with "inconsistent types
  deduced for parameter" (SQLite silently tolerated it, so this had never been caught).
  **Correction:** the `sources` table has never had a `heartbeat_at` column in any migration; that
  column only ever existed on the legacy `jobs` table (dropped by revision 0017). An earlier item-4
  commit added a code comment to `src/sources/models.py` incorrectly attributing a `heartbeat_at`
  column to `sources` - corrected in this change once the migration inventory caught it.

### 2026-09-22 - Self-Hosted Variable Fonts, No Third-Party Font CDN

- Status: Accepted and implemented.
- Product constraint: Privacy consistency for the web landing page - the rest of the site already
  avoids third-party trackers and CDNs, so typography should not quietly add a Google Fonts request
  either.
- Notes: `web/src/styles/global.css` declared `Clash Display`, `Geist`, `Satoshi`, and
  `Plus Jakarta Sans` in its font stacks, but nothing ever loaded them (no `@font-face`, no `<link>`,
  no package), so every browser silently fell back to a system font and non-standard weights like
  `850`/`820` snapped to the nearest static weight. Standardized on two self-hosted variable fonts,
  both OFL-licensed and shipped as npm packages: Plus Jakarta Sans Variable for display (headlines)
  and Geist Variable for body text, via `@fontsource-variable/plus-jakarta-sans` and
  `@fontsource-variable/geist`. Clash Display and Satoshi (Fontshare) are not OFL, so they were
  dropped rather than self-hosted. The display font's latin `.woff2` is preloaded; both load with
  `font-display: swap` (fontsource's default). Weights were snapped to values the chosen fonts
  actually support (Plus Jakarta Sans's axis tops out at 800, not 900).

### Web Privacy/Support Pages: API 301-Redirects To The Web App

- Status: Accepted and implemented.
- Product constraint: v1 contract safety for the App Store listing and in-app link
  (`mobile/eas.json`'s `EXPO_PUBLIC_PRIVACY_POLICY_URL` points at the API host,
  `https://mentioned-api.onrender.com/privacy`) - that URL must keep resolving even after the
  content's real home moves, and the public web app should not gain an API-shaped URL as its
  canonical privacy/support link.
- Notes: `src/main.py` carried ~130 lines of inline HTML for `/privacy` and `/support`, including a
  personal support email, and the web landing page's footer fell back to those same `/privacy`/
  `/support` paths (404 on the static site, since it never had those pages). Built
  `web/src/pages/privacy.astro` and `support.astro` as the real, styled home for that content and
  made the site footer link to them unconditionally. The API routes stay mounted rather than being
  deleted: a new optional `WEB_BASE_URL` setting (validated as an HTTPS origin by
  `scripts/check_release_env.py`, set to the web origin in `render.yaml`) makes them 301-redirect to
  the web pages when configured, so the App Store/in-app link keeps working unchanged. When
  `WEB_BASE_URL` is unset (e.g. a fresh environment before the web app is deployed), the API still
  serves the original inline content - now from `src/templates/*.html` instead of a Python string
  literal - so neither URL ever 404s.

### 2026-09-22 - Alembic Chain Squashed Into One Revision

- Status: Accepted and implemented.
- Product constraint: Contract safety for production's `alembic_version` (the squash must be a
  no-op for a database already at `20260922_0018`) and onboarding - a new engineer or agent reading
  the schema should have one file to read, not 17 with a legacy detour through `jobs`/`mentions`/
  `job_events` that no longer exist.
- Notes: `migrations/versions/` went from 17 files (`20260504_0003` through `20260922_0018`,
  including the hash-named `781a3572bbaf`) to one, `20260922_0018_initial_schema.py`, containing
  only the net live schema: `books`, `places`, `sources`, `source_items`, `saved_sources`,
  `push_tokens`, `waitlist_signups`, and the `extract_sources`/`push_notifications` pgmq queues. The
  revision id was kept as `20260922_0018` (the chain's old head) so production needs no
  `alembic stamp`; the next real revision continues as `20260923_0019`. Verified with a throwaway
  Postgres container (`supabase/postgres:17.6.1.167`): the old 17-file chain and the squashed file
  produce identical schema-only `pg_dump` output, `pg_policies`, `information_schema.
  role_table_grants` for `mentioned_api`/`mentioned_worker`, and `pgmq.list_queues()`; also confirmed
  `alembic downgrade base` then `upgrade head` round-trips cleanly and
  `tests/test_postgres_dedicated_worker_rls.py` still passes against the squashed schema. Did not
  attempt SQLite compatibility for the squashed file - the original chain already fails immediately
  on SQLite (raw Postgres-only RLS/pgmq/extension SQL from revision `20260504_0003` onward), and
  local dev never runs Alembic against SQLite in practice (`AUTO_CREATE_TABLES` uses
  `SQLModel.metadata.create_all` instead); the squash is no worse than the chain it replaces.

### Book Catalog And Reading List Support

> Product intent lives in `docs/strategy/product.md`. Technical work here should support the
> book-first wedge without making the architecture book-only.

- The first-class `Book` model (`src/books/models.py`), Google Books enrichment (`src/extraction/google_books.py`), and worker enrichment path (`src/worker.py`) already exist.
- Remaining technical gaps should support the user-facing catalog and reading-list UX without changing the frozen v1 contract.
- Tighten saved-book normalization and dedup at the user-catalog level, distinct from provider-level `books` dedup.

### Mobile Frontend Architecture

> Product UX goals live in `docs/strategy/product.md`; frontend refactors should make those flows
> easier to ship and validate.

- Break down large mobile surfaces into focused components, screens, hooks, and API/state modules as work touches them.
- Keep downloaded reel thumbnails available for product surfaces that show saved source history.
- Support future UX for book catalog, reading list, saved sources, and job progress without coupling the app to books as the only possible mention type.

### Media And Artifact Retention

- Decide what to do with downloaded reels after extraction.
- Keep lightweight derived artifacts where useful, such as thumbnails, sampled frames, transcript text, OCR output, and evidence snippets.
- Avoid keeping full videos forever unless there is a clear user-facing or debugging need.

### Platform Expansion

- Add TikTok support.
- Add YouTube Shorts support.
- Design platform handling through source adapters so Instagram, TikTok, and YouTube do not leak platform-specific logic across the whole app.

### Chat And Semantic Search

- Let users chat with or search across their saved lists.
- Use semantic search so users can find things that Instagram itself cannot easily search.
- Start with retrieval/search over saved structured items before building a full chat experience.

## Open Questions

- ~~Which non-book mention type should we surface first after books?~~ Settled 2026-06-25: **places first** for enrichment (see the dated note above); products are the next enrichment phase. The wedge question remains as in `docs/strategy/product.md`: v1 = books, v3 = generalize.
- What book metadata is mandatory for a good first experience: title, author, cover, description, ISBN, published date, categories?
- Should extracted mentions be considered evidence, while books become normalized saved entities?
- What is the retention policy for original downloaded videos?
- What queue/event system is worth learning without adding production complexity too early?
- Should migrations run automatically as part of deploy, manually before deploy, or through a one-off release command?

## Candidate Next Specs

1. production-ingestion-hardening (Axis A - claim safety, timeouts, idempotency, concurrency, cost control). **First.**
2. v2-contract (Axis B - polished `/v2` endpoints on shared `public` tables).
3. Book catalog UX and reading list (backend `Book`/enrichment already shipped; this is the user-facing surface).
4. Frontend component split and catalog/reading-list UX.
5. Media artifact retention policy.
6. Multi-platform source adapter design.
7. Semantic search over saved items.
8. Generalized collections / non-book mention types (v3 direction).
