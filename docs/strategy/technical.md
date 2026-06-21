# Technical Decisions And Ideation

Last updated: 2026-06-21

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
