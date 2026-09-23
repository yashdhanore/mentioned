# Test Agent Guide

`tests/` contains pytest coverage for the backend and extraction behavior.

## Patterns

- Follow the root [Testing](../AGENTS.md#testing) policy: E2E tests first, isolation tests only after listing the ways the system can fail.
- E2E tests live in `tests/e2e/`, run against the real local stack from `make dev` (Supabase Auth, Postgres with the `mentioned_api` role, API processes they boot themselves), and skip when that stack is not running.
  Fake external providers at the network or process boundary with the fakes in `tests/e2e/fakes.py`: Gemini through the SDK's `GOOGLE_GEMINI_BASE_URL`, Google Books by pointing `src.extraction.google_books.GOOGLE_BOOKS_API` at a local server, and the Instagram download as a fake `yt-dlp` first on PATH (`tests/e2e/fake_yt_dlp.py`); never contact Instagram from a test.
  Install the harness `NetworkGuard` in a suite that runs the worker in-process, so any other outbound connection fails the test instead of reaching a real provider.
  A suite that saves through the real API, which queues extraction with no delay, runs in its own Alembic-migrated database (`IsolatedDatabase` in the harness), because the running `make dev` worker polls the queue in the `postgres` database and would try to download the Reel from Instagram; it drives the worker by calling the worker's loop body (`src.worker._run_queue_worker_iteration`).
  Shared plumbing (report, local stack discovery, API processes, isolated database, network guard) lives in `tests/e2e/harness.py`.
  Each suite writes a JSON report of every check plus the API logs to `outputs/e2e/<suite>/<run>/`, with a copy of the newest report at `outputs/e2e/<suite>/latest.json`.
  A scenario for a product bug that is not fixed yet asserts the correct behavior, passes `known_bug=` to `report.scenario`, and is marked `pytest.mark.xfail(strict=True, raises=AssertionError)`, so the run stays green and turns red once the bug is fixed.
- Place tests in `tests/test_*.py` or the relevant feature subdirectory with functions named `test_*`.
- In isolation tests, prefer `tmp_path`, `monkeypatch`, and in-process fakes for file, provider, and subprocess behavior so tests stay deterministic and offline.
- For provider integrations, cover both the configured-provider path and the fallback path.
- Keep tests focused on the behavior changed; broaden coverage when shared contracts, queues, auth, storage, or extraction output shape changes.

## Commands

- Run all backend tests with `pytest`; the E2E suites run too when `make dev` is up.
- Run only the E2E suites with `pytest tests/e2e -v`.
- CI runs them in the `e2e` job with `E2E_REQUIRED=1`, which fails the run instead of skipping when the stack is missing; download a run's reports from the job's `e2e-reports` artifact.
- Run focused suites with paths such as `pytest tests/sources`, `pytest tests/extraction`, or `pytest tests/auth`.
- Update this guide when test layout, required fixtures, offline strategy, or validation commands change.
