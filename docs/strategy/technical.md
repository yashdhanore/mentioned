# Technical Decisions And Ideation

Last updated: 2026-06-22

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

> **Read this first if you are an agent working on the backend.** As of 2026-06-13 the app is submitted to the App Store. The shipped mobile binary is frozen against the **v1 HTTP contract**, so v1 **user-visible behavior and HTTP contract must not change** — but internal worker/ingestion behavior *can* (see "Frozen = contract, not internals" below). v2 is being built *alongside* v1 in the same repo and same Supabase project — not as a replacement edit.

> **2026-06-22 update:** The saved-source cutover supersedes the old `/v1/jobs` and
> `/v1/mentions` surface before public release. Treat the job/mention contract and `/v2`
> sequencing notes below as historical compatibility context unless an already-shipped binary still
> calls them. Active app/backend work should target `/v1/saved-sources`, `sources`,
> `source_items`, and `saved_sources`.

**v1 — live. Frozen CONTRACT, not frozen internals:**
- What is frozen: the **entire `/v1` HTTP contract and user-visible semantics** the submitted app calls (verified against `mobile/src/api.ts`). These are a promise to the published app and must not change:
  - `/v1/jobs` (POST create, GET list) + `/v1/jobs/{id}` (GET, DELETE) — `src/jobs/router.py`
  - `/v1/mentions/{id}` (DELETE) — mentions router
  - `/v1/account` (DELETE) — `src/account/router.py`
  - `/v1/push-tokens` (POST) and `/v1/push-tokens/disable` (POST) — push router
  - Plus the Supabase **realtime subscription to `public.job_events`** the app relies on for completion refresh (`mobile/src/features/captures/use-captures.ts`). Changing the event shape or table is also a contract break.
- What is NOT frozen: **internal worker/ingestion behavior is allowed and desired to change in place.** Hardening `public.jobs` claiming, timeouts, idempotency, and concurrency does not alter the contract, so it ships safely to v1 users now (see Axis A).
- Data: `public.jobs`, `public.mentions` (`src/jobs/models.py`, `src/mentions/models.py`).
- Ingestion: `extract_jobs` pgmq queue → single `mentioned-worker` Render service (`src/worker.py`).
- Known brittleness (the thing Axis A fixes): single-worker SPOF, serial processing, no per-job timeout, unbounded per-job Gemini calls, non-idempotent mention writes.

**v2 — in progress. Two decoupled axes, SHARED `public` data (no separate schema):**

> A separate `v2` Postgres schema was considered and **rejected** after code review (2026-06-13). It caused split-brain data, a worker that couldn't write across schemas (FK to `public.jobs`), a dropped realtime `job_events` path, account-deletion leakage, quota bypass, and RLS/grant duplication — all for isolation the real goal never needed. The rejected plan is kept as a record at `docs/superpowers/plans/2026-06-13-v2-coexistence-foundation.md` (marked SUPERSEDED). **Do not resurrect the schema-split approach.**

The work splits along two independent axes:

- **Axis A — Production ingestion hardening (invisible to the app, do FIRST — and note this is v1-compatible, NOT gated on `/v2`):** fix the brittle claim path **in place on `public.jobs`** — `FOR UPDATE SKIP LOCKED` claiming, per-job timeout, idempotent mention writes (unique constraint or upsert), bounded Gemini concurrency. Because the "10–15 users / high expense" concern is half reliability and half *cost*, this pass also includes the cost-control track: provider budget caps, per-user cost/retry ceilings, and per-extraction cost/latency instrumentation (see "Ingestion And Cost Control" below). All of it lives *behind* the HTTP contract, so it ships safely to v1 users now, no app release required.
- **Axis B — `/v2` contract (visible to the app, do AFTER A is stable):** mount polished `/v2/*` endpoints in the same FastAPI app that **read/write the existing `public` tables**. Same auth, same data, same `job_events` realtime path, same RLS, same quotas — so none of the coexistence-tax bugs apply. The `/v2` prefix gates rollout: published app stays on `/v1`, new app build calls `/v2`. No data copy, no split-brain, because both contracts sit on one set of tables.

- **Guardrail:** Axis B builds `/v2` handlers in parallel modules; do NOT refactor the shared v1 code in `src/jobs/*` that the published app depends on. Axis A *does* modify shared worker/service code in place — that's intended, and it must keep v1 endpoints behaviorally identical (regression-test the v1 contract).

**Plans (sequenced):**
1. *production-ingestion-hardening* (to be written) — Axis A, in place on `public.jobs`. v1-compatible, NOT gated on `/v2`. Covers claim safety + timeouts + idempotency + concurrency AND the cost-control track (budget caps, per-user ceilings, retry budgets, cost/latency instrumentation). **Start here; serves the actual goal.**
2. *v2-contract* (to be written, needs an API design pass) — Axis B on shared `public` tables: improved request/response shapes, pagination, idempotency keys, error envelope.
3. *mobile-v2-cutover* (to be written) — point new app build at `/v2`, submit, retire `/v1` routes once old-app traffic hits zero.
- ⛔ `docs/superpowers/plans/2026-06-13-v2-coexistence-foundation.md` — SUPERSEDED/rejected (schema-split). Record only; do NOT execute or treat as active.

## Ideas To Preserve

### Job And Worker Architecture

> Now being actioned — see "Architecture Status" above. Hardening specifics live in the planned *production-ingestion-hardening* plan (Axis A, in place on `public.jobs`). NOTE: the old `2026-06-13-v2-coexistence-foundation.md` is a REJECTED record — do not follow it.

- Revisit the current always-running worker model.
- Explore event-driven processing so extraction work starts when a job/event arrives.
- Learn queues through a practical implementation, possibly RabbitMQ, Redis Queue, Celery, Dramatiq, or a managed cloud queue.
- Decide whether database-backed jobs are enough for the current scale or whether a queue should own job delivery.

### Ingestion And Cost Control

- Reduce dependence on sending every downloaded reel directly to Gemini.
- Add cheaper extraction passes before multimodal LLM calls, such as URL parsing, captions, metadata, OCR, transcripts, and frame sampling.
- Use LLM calls as a fallback or confidence booster rather than the default for every input.
- Track provider cost, latency, and confidence per extraction.

### 2026-06-21 - Behavior-Preserving Ingestion Module Seam

- Status: Accepted as the first architecture step before production ingestion hardening.
- Product constraint: Protects the save -> extract -> revisit loop and frozen v1 HTTP contract while
  making worker internals easier to harden in place.
- Notes: Saved source processing now belongs behind `src.ingestion.processor`, extract queue message
  handling behind `src.ingestion.queue_worker`, and push queue message handling behind
  `src.push.worker`. This does not add Axis A hardening yet; claim safety, timeouts, idempotency,
  concurrency, retry budgets, and cost instrumentation remain in the future
  *production-ingestion-hardening* plan.

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

- Which non-book mention type should we surface first after books (`product` and `place` already exist in the schema)? The wedge question is settled in `docs/strategy/product.md`: v1 = books, v3 = generalize.
- What book metadata is mandatory for a good first experience: title, author, cover, description, ISBN, published date, categories?
- Should extracted mentions be considered evidence, while books become normalized saved entities?
- What is the retention policy for original downloaded videos?
- What queue/event system is worth learning without adding production complexity too early?
- Should migrations run automatically as part of deploy, manually before deploy, or through a one-off release command?

## Candidate Next Specs

1. production-ingestion-hardening (Axis A — claim safety, timeouts, idempotency, concurrency, cost control). **First.**
2. v2-contract (Axis B — polished `/v2` endpoints on shared `public` tables).
3. Book catalog UX and reading list (backend `Book`/enrichment already shipped; this is the user-facing surface).
4. Frontend component split and catalog/reading-list UX.
5. Media artifact retention policy.
6. Multi-platform source adapter design.
7. Semantic search over saved items.
8. Generalized collections / non-book mention types (v3 direction).
