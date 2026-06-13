# Mentioned Product Ideas

Last updated: 2026-06-13

This is a living backlog for product, architecture, and learning ideas. It is intentionally not a committed roadmap yet; ideas here should be promoted into specs only after we validate the next smallest step.

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

## Product Vision And Scope (read before using domain language)

Mentioned helps users turn social videos into structured, saved, organizable items. **The core object is a generic "mention" / saved item, not a book.** Books are simply the first *type we surface to users* — the data model is already type-agnostic (`MentionCategory` in `src/mentions/models.py` supports `book`, `product`, `place` today). Avoid writing as if the product *is* a book app; write as if books are one supported category among several.

Product direction by version (informal, not a committed roadmap):
- **v1 (shipped):** the books wedge — extract book recommendations from Instagram Reels. Books is the surfaced type, but the schema underneath is generic.
- **v2 (in progress):** infrastructure, not new entity types — ingestion/worker hardening + a polished `/v2` contract on shared `public` tables (see "Architecture Status").
- **v3 (future direction):** generalize beyond books — let users build a list/collection out of *any* reel, across mention types (products, places, quotes, travel, restaurants, etc.). See "Generalized Collections" below.

When writing specs, plans, or UI copy: prefer "saved item" / "mention" / "collection" as the default vocabulary, and treat "book" as a concrete example of a type — not the universal noun.

## Ideas To Preserve

### Book Catalog And Reading Lists

> Already shipped: the first-class `Book` model (`src/books/models.py`), Google Books enrichment (`src/extraction/google_books.py`), and the worker enrichment path (`src/worker.py:86`). The items below are the remaining UX/normalization GAPS, not greenfield work.

- Add user-facing book catalog UX (the `Book`/enrichment backend exists; the catalog surface does not).
- Let users create a personal to-read / reading list from extracted books.
- Tighten saved-book normalization and dedup at the user-catalog level (distinct from the provider-level `books` dedup already in place).

### Job And Worker Architecture

> Now being actioned — see "Architecture Status" above. Hardening specifics live in the planned *production-ingestion-hardening* plan (Axis A, in place on `public.jobs`). NOTE: the old `2026-06-13-v2-coexistence-foundation.md` is a REJECTED record — do not follow it.

- Revisit the current always-running worker model.
- Explore event-driven processing so extraction work starts when a job/event arrives.
- Learn queues through a practical implementation, possibly RabbitMQ, Redis Queue, Celery, Dramatiq, or a managed cloud queue.
- Decide whether database-backed jobs are enough for the current scale or whether a queue should own job delivery.

### Frontend Refactor And UX

- Break down `mobile/App.tsx` into focused components, screens, hooks, and API/state modules.
- Improve the mobile UI beyond placeholder assets.
- Use downloaded reel thumbnails when available instead of generic placeholders.
- Add UX for a book catalog, reading list, saved sources, and job progress.

### Ingestion And Cost Control

- Reduce dependence on sending every downloaded reel directly to Gemini.
- Add cheaper extraction passes before multimodal LLM calls, such as URL parsing, captions, metadata, OCR, transcripts, and frame sampling.
- Use LLM calls as a fallback or confidence booster rather than the default for every input.
- Track provider cost, latency, and confidence per extraction.

### Media And Artifact Retention

- Decide what to do with downloaded reels after extraction.
- Keep lightweight derived artifacts where useful, such as thumbnails, sampled frames, transcript text, OCR output, and evidence snippets.
- Avoid keeping full videos forever unless there is a clear user-facing or debugging need.

### Platform Expansion

- Add TikTok support.
- Add YouTube Shorts support.
- Design platform handling through source adapters so Instagram, TikTok, and YouTube do not leak platform-specific logic across the whole app.

### Generalized Collections (the v3 direction)

> This is the v3 north star from "Product Vision" above: lists/collections out of *any* reel, across types. The mention schema is already type-agnostic (`book`/`product`/`place` today), so the gap is surfacing + UX + extraction coverage, not a fundamental model rewrite.

- Surface mention types beyond books that the schema already supports (`product`, `place`), then expand the enum to new types:
  - quotes
  - outfit ideas
  - travel destinations
  - hotels
  - restaurants
- Let users build a list/collection out of any reel, mixing types within one collection.
- Decide how to model collections: typed collections, a generic `SavedItem`/collection-of-mentions, or both. (The per-type enrichment, e.g. Google Books for `book`, stays type-specific.)

### Chat And Semantic Search

- Let users chat with or search across their saved lists.
- Use semantic search so users can find things that Instagram itself cannot easily search.
- Start with retrieval/search over saved structured items before building a full chat experience.

## Open Questions

- Which non-book mention type should we surface first after books (`product` and `place` already exist in the schema)? (The wedge question is settled: v1 = books, v3 = generalize — see "Product Vision".)
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
