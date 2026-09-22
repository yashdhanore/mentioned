# Mentioned

[![CI](https://github.com/yashdhanore/mentioned/actions/workflows/ci.yml/badge.svg)](https://github.com/yashdhanore/mentioned/actions/workflows/ci.yml)

Mentioned turns Instagram Reels and posts you save into a list of the books, products, and places they mention.
Share a Reel or post from Instagram (or paste its link) and Mentioned downloads the media, asks Gemini what is being recommended, and saves the results against your account so you can find them again later.
It currently supports public Instagram Reel and post URLs only; the backend rejects every other host and every other Instagram content type.

## How it works

1. You share an Instagram Reel or post from the native share sheet (`mobile/ShareExtension.tsx`), or paste the link into the app.
2. The app calls `POST /v1/saved-sources` with the URL.
3. The API normalizes and validates the URL as a public Instagram Reel or post (`src/extraction/url.py`), then resolves it to a canonical source identity such as `instagram:reel:<shortcode>` (`src/sources/identity.py`).
4. If another user already saved the same canonical source, the API links your account to the existing source and its extraction, so the same Reel is never extracted twice (`src/sources/service.py`, `save_source_for_user`).
5. For a new source, the API inserts the `sources` row and sends a pgmq message on the `extract_sources` queue in the same database transaction (`src/sources/queue.py`).
6. The worker claims the source with an atomic `UPDATE ... WHERE status = 'pending' ... RETURNING` (`src/sources/service.py`, `claim_source_for_processing`).
7. `yt-dlp` downloads the media, caption, and thumbnail URL (`src/extraction/download.py`).
8. A cheap relevance gate looks at the caption and thumbnail and can skip the Gemini call when it is confident there is nothing to find; any doubt falls through to full extraction (`src/extraction/relevance.py`).
9. Gemini reads the video or images and returns structured book, product, and place mentions (`src/extraction/gemini.py`).
10. Each book mention is checked against the top five Google Books results on title and author before a cover and metadata are attached; a book nothing passes keeps its extracted title and gets no cover (`src/books/resolution.py`, `src/books/enrichment.py`).
11. The worker writes the result to `sources`/`source_items` and, in the same transaction, enqueues a push notification that the push worker fans out to every user who saved that source (`src/push/queue.py`, `src/push/worker.py`).
12. The app reads `GET /v1/saved-sources` to show saved Reels/posts and their extracted items.

```mermaid
flowchart LR
    App[Expo app or share extension] -->|POST /v1/saved-sources| API[FastAPI API]
    API --> DB[(Postgres + pgmq)]
    API -->|auth| Auth[Supabase Auth]
    DB -->|extract_sources queue| Worker[Worker]
    Worker --> Gemini[Gemini]
    Worker --> Books[Google Books]
    Worker --> DB
    Worker -->|thumbnails| Storage[Supabase Storage]
    Worker -->|push_notifications queue| Push[Expo push]
    App -->|GET /v1/saved-sources| API
    Push --> App
```

## Repository layout

| Path | Contents |
| --- | --- |
| `src/` | FastAPI API, worker, extraction pipeline, auth, push, storage. See `src/AGENTS.md`. |
| `migrations/` | Alembic revisions; the source of truth for tables, grants, and row-level security policies. See `docs/adr/0001-alembic-is-the-schema-source-of-truth.md`. |
| `tests/` | Backend pytest suite, mirroring the `src/` layout. |
| `mobile/` | Expo/React Native iOS app and share extension. See `mobile/README.md`. |
| `web/` | Astro landing page and waitlist form. |
| `supabase/` | Supabase CLI config for the local stack, storage buckets, and auth. Only the storage bucket migration does anything; the other two SQL files are no-ops kept for Supabase CLI migration history (see the ADR). |
| `scripts/` | Release checks, smoke tests, local dev scripts, eval tooling. |
| `evals/` | Hand-labeled Reels, Reel lists, and results for the extraction and book resolution evals. |
| `docs/` | Deployment runbook, extraction roadmap, architecture decision records, product/technical strategy notes. |
| `.agents/` | Shared agent commands and skills used by coding agents working in this repo. |

## Engineering notes

- **Transactional outbox for extraction.** `save_source_for_user` inserts the new `sources` row and sends the pgmq message in the same transaction, committing once, so the enqueue failing rolls back the whole save instead of leaving an unqueued row (`src/sources/service.py`; proven by `tests/sources/test_service.py::test_save_source_for_user_rolls_back_when_enqueue_fails`).
- **Atomic source claiming with a stale-attempt guard.** `claim_source_for_processing` is a single `UPDATE ... WHERE status = 'pending' ... RETURNING`, and `complete_source_processing`/`fail_source_processing` only finalize a source if it is still in the exact `processing_started_at` attempt the worker claimed, so a slow or duplicated worker can't clobber a newer attempt (`src/sources/service.py`; race tests in `tests/sources/test_service.py`).
- **Least-privilege, per-request database roles.** The API and worker connect as separate non-superuser, non-`BYPASSRLS` Postgres roles, with startup refusing to boot in production if either role has elevated privileges, and row-level security context is set per transaction via `set_config('app.current_user_id', ...)` in a SQLAlchemy `after_begin` hook rather than once per connection (`src/database.py`).
- **Thumbnail fetcher hardened against SSRF.** Thumbnails are only fetched from an allowlisted Instagram CDN host suffix, redirects are followed manually and re-validated against the same allowlist, only a fixed set of image content types is accepted, and the response body is streamed with a hard byte cap instead of trusting `Content-Length` (`src/storage/thumbnails.py`).
- **Relevance gate with a shadow mode.** Before the expensive Gemini video call, a cheap caption+thumbnail check can skip extraction, but only in `active` mode and only on a confident `irrelevant` verdict; `shadow` mode logs the verdict without skipping anything (`src/extraction/relevance.py`, `src/extraction/pipeline.py`).
  The gate fails open to full extraction on any error, and a permanent 4xx from the gate model (such as a retired model returning 404) logs at error level so a broken gate is visible.
- **A release gate script instead of a manual checklist.** `scripts/check_release_env.py` checks the production environment shape (auth mode, HTTPS enforcement, distinct database URLs, CORS and host allowlists, rate-limit and media-size guardrails, worker replica count) without printing secrets.
  It runs in the worker's Render pre-deploy step before migrations, so a misconfigured deploy stops there (`scripts/render-predeploy.sh`).
- **Catalog resolution that refuses to guess.** The first Google Books result for a title is often a summary, a sequel, or a box set, so the resolver checks the top five on title and author and leaves an unconfirmed book unattached (`src/books/resolution.py`).
  A text-only tool-using agent can then search up to three more times for the books the check could not confirm, and may only pick a volume it has seen in a search result (`src/books/resolution_agent.py`, eval only for now).
- **A strict allowlist for shared URLs, on both ends.** Text from the share extension and share deep links goes through one parser that only accepts `https://instagram.com` or `https://www.instagram.com` URLs with a `/reel/` or `/p/` path (`mobile/src/utils/shared-source-url.ts`).
  Pasted links are sent as typed and rely on the same rule in the API (`src/extraction/url.py`, `src/sources/identity.py`).

## Extraction quality

Extraction is measured against 22 hand-labeled Reels (131 books), scored as precision and recall with 95% Wilson intervals, cost per correct mention, and latency (`evals/`, `scripts/score_extraction_eval.py`).
Latest run, 2026-09-22:

| Model | Precision | Recall | Cost per 1,000 correct mentions |
| --- | --- | --- | --- |
| `gemini-2.5-flash` (previous production default) | 0.963 | 0.992 | $1.26 |
| `gemini-3.1-flash-lite` (production) | 0.992 | 0.992 | $0.27 |
| `gemini-3.8-flash` | 1.000 | 0.992 | $1.03 |

Error analysis drove the changes: about half of the first run's errors turned out to be labeling mistakes, and most of the rest were places leaking into book Reels ("Turkey" captioned next to a book set there), which a prompt fix cut from 12 to 1 with no loss of recall.
A confidence threshold looked like a free win and was dropped when the next run showed the model's confidence was not stable.
The set has no place, product, or empty Reels yet, so it says nothing about recall on those.
Full results, method, and limits are in [`evals/README.md`](evals/README.md#results).

The step after extraction is measured too: does each book end up attached to the right catalog entry (`scripts/score_resolution_eval.py`)?
On the 126 unique labeled books, hand-checked:

| Strategy | Same work | Collection or bundle | Wrong book | Unresolved |
| --- | --- | --- | --- | --- |
| First Google Books hit (previous production) | 110 | 6 | 6 | 4 |
| Top 5 checked on title and author (production) | 122 | 0 | 0 | 4 |
| Top 5 + tool-using agent for the rest (eval only) | 124 | 1 | 0 | 1 |

The first hit showed 5% of books with the wrong cover (a summary, a sequel, a theatre adaptation); the check removed all of them without losing a book, and the agent recovered three of the four it could not confirm for about half a cent in total.
Details and limits are in [`evals/README.md`](evals/README.md#book-resolution).

## Known limitations

- Place enrichment is wired up end to end but the actual Google Places lookup is a stub that always returns nothing (`src/places/enrichment.py`, `find_google_place_sync`); place mentions are stored without address or map data today.
- The worker is single-process and deployed as exactly one Render instance (`render.yaml`, `numInstances: 1`); there is no bounded-concurrency or multi-worker extraction path yet.
- Only Instagram is supported, and every other host is rejected at the URL-validation layer (`src/extraction/url.py`).

## Local development (full stack)

Run the API, worker, web app, and mobile app (Expo web) together against a local Postgres, with the same queue-based pipeline as production:

```bash
make dev       # starts everything
make dev-logs  # tail all logs together
make dev-down  # stops everything; local DB state is kept for next time
```

First run bootstraps a local Postgres via the Supabase CLI (`supabase start`), creates the `mentioned_api`/`mentioned_worker` roles, and applies all Alembic and Supabase-managed migrations automatically.
If `make dev` stops with `Can't locate revision identified by '20260628_0016'` (or another old revision), your local database predates the 2026-09-22 migration squash; if it holds nothing you need, run `supabase db reset --local` and then `make dev` again.
Requires Docker, the Supabase CLI (`brew install supabase/tap/supabase`), and the backend `.venv` from `uv sync --frozen --extra dev`.

`scripts/dev-up.sh` exports these for the API and worker processes it starts, so `make dev` uses Postgres (queue-backed worker, real RLS) with no `.env` edits:

```
DATABASE_URL=postgresql://mentioned_api:local-dev-api-pw@127.0.0.1:54322/postgres
WORKER_DATABASE_URL=postgresql://mentioned_worker:local-dev-worker-pw@127.0.0.1:54322/postgres
```

Running `fastapi dev` or `mentioned-worker` directly (outside `make dev`), without these set in your `.env`, falls back to SQLite.
On SQLite there is no pgmq, so `enqueue_source_extraction` is a no-op and the worker instead polls for pending `Source` rows and claims them with the same atomic claim used in production (`src/worker.py`, `claim_next_pending_source`).

Real extraction needs `EXTRACTION_BACKEND=gemini` and a `GEMINI_API_KEY`; install `ffmpeg` too, or videos over the size limit are sent uncompressed (`src/extraction/download.py`).
`.env.example` ships `EXTRACTION_BACKEND=local`, a stub that always returns zero mentions (`src/extraction/local_pipeline.py`).
A `GOOGLE_BOOKS_API_KEY` is optional but recommended: without it, book cover/metadata lookups are unauthenticated and get rate-limited almost immediately.

## Tests and checks

Backend, using [uv](https://docs.astral.sh/uv/):

```bash
uv sync --frozen --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

A Postgres role/RLS proof is skipped unless three connection strings are set (an admin or owner role, the API role, and the worker role):

```bash
POSTGRES_TEST_DATABASE_URL=postgresql://admin-or-owner-url \
POSTGRES_TEST_API_DATABASE_URL=postgresql://mentioned_api-url \
POSTGRES_TEST_WORKER_DATABASE_URL=postgresql://mentioned_worker-url \
uv run pytest tests/test_postgres_dedicated_worker_rls.py
```

Mobile, from `mobile/`:

```bash
npm test
```

This runs five focused scripts (capture flow, shared-source intake, share URL parsing, pending shared source, Supabase config), then ESLint, then `tsc --noEmit`.

Web, from `web/`:

```bash
npm test
```

This runs `astro check`, an `astro build`, and the Playwright end-to-end suite.

CI (`.github/workflows/ci.yml`) runs the backend, mobile, and web checks on every pull request and on every push to `main`.

## API

Auth: `AUTH_MODE=supabase` in production, verifying the caller's Supabase access token as a bearer token; local development defaults to `AUTH_MODE=dev`, which either uses `DEV_USER_ID` or accepts `Authorization: Bearer dev:<uuid>` to simulate a different user.

- `POST /v1/saved-sources` - save an Instagram Reel/post URL; queues extraction if nobody has saved it yet, and retries it if the caller's earlier save failed.
- `GET /v1/saved-sources` - list the authenticated user's saved sources.
- `GET /v1/saved-sources/{saved_source_id}` - get one saved source's status and extracted items.
- `DELETE /v1/saved-sources/{saved_source_id}` - unlink that saved source for the authenticated user.
- `DELETE /v1/account` - delete the caller's owned data (saved sources, push tokens) and their Supabase auth user.
- `POST /v1/push-tokens` / `POST /v1/push-tokens/disable` - register or disable an Expo push token.
- `POST /v1/waitlist` - record a waitlist signup from the landing page.

## Deployment

Mentioned deploys as three Render services (a static web build, the API, and the worker) against one Supabase project, with Alembic migrations applied by the worker's pre-deploy step.
See [`docs/deployment.md`](docs/deployment.md) for role setup, environment variables, release checks, mobile build configuration, and the smoke test.

## Working with AI agents

`AGENTS.md` at the root and in nested directories holds the instructions coding agents follow for that part of the codebase; the root `CLAUDE.md` is a symlink to the root `AGENTS.md`.
`.agents/` holds commands and skills shared across agent tools, with `.claude/` and `.cursor/` symlinked into it so different tools see the same instructions.
`docs/strategy/product.md` and `docs/strategy/technical.md` are the running decision log for product and technical choices, including approaches that were considered and rejected; `docs/adr/` holds shorter, single-decision architecture records.
